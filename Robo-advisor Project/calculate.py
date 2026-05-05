import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf
from sklearn.linear_model import Ridge
from sklearn.decomposition import PCA
from sklearn.model_selection import TimeSeriesSplit
import warnings

warnings.filterwarnings("ignore")
np.random.seed(42)

# ============================================================
# CONFIG
# ============================================================
TRADING_DAYS = 252
START_DATE_DEFAULT = "2018-01-01"
RISK_FREE_DEFAULT = 0.042
INFLATION_DEFAULT = 0.025

DEFAULT_ASSETS = [
    "AAPL","MSFT","NVDA","GOOGL","META","AMZN","JPM","AVGO","LLY","XOM",
    "UNH","COST","TSLA","AMD","PEP","AZN.L","SHEL.L","HSBA.L","ULVR.L",
    "BP.L","RIO.L","GSK.L","DGE.L","REL.L","NG.L","VOD.L","BATS.L","LSEG.L","RTX",
    "BARC.L","AAL.L", "RR.L","AIR.PA","LMT","GLD","BTC-USD","ETH-USD","BIL","VGOV.L"
]

BENCHMARKS = {
    "S&P 500": "^GSPC",
    "FTSE 100": "^FTSE",
    "Nasdaq": "^IXIC"
}


# ============================================================
# Small helpers
# ============================================================
def is_crypto_ticker(t: str) -> bool:
    u = t.upper()
    return ("-USD" in u) or ("-GBP" in u) or u.endswith("USD") or u.endswith("GBP") or u in {"BTC", "ETH"}


def _as_bizdays(df: pd.DataFrame):
    return df.sort_index().asfreq("B")


# ============================================================
# Robust prices + dividends download
# ============================================================
def download_prices_and_dividends(assets, start_date):
    raw = yf.download(
        assets,
        start=start_date,
        auto_adjust=False,
        actions=True,
        progress=False,
        group_by="column"
    )

    if raw is None or raw.empty:
        raise ValueError("yfinance returned empty data. Check tickers/date range.")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Adj Close" in raw.columns.get_level_values(0):
            px = raw["Adj Close"]
        elif "Close" in raw.columns.get_level_values(0):
            px = raw["Close"]
        else:
            raise ValueError("yfinance data did not include 'Adj Close' or 'Close'.")

        div = raw["Dividends"] if ("Dividends" in raw.columns.get_level_values(0)) else None
    else:
        px = raw["Adj Close"] if "Adj Close" in raw.columns else raw["Close"]
        div = raw["Dividends"] if "Dividends" in raw.columns else None

    px = px.dropna(how="all")

    if isinstance(px, pd.Series):
        px = px.to_frame()

    if div is None:
        div = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    else:
        if isinstance(div, pd.Series):
            div = div.to_frame(name=px.columns[0])
        div = div.reindex_like(px).fillna(0.0)

    # fallback dividend fetch
    if (div.sum().sum() == 0) and (len(px.columns) > 0):
        div_fix = pd.DataFrame(0.0, index=px.index, columns=px.columns)
        for t in px.columns:
            try:
                d = yf.Ticker(t).dividends
                if d is None or d.empty:
                    continue
                d = d[d.index >= pd.to_datetime(start_date)]
                d = d.reindex(px.index, fill_value=0.0)
                div_fix[t] = d.values
            except Exception:
                pass

        if div_fix.sum().sum() > 0:
            div = div_fix.reindex_like(px).fillna(0.0)

    return px, div


# ============================================================
# Cleaning + returns
# ============================================================
def robust_returns_from_prices(
    prices: pd.DataFrame,
    align_business_days: bool = True,
    ffill_limit: int = 3,
    min_obs_per_asset: int = 252,
    min_day_coverage: float = 0.80,
    min_asset_coverage: float = 0.80
):
    px = prices.copy()

    failed = [c for c in px.columns if px[c].isna().all()]
    if failed:
        px = px.drop(columns=failed)

    px = px.dropna(axis=1, thresh=int(min_obs_per_asset))
    if px.shape[1] < 2:
        raise ValueError(f"Too few assets after cleaning prices (need ≥2). Remaining={px.shape[1]}.")

    if align_business_days:
        px = _as_bizdays(px)

    if ffill_limit and int(ffill_limit) > 0:
        px = px.ffill(limit=int(ffill_limit))

    r = px.pct_change()
    r = r.dropna(thresh=int(min_day_coverage * r.shape[1]))
    r = r.dropna(axis=1, thresh=int(min_asset_coverage * r.shape[0]))

    if r.shape[0] < 2:
        raise ValueError("Returns became empty after cleaning. Relax thresholds or extend date range.")
    if r.shape[1] < 2:
        raise ValueError("Too few assets after cleaning returns. Relax thresholds.")

    px = px[r.columns]

    return r, px, failed


