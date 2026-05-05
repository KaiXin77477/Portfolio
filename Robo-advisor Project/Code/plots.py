# This file contains all the graphics for the results section
import numpy as np
import plotly.graph_objects as go

def growth_chart(simulations, years):

    steps = simulations.shape[1]
    x = np.arange(steps)

    # Median + percentiles
    median = np.percentile(simulations, 50, axis=0)
    p10 = np.percentile(simulations, 10, axis=0)
    p90 = np.percentile(simulations, 90, axis=0)

    fig = go.Figure()

    # ---------- RANGE (uncertainty band) ----------
    fig.add_trace(go.Scatter(
        x=x,
        y=p90,
        mode='lines',
        marker=dict(size=0),   # FORCE no markers
           line=dict(color='black', width=1),
        name="Upper bound (90th percentile)",
        showlegend=False
    ))
    # ---------- LOWER BOUND + FILL ----------
    fig.add_trace(go.Scatter(
        x=x,
        y=p10,
        mode='lines',
        fill='tonexty',
        fillcolor='rgba(173,216,230,0.45)',  
        marker=dict(size=0),   # FORCE no markers
        line=dict(color='black', width=1),    
        name="Range (10–90%)"
    ))

    # ---------- MEDIAN LINE ----------
    fig.add_trace(go.Scatter(
        x=x,
        y=median,
        mode='lines',
        line=dict(color='#001f3f', width=3),  # 💡 dark navy
        name="Expected growth"
    ))

    # ---------- AXIS LABELS ----------
    if years <= 1:
        # Show months
        x_vals = np.arange(steps)
        fig.update_xaxes(
            title="Months",
            tickmode='auto'
        )
    else:
    # Convert months → years
        x_vals = np.arange(steps) / 12

        fig.update_traces(x=x_vals)

        fig.update_xaxes(
            title="Years",
            tickmode='auto'
        )
    for trace in fig.data:
        trace.x = x_vals

    fig.update_yaxes(title="Portfolio Value (£)")

    # ---------- AXIS LINES ----------
    fig.update_layout(
        template="simple_white",
        xaxis=dict(
            showline=True,
            linecolor='black',
            linewidth=1
        ),
        yaxis=dict(
            showline=True,
            linecolor='black',
            linewidth=1
        ),
        margin=dict(l=40, r=20, t=40, b=40)
    )

    return fig.to_html(full_html=False)

# ----- Allocation Bar Chart -----
def allocation_bar_chart(weights_dict):
    import plotly.graph_objects as go

    # Sort descending
    items = sorted(weights_dict.items(), key=lambda x: x[1], reverse=True)

    # Short labels (tickers only)
    labels = [k.split("(")[-1].replace(")", "") for k, v in items]
    values = [v * 100 for k, v in items]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels,
        y=values,
        marker_color='#0074D9',
        width=0.5
    ))

    fig.update_layout(
        title="Allocation by Ticker",
        template="simple_white",
        
        bargap=0.15,        
        bargroupgap=0.05,

        xaxis=dict(
            tickangle=45,
            showline=True,
            linecolor="black"
        ),
        yaxis=dict(
            showline=True,
            linecolor="black"
        ),

        # 🔧 increase chart width
        width=700,          
        height=400,

        margin=dict(l=40, r=20, t=40, b=100)
    )

    return fig.to_html(full_html=False)


# ---- Donut chart for category mix -----
def allocation_donut_chart(weights_dict, ticker_data):
    import plotly.graph_objects as go

    sector_totals = {}

    for label, weight in weights_dict.items():
        # label format: "Apple (AAPL)"
        ticker = label.split("(")[-1].replace(")", "")

        sector = ticker_data[ticker]["sector"]

        sector_totals[sector] = sector_totals.get(sector, 0) + weight

    labels = list(sector_totals.keys())
    values = [v * 100 for v in sector_totals.values()]

    fig = go.Figure()

    fig.add_trace(go.Pie(
        labels=labels,
        values=values,
        hole=0.5,
        textinfo='percent',
        hoverinfo='label+percent'
    ))

    fig.update_layout(
        title="Sector Allocation",
        template="simple_white",
        showlegend=True
    )

    return fig.to_html(full_html=False)


# ----- Correlation heatmap -----
def correlation_heatmap(returns, selected_assets):

    # Filter to selected assets only
    data = returns[selected_assets]

    # Compute correlation matrix
    corr = data.corr()

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.columns,
        colorscale="RdBu",
        zmin=-1,
        zmax=1,
        colorbar=dict(title="Correlation")
    ))

    fig.update_layout(
        title="Correlation Heatmap",
        template="simple_white",
        width=700,
        height=600,
        xaxis=dict(tickangle=45),
        margin=dict(l=60, r=20, t=50, b=100)
    )

    return fig.to_html(full_html=False)


    # ----- Distribution of final portfolio values -----
def distribution_chart(simulations):
    import plotly.graph_objects as go
    import numpy as np

    final_vals = simulations[:, -1]

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=final_vals,
        nbinsx=38,
        name="Final portfolio values"
    ))

    fig.update_layout(
        title="Distribution of Final Portfolio Values",
        xaxis_title="Portfolio Value (£)",
        yaxis_title="Frequency",
        width=800,
        height=600,
        template="simple_white"
    )

    return fig.to_html(full_html=False)
