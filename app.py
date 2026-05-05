# This is the app.py code for Tom's ML_PRTFLO_model_v5.ipnb file
# It uses Flask to create a web app that allows users to input their investment preferences and see the results of the portfolio optimisation and simulation. 
# The code uses yfinance to download stock data, and Plotly to create interactive charts. 
# The calculations are made in the calculate.py file, and the mapping of tickers to names and sectors is done in the mapping.py file. 
# The plots are created in the plots.py file.
# Need to run on 

# ============================================================
# Import required libraries and functions from other files
# ============================================================

from flask import Flask, render_template, request
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go

from mapping import TICKER_DATA

from calculate import (
    download_prices_and_dividends,
    prepare_returns,
    compute_expected_returns,
    run_portfolio_simulation,
    select_mu_model,
    run_portfolio_optimisation,
    portfolio_perf,
    portfolio_daily_returns,
    sortino_ratio_ann,
    DEFAULT_ASSETS
)

from plots import (
    growth_chart,
    allocation_bar_chart,
    allocation_donut_chart,
    correlation_heatmap,
    distribution_chart
)

app = Flask(__name__)


# ============================================================
# Home page - UI interface
# ============================================================
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    form_data = {}

    if request.method == "POST":
        try:
            # -----------------------------
            # 1. Basic inputs
            # -----------------------------
            initial = float(request.form["initial"])
            if initial <= 0:
                raise ValueError("Investment must be greater than 0.")

            # Flip the risk so that the slider shows low risk = 1 and high risk = 10, but the calculation uses low risk aversion = 10 and high risk aversion = 1    
            risk_input = float(request.form["risk"])   # slider: 1 = low risk, 10 = high risk
            risk = 11.0 - risk_input                   # invert: high risk tolerance → low risk aversion

            years = float(request.form["years"])
            dividend = request.form["dividend"]
            vol_targeting = request.form.get("vol_targeting") == "on"
            vol_target = float(request.form.get("vol_target", 0.10))        

            # Ensure vol target is within reasonable bounds
            vol_target = np.clip(vol_target, 0.01, 0.50)    

            # -----------------------------
            # 2. Sector selection
            # -----------------------------
            selected_sectors = request.form.getlist("sectors")

            if not selected_sectors:
                raise ValueError("You must select at least one sector to build your portfolio.")

            allowed_assets = [
                ticker for ticker, info in TICKER_DATA.items()
                if info["sector"] in selected_sectors and ticker in DEFAULT_ASSETS
            ]
            allowed_assets = list(dict.fromkeys(allowed_assets))

            if len(allowed_assets) < 2:
                raise ValueError("Not enough assets after sector filtering.")

            # -----------------------------
            # 3. Other inputs
            # -----------------------------
            start_date = request.form.get("start_date", "2018-01-01")
            risk_free = float(request.form.get("risk_free", 0.04))
            inflation = float(request.form.get("inflation", 0.025))
            model = request.form.get("model", "blend")

            # If there are monthly contributions - then add these
            enable_contributions = request.form.get("enable_contributions") == "on"

            if enable_contributions:
                monthly_contribution = float(request.form.get("monthly_contribution", 0))
            else:
                monthly_contribution = 0.0

            # -----------------------------
            # 4. Download data
            # -----------------------------
            prices_raw, dividends_raw = download_prices_and_dividends(allowed_assets, start_date)

            # -----------------------------
            # 5. Clean + returns
            # -----------------------------
            prep = prepare_returns(prices_raw, allowed_assets)
            returns = prep["returns"]
            prices_clean = prep["prices"]

            # IMPORTANT:
            # final asset universe = assets that survived cleaning
            assets_used = list(returns.columns)

            if len(assets_used) < 2:
                raise ValueError("Too few assets after cleaning.")

            # Align dividends to cleaned prices/assets
            dividends_clean = dividends_raw.reindex_like(prices_clean).fillna(0.0)
            dividends_clean = dividends_clean[assets_used]
            prices_clean = prices_clean[assets_used]

            # -----------------------------
            # 6. Benchmark data
            # -----------------------------
            bench = yf.download(
                ["^GSPC"],
                start=start_date,
                auto_adjust=True,
                progress=False
            )

            if bench is None or bench.empty:
                raise ValueError("Failed to download S&P 500 benchmark data.")

            if isinstance(bench.columns, pd.MultiIndex):
                bench_prices = bench["Close"]["^GSPC"].dropna()
            else:
                bench_prices = bench["Close"].dropna()

            bench_rets = pd.DataFrame({"^GSPC": bench_prices.pct_change().dropna()})

            # -----------------------------
            # 7. Expected returns
            # -----------------------------
            exp = compute_expected_returns(
                returns=returns,
                bench_rets=bench_rets,
                risk_free=risk_free,
                inflation=inflation,
                capm_benchmark_name="S&P 500",
                apt_factors=3,
                apt_include_benchmark=True
            )

            mu_sel = select_mu_model(
                model=model,
                mu_mpt_s=exp["mu_mpt"],
                capm_mu_ann=exp["capm_mu"],
                apt_mu_ann=exp["apt_mu"],
                ml_mu_ann=exp["ml_mu"],
                ml_blend=0.3
            )

            # Restrict and align everything to the cleaned asset universe
            mu_sel = mu_sel.reindex(assets_used)
            cov_df = pd.DataFrame(exp["cov"], index=assets_used, columns=assets_used)

            # -----------------------------
            # 8. Optimisation
            # -----------------------------
            opt = run_portfolio_optimisation(
                mu_sel_s=mu_sel,
                cov_df=cov_df,
                config={
                    "max_weight": 0.30,
                    "long_short": False,
                    "use_sharpe_caps": False,
                    "sharpe_strength": 0.3,
                    "strategy": "MV",
                    "risk_aversion": float(risk),
                    "max_gross": 1.0
                },
                risk_free=risk_free
            )

            chosen_assets = list(opt["assets"])

            # Optimised risky-sleeve weights, aligned to chosen_assets only
            weights = pd.Series(opt["weights"], index=chosen_assets, dtype=float)
            weights = weights[weights > 1e-6]

            if weights.empty or weights.sum() <= 0:
                raise ValueError("Optimisation produced invalid portfolio weights.")

            # Re-normalise after dropping tiny numerical weights
            weights = weights / weights.sum()
            chosen_assets = list(weights.index)

            # Align all simulation inputs to chosen_assets in EXACT same order
            mu_for_sim = mu_sel.reindex(chosen_assets).values
            cov_for_sim = cov_df.loc[chosen_assets, chosen_assets].values
            prices_sim = prices_clean[chosen_assets]
            dividends_sim = dividends_clean[chosen_assets]
            weights_for_sim = weights.values

            # -----------------------------
            # 9. Risk-free allocation
            # -----------------------------
            # port_r = float(weights_for_sim @ mu_for_sim)   # From Claude
            # port_v = float(np.sqrt(max(1e-18, weights_for_sim.T @ cov_for_sim @ weights_for_sim))) # From Claude
            port_r, port_v = portfolio_perf(weights_for_sim, mu_for_sim, cov_for_sim)

            var_risky = port_v ** 2

            if var_risky > 0:
                risky_weight = np.clip(
                    (port_r - risk_free) / (float(risk) * var_risky),
                    0.0,
                    1.0
                )
            else:
                risky_weight = 1.0

            rf_weight = 1.0 - risky_weight

            # Apply volatility targeting
            if vol_targeting and vol_target > 0:
                if port_v > 0:
                    total_vol_current = risky_weight * port_v

                    if total_vol_current > 1e-12:
                        new_risky_weight = risky_weight * (vol_target / total_vol_current)
                        new_risky_weight = np.clip(new_risky_weight, 0.0, 1.0)

                        risky_weight = new_risky_weight
                        rf_weight = 1.0 - risky_weight

            # Compute the totals
            total_return = risky_weight * port_r + rf_weight * risk_free
            total_vol = risky_weight * port_v

            # Calculate the Sharpe ratio - guard against zero volatility to avoid division errors
            if total_vol > 1e-12:
                sharpe_ratio = (total_return - risk_free) / total_vol
            else:
                sharpe_ratio = 0.0

            # Calculate the Sortino ratio (downside volatility)
            r_port_daily = portfolio_daily_returns(
                returns=returns[chosen_assets],   # IMPORTANT: use same asset universe
                weights=weights_for_sim,
                rf_weight=rf_weight,
                risk_free=risk_free
            )

            sortino_ratio = sortino_ratio_ann(r_port_daily, rf_annual=risk_free)

            if not np.isfinite(sortino_ratio):
                sortino_ratio = 0.0

            # -----------------------------
            # 10. Correlation plot
            # -----------------------------
            corr_plot = correlation_heatmap(returns, chosen_assets)

            # -----------------------------
            # 11. Growth chart data
            # -----------------------------
            reinvest = (dividend == "reinvest")

            sim_data = run_portfolio_simulation(
                mu=mu_for_sim,
                cov=cov_for_sim,
                weights=weights_for_sim,
                prices=prices_sim,
                dividends=dividends_sim,
                config={
                    "rf_weight": rf_weight,
                    "years": int(years),
                    "initial": initial,
                    "contribution": monthly_contribution,
                    "contribution_freq": "Monthly",
                    "rebalance_freq": "Annual",
                    "runs": 200
                },
                risk_free=risk_free,
                reinvest=reinvest
            )
            simulations = sim_data["simulations"]
            growth_plot = growth_chart(simulations, years)

            # -----------------------------
            # 12. Monte Carlo Distribution Chart
            # -----------------------------
            dist_plot = distribution_chart(simulations)

            # -----------------------------
            # 13. Final value stats
            # -----------------------------
            final_vals = simulations[:, -1]

            median_val = np.percentile(final_vals, 50)
            p10_val = np.percentile(final_vals, 10)
            p90_val = np.percentile(final_vals, 90)

            def fmt(x):
                return f"£{int(x):,}"

            final_summary = {
                "median": fmt(median_val),
                "low": fmt(p10_val),
                "high": fmt(p90_val)
            }

            # -----------------------------
            # 14. Display weights
            # -----------------------------
            named_weights = {
                f"{TICKER_DATA[t]['name']} ({t})": float(w)
                for t, w in weights.items()
            }

            bar_chart = allocation_bar_chart(named_weights)
            donut_chart = allocation_donut_chart(named_weights, TICKER_DATA)

            # -----------------------------
            # 15. Final result
            # -----------------------------
            result = {
                "weights": named_weights,
                "return_total": round(total_return * 100, 2),   # Total portfolio return including risk-free
                "vol_total": round(total_vol * 100, 2),         # Total portfolio volatility including risk-free
                "return_risky": round(port_r * 100, 2),         # Risky sleeve return
                "vol_risky": round(port_v * 100, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "sortino_ratio": round(sortino_ratio, 2),
                "growth_plot": growth_plot,
                "bar_chart": bar_chart,
                "donut_chart": donut_chart,
                "corr_plot": corr_plot,
                "dist_plot": dist_plot,
                "final_summary": final_summary,
                "rf_weight": round(rf_weight * 100, 2),
                "risky_weight": round((1.0 - rf_weight) * 100, 2),
                "assets_used": chosen_assets
            }
            
            form_data = request.form

        except Exception as e:
            error = str(e)
            form_data = request.form


    return render_template("index.html", result=result, error=error, form=form_data)



# ============================================================
# Run app
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)