def autotune_cleaning_settings(prices_raw: pd.DataFrame, assets: list[str]):
    n_assets = len(assets)
    has_crypto = any(is_crypto_ticker(a) for a in assets)

    align_bd = True
    ffill = 3 if has_crypto else 2

    counts = prices_raw.notna().sum()
    med = int(np.nanmedian(counts.values)) if len(counts) else 0
    min_obs = int(np.clip(min(504, med), 126, 756))

    if n_assets >= 30:
        day_cov = 0.65
        asset_cov = 0.65
    elif n_assets >= 15:
        day_cov = 0.75
        asset_cov = 0.75
    else:
        day_cov = 0.85
        asset_cov = 0.85

    return align_bd, ffill, min_obs, day_cov, asset_cov


def try_cleaning_with_fallback(prices_raw: pd.DataFrame, align_bd, ffill, min_obs, day_cov, asset_cov):
    ladders = [
        (align_bd, ffill, min_obs, day_cov, asset_cov),
        (align_bd, max(ffill, 1), max(126, min_obs - 126), min(day_cov, 0.70), min(asset_cov, 0.70)),
        (align_bd, max(ffill, 1), 126, 0.60, 0.60),
        (align_bd, 0, 126, 0.55, 0.55),
    ]

    last_err = None
    for p in ladders:
        try:
            r, px, failed = robust_returns_from_prices(
                prices_raw,
                align_business_days=p[0],
                ffill_limit=p[1],
                min_obs_per_asset=p[2],
                min_day_coverage=p[3],
                min_asset_coverage=p[4]
            )
            return r, px, failed, p
        except Exception as e:
            last_err = e

    raise last_err


def prepare_returns(prices_raw, assets):
    align_bd, ffill, min_obs, day_cov, asset_cov = autotune_cleaning_settings(prices_raw, assets)

    r, px, failed, params = try_cleaning_with_fallback(
        prices_raw,
        align_bd,
        ffill,
        min_obs,
        day_cov,
        asset_cov
    )

    return {
        "returns": r,
        "prices": px,
        "failed_assets": failed,
        "params_used": params
    }


# ============================================================
# MPT core
# ============================================================
def estimate_mu_cov(r: pd.DataFrame, inflation: float):
    mu = (r.mean() - 0.5 * r.var()) * TRADING_DAYS - inflation
    cov = LedoitWolf().fit(r.values).covariance_ * TRADING_DAYS
    return mu.values, cov


def portfolio_perf(w: np.ndarray, mu: np.ndarray, cov: np.ndarray):
    ret = float(w @ mu)
    vol = float(np.sqrt(max(1e-18, w.T @ cov @ w)))
    return ret, vol


def per_asset_sharpe(mu: np.ndarray, cov: np.ndarray, risk_free: float) -> np.ndarray:
    vols = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    s = (mu - risk_free) / vols
    return np.clip(s, -3.0, 6.0)

# ============================================================
# Sortino helpers (NEW)
# ============================================================
def downside_deviation_ann(r_daily: pd.Series, mar_annual: float = 0.0) -> float:
    if r_daily is None or len(r_daily) < 5:
        return np.nan
    mar_d = float(mar_annual) / TRADING_DAYS
    d = (r_daily - mar_d).values
    d = d[d < 0.0]
    if d.size < 2:
        return 0.0
    return float(np.sqrt(np.mean(d**2)) * np.sqrt(TRADING_DAYS))

def sortino_ratio_ann(r_daily: pd.Series, rf_annual: float) -> float:
    if r_daily is None or len(r_daily) < 5:
        return np.nan
    mu_ann = float(r_daily.mean() * TRADING_DAYS)
    dd = downside_deviation_ann(r_daily, mar_annual=rf_annual)
    if dd <= 0:
        return np.nan
    return float((mu_ann - float(rf_annual)) / dd)


def portfolio_daily_returns(returns: pd.DataFrame,
                            weights: np.ndarray,
                            rf_weight: float,
                            risk_free: float) -> pd.Series:

    # risky portfolio returns
    r_risky = returns.values @ weights

    # risk-free daily return
    rf_daily = risk_free / TRADING_DAYS

    # combine
    r_total = (1.0 - rf_weight) * r_risky + rf_weight * rf_daily

    return pd.Series(r_total, index=returns.index)


def build_max_weight_bounds(
    mu: np.ndarray,
    cov: np.ndarray,
    risk_free: float,
    hard_cap: float,
    long_short: bool,
    use_sharpe_caps: bool,
    sharpe_strength: float
):
    n = len(mu)
    cap = float(np.clip(hard_cap, 0.02, 1.0))
    lo_cap = -cap if long_short else 0.0
    hi_cap = cap

    if (not use_sharpe_caps) or sharpe_strength <= 0:
        return [(lo_cap, hi_cap)] * n

    s = per_asset_sharpe(mu, cov, risk_free=risk_free)
    s_pos = np.maximum(s, 0.0)
    if np.all(s_pos == 0):
        return [(lo_cap, hi_cap)] * n

    s_norm = s_pos / (np.max(s_pos) if np.max(s_pos) > 0 else 1.0)
    base = cap * (1.0 - 0.5 * float(sharpe_strength))
    boost = cap * (1.0 + 0.25 * float(sharpe_strength))
    max_abs = np.clip(base + (boost - base) * s_norm, 0.01, cap)

    if long_short:
        return [(-float(m), float(m)) for m in max_abs]
    return [(0.0, float(m)) for m in max_abs]


def optimise(
    mu: np.ndarray,
    cov: np.ndarray,
    mode: str,
    risk_aversion: float,
    risk_free: float,
    bounds,
    long_short: bool,
    max_gross: float
):
    n = len(mu)
    w0 = np.ones(n) / n
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    if long_short:
        mg = float(max(1.0, max_gross))
        cons.append({"type": "ineq", "fun": lambda w, mg=mg: mg - np.sum(np.abs(w))})

    def obj(w):
        r, v = portfolio_perf(w, mu, cov)
        if mode == "Sharpe":
            return -((r - risk_free) / v) if v > 0 else 1e9
        return -(r - 0.5 * risk_aversion * v * v)

    res = minimize(
        obj,
        w0,
        bounds=bounds,
        constraints=cons,
        method="SLSQP",
        options={"maxiter": 500, "ftol": 1e-10}
    )

    return res.x if res.success else w0


# ============================================================
# Dividends
# ============================================================
def dividend_yield_by_asset(prices: pd.DataFrame, dividends: pd.DataFrame):
    dividends = dividends.reindex_like(prices).fillna(0.0)
    div_ttm = dividends.rolling(window=252, min_periods=1).sum().iloc[-1]
    last_px = prices.iloc[-1]
    yld = (div_ttm / last_px).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return yld


def portfolio_dividend_yield(w, prices: pd.DataFrame, dividends: pd.DataFrame):
    if isinstance(w, pd.Series):
        w_series = w.copy()
    else:
        w_series = pd.Series(np.asarray(w, dtype=float), index=list(prices.columns))

    cols = [c for c in w_series.index if c in prices.columns and c in dividends.columns]
    if len(cols) == 0:
        return 0.0

    wv = w_series.loc[cols].values.astype(float)
    yld = dividend_yield_by_asset(prices[cols], dividends[cols]).values.astype(float)
    return float(np.nansum(wv * yld))


def contribution_steps_per_year(freq: str):
    return {"Monthly": 12, "Quarterly": 4, "Annual": 1}.get(freq, 12)


def rebalance_steps_per_year(freq: str):
    return {"None": 0, "Monthly": 12, "Quarterly": 4, "Annual": 1}.get(freq, 0)


# ============================================================
# CAPM + APT + ML expected returns
# ============================================================
def monthly_asset_returns_from_daily(returns: pd.DataFrame) -> pd.DataFrame:
    return (1.0 + returns).resample("ME").prod() - 1.0


def capm_estimates(asset_monthly: pd.DataFrame, bench_monthly: pd.Series, rf_annual: float):
    rf_m = rf_annual / 12.0
    y = asset_monthly.sub(rf_m, axis=0).dropna(how="all")
    x = (bench_monthly - rf_m).reindex(y.index).dropna()
    y = y.reindex(x.index).dropna(how="any")

    if y.empty or x.empty:
        raise ValueError("Not enough overlapping monthly data for CAPM.")

    xm = x.values.reshape(-1, 1)
    betas, alphas = {}, {}

    for c in y.columns:
        yc = y[c].values
        reg = Ridge(alpha=1.0, fit_intercept=True).fit(xm, yc)
        betas[c] = float(reg.coef_[0])
        alphas[c] = float(reg.intercept_)

    beta = pd.Series(betas)
    alpha = pd.Series(alphas)
    mkt_prem_m = float(x.mean())
    capm_mu_m = rf_m + beta * mkt_prem_m + alpha
    capm_mu_ann = (1.0 + capm_mu_m).pow(12) - 1.0

    return beta, alpha, capm_mu_ann


def apt_statistical(asset_monthly: pd.DataFrame, n_factors: int, include_benchmark: bool, bench_monthly: pd.Series | None):
    X = asset_monthly.dropna(how="any")
    if X.shape[0] < 24:
        raise ValueError("APT needs more monthly history (try earlier start date).")

    if include_benchmark and bench_monthly is not None:
        bm = bench_monthly.reindex(X.index)
        if bm.notna().sum() > 0:
            X = X.copy()
            X["__BM__"] = bm

    Z = (X - X.mean()) / (X.std(ddof=0) + 1e-12)
    k = int(np.clip(n_factors, 1, min(10, Z.shape[1] - 1)))
    pca = PCA(n_components=k).fit(Z.values)

    factors = pd.DataFrame(
        pca.transform(Z.values),
        index=Z.index,
        columns=[f"F{i+1}" for i in range(k)]
    )
    premia = factors.mean(axis=0)
    loadings = pd.DataFrame(pca.components_.T, index=Z.columns, columns=factors.columns)
    z_mu = loadings @ premia
    mu_m = (z_mu * (X.std(ddof=0) + 1e-12) + X.mean())
    mu_m = mu_m.drop(index="__BM__", errors="ignore")
    mu_ann = (1.0 + mu_m).pow(12) - 1.0
    exposures = loadings.drop(index="__BM__", errors="ignore")

    return mu_ann, exposures, premia, factors


def ml_predict_next_month_mu(asset_monthly: pd.DataFrame, bench_monthly: pd.Series | None, n_lags: int = 6):
    X = asset_monthly.dropna(how="any")
    if X.shape[0] < (24 + n_lags + 1):
        raise ValueError("ML forecast needs more monthly history (try earlier start date).")

    bm = bench_monthly.reindex(X.index) if bench_monthly is not None else None

    mu_next = {}
    r2s = {}

    for c in X.columns:
        s = X[c].copy()
        df = pd.DataFrame({"y": s.shift(-1)})

        for k in range(1, n_lags + 1):
            df[f"lag{k}"] = s.shift(k)

        if bm is not None:
            for k in range(1, min(3, n_lags) + 1):
                df[f"bm_lag{k}"] = bm.shift(k)

        df = df.dropna()

        if df.shape[0] < 30:
            mu_next[c] = float(s.iloc[-1])
            r2s[c] = np.nan
            continue

        Xmat = df.drop(columns=["y"]).values
        y = df["y"].values
        tscv = TimeSeriesSplit(n_splits=4)

        scores = []
        for tr, te in tscv.split(Xmat):
            reg = Ridge(alpha=10.0).fit(Xmat[tr], y[tr])
            scores.append(reg.score(Xmat[te], y[te]))

        r2 = float(np.nanmean(scores)) if len(scores) else np.nan

        reg = Ridge(alpha=10.0).fit(Xmat, y)
        last_row = df.drop(columns=["y"]).iloc[[-1]].values
        pred = float(reg.predict(last_row)[0])

        mu_next[c] = pred
        r2s[c] = r2

    return pd.Series(mu_next), pd.Series(r2s)


# ============================================================
# Monte Carlo simulation
# ============================================================
def sample_multivariate_t(rng, df: int, dim: int) -> np.ndarray:
    z = rng.standard_normal(dim)
    u = rng.chisquare(df)
    scale = np.sqrt(u / df) if u > 0 else 1.0
    return z / scale


def simulate_paths(
    mu_ann,
    cov_ann,
    w_risky,
    rf_weight,
    years,
    initial,
    contrib_amount,
    contrib_freq,
    rebalance_freq,
    runs,
    risk_free,
    prices,
    dividends,
    reinvest_divs=True,
    seed=42,
    mc_model="t",
    t_df=6
):
    rng = np.random.default_rng(seed)
    steps = years * 12

    mu_m = np.asarray(mu_ann) / 12.0
    cov_m = np.asarray(cov_ann) / 12.0
    rf_m = float(risk_free) / 12.0

    w_series = pd.Series(np.asarray(w_risky, dtype=float), index=list(prices.columns))
    div_y = portfolio_dividend_yield(w_series, prices, dividends)
    div_m = div_y / 12.0

    contrib_per_year = contribution_steps_per_year(contrib_freq)
    contrib_interval = int(12 / contrib_per_year) if contrib_per_year else 1

    reb_per_year = rebalance_steps_per_year(rebalance_freq)
    reb_interval = int(12 / reb_per_year) if reb_per_year else 0

    try:
        L = np.linalg.cholesky(cov_m + 1e-12 * np.eye(len(mu_m)))
    except np.linalg.LinAlgError:
        L = np.linalg.cholesky(np.diag(np.clip(np.diag(cov_m), 1e-12, None)))

    values = np.zeros((runs, steps), dtype=float)
    incomes = np.zeros((runs, steps), dtype=float)

    for i in range(runs):
        income = 0.0

        risky_bucket = float(initial) * (1.0 - rf_weight)
        rf_bucket = float(initial) * rf_weight

        for t in range(steps):
            if t % contrib_interval == 0:
                risky_bucket += float(contrib_amount) * (1.0 - rf_weight)
                rf_bucket += float(contrib_amount) * rf_weight

            if mc_model == "normal":
                z = rng.standard_normal(len(mu_m))
                asset_ret = mu_m + (L @ z)
            else:
                zt = sample_multivariate_t(rng, int(t_df), len(mu_m))
                asset_ret = mu_m + (L @ zt)

            rp = float(np.dot(w_risky, asset_ret))

            risky_bucket *= (1.0 + rp)
            rf_bucket *= (1.0 + rf_m)

            div_cash = risky_bucket * div_m
            if reinvest_divs:
                risky_bucket += div_cash
            else:
                income += div_cash

            if reb_interval and (t + 1) % reb_interval == 0:
                total = risky_bucket + rf_bucket
                risky_bucket = total * (1.0 - rf_weight)
                rf_bucket = total * rf_weight

            values[i, t] = risky_bucket + rf_bucket
            incomes[i, t] = income

    return values, incomes


# ============================================================
# Expected returns pipeline
# ============================================================
def compute_expected_returns(
    returns: pd.DataFrame,
    bench_rets: pd.DataFrame,
    risk_free: float,
    inflation: float,
    capm_benchmark_name: str,
    apt_factors: int,
    apt_include_benchmark: bool
):
    assets_used = list(returns.columns)

    if len(assets_used) < 2:
        raise ValueError("Too few assets after cleaning.")

    # ---------- MPT ----------
    mu_mpt, cov = estimate_mu_cov(returns, inflation=inflation)
    mu_mpt_s = pd.Series(mu_mpt, index=assets_used)

    # ---------- Monthly ----------
    asset_monthly = monthly_asset_returns_from_daily(returns).dropna(how="any")

    capm_ticker = BENCHMARKS[capm_benchmark_name]
    if capm_ticker not in bench_rets.columns:
        raise ValueError(f"Benchmark {capm_benchmark_name} not available.")

    bench_monthly = (1.0 + bench_rets[capm_ticker].dropna()).resample("ME").prod() - 1.0
    bench_monthly = bench_monthly.reindex(asset_monthly.index).dropna()

    # ---------- CAPM ----------
    try:
        capm_beta, capm_alpha, capm_mu_ann = capm_estimates(
            asset_monthly,
            bench_monthly,
            rf_annual=risk_free
        )
        capm_mu_ann = capm_mu_ann.reindex(assets_used).fillna(mu_mpt_s)
    except Exception:
        capm_mu_ann = mu_mpt_s.copy()

    # ---------- APT ----------
    try:
        apt_mu_ann, apt_exposures, apt_premia, apt_factors_ts = apt_statistical(
            asset_monthly,
            n_factors=int(apt_factors),
            include_benchmark=apt_include_benchmark,
            bench_monthly=bench_monthly
        )
        apt_mu_ann = apt_mu_ann.reindex(assets_used).fillna(mu_mpt_s)
    except Exception:
        apt_mu_ann = mu_mpt_s.copy()

    # ---------- ML ----------
    try:
        ml_mu_next_m, ml_r2 = ml_predict_next_month_mu(
            asset_monthly,
            bench_monthly,
            n_lags=6
        )
    except Exception:
        ml_mu_next_m = pd.Series(0.0, index=assets_used)

    ml_mu_ann = (1.0 + ml_mu_next_m).pow(12) - 1.0

    return {
        "mu_mpt": mu_mpt_s,
        "cov": cov,
        "capm_mu": capm_mu_ann,
        "apt_mu": apt_mu_ann,
        "ml_mu": ml_mu_ann,
        "assets": assets_used
    }


# ============================================================
# Model selection
# ============================================================
def select_mu_model(
    model: str,
    mu_mpt_s,
    capm_mu_ann,
    apt_mu_ann,
    ml_mu_ann,
    ml_blend: float
):
    if model == "mpt":
        mu_sel_s = mu_mpt_s.copy()
    elif model == "capm":
        mu_sel_s = capm_mu_ann.copy()
    elif model == "apt":
        mu_sel_s = apt_mu_ann.copy()
    else:
        base = (mu_mpt_s + capm_mu_ann + apt_mu_ann) / 3.0
        mu_sel_s = (1.0 - ml_blend) * base + ml_blend * ml_mu_ann

    mu_sel_s = mu_sel_s.replace([np.inf, -np.inf], np.nan).fillna(mu_mpt_s)
    return mu_sel_s


def run_portfolio_optimisation(
    mu_sel_s,
    cov_df,
    config: dict,
    risk_free: float
):
    assets = list(mu_sel_s.index)

    mu = mu_sel_s.loc[assets].values
    cov = cov_df.loc[assets, assets].values

    bounds = build_max_weight_bounds(
        mu=mu,
        cov=cov,
        risk_free=risk_free,
        hard_cap=config["max_weight"],
        long_short=config["long_short"],
        use_sharpe_caps=config["use_sharpe_caps"],
        sharpe_strength=config["sharpe_strength"]
    )

    weights = optimise(
        mu,
        cov,
        mode=config["strategy"],
        risk_aversion=config["risk_aversion"],
        risk_free=risk_free,
        bounds=bounds,
        long_short=config["long_short"],
        max_gross=config["max_gross"]
    )

    port_r, port_v = portfolio_perf(weights, mu, cov)

    return {
        "weights": weights,
        "return": port_r,
        "vol": port_v,
        "assets": assets
    }


def run_portfolio_simulation(
    mu,
    cov,
    weights,
    prices,
    dividends,
    config: dict,
    risk_free: float,
    reinvest=True
):
    sims, incomes = simulate_paths(
        mu_ann=mu,
        cov_ann=cov,
        w_risky=weights,
        rf_weight=config["rf_weight"],
        years=config["years"],
        initial=config["initial"],
        contrib_amount=config["contribution"],
        contrib_freq=config["contribution_freq"],
        rebalance_freq=config["rebalance_freq"],
        runs=config["runs"],
        risk_free=risk_free,
        prices=prices,
        dividends=dividends,
        reinvest_divs=reinvest
    )

    return {
        "simulations": sims,
        "incomes": incomes
    }
