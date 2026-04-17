"""
tabs/funcs/sku_analysis.py
==========================
SKU-level analysis functions for the Sales Analysis tab.
All functions return Plotly figures — rendering is done in data_analysis.py.
"""

import pandas as pd
import plotly.graph_objects as go


def fig_stock_remaining(
    sellin, sellout, customer_code, sku_code, percentage, take_from_first_si=False
):

    print(f"customer_code: {customer_code}, sku_code: {sku_code}")

    # -----------------------------
    # Filter customer data
    # -----------------------------
    df_sellin = sellin[(sellin["customer_code"] == customer_code)].copy()
    df_sellout = sellout[(sellout["customer_code"] == customer_code)].copy()

    # -----------------------------
    # Optional: start from first valid sell-in date
    # -----------------------------
    if take_from_first_si:
        si_filtered = df_sellin[
            (df_sellin["sku_code"] == sku_code) & (df_sellin["sales_quantity"] > 0)
        ]

        if not si_filtered.empty:
            first_si_date = si_filtered["date"].min()

            df_sellin = df_sellin[df_sellin["date"] >= first_si_date].copy()
            df_sellout = df_sellout[df_sellout["date"] >= first_si_date].copy()

    # -----------------------------
    # Filter SKU
    # -----------------------------
    temp_sellout = df_sellout[df_sellout["sku_code"] == sku_code][
        ["date", "sales_quantity"]
    ].copy()

    temp_sellin = (
        df_sellin[df_sellin["sku_code"] == sku_code][["date", "sales_quantity"]]
        .copy()
        .rename(columns={"sales_quantity": "sales_quantity_sellin"})
    )

    # -----------------------------
    # Aggregate by date
    # -----------------------------
    temp_sellout = temp_sellout.groupby("date")["sales_quantity"].sum()
    temp_sellin = temp_sellin.groupby("date")["sales_quantity_sellin"].sum()

    # -----------------------------
    # Merge
    # -----------------------------
    final_temp = pd.merge(temp_sellout, temp_sellin, on="date", how="outer")
    final_temp.fillna(0, inplace=True)

    # -----------------------------
    # Sort BEFORE logic
    # -----------------------------
    final_temp = final_temp.sort_index()

    # -----------------------------
    # 🔥 ADD INITIAL STOCK LOGIC
    # -----------------------------
    # Find first fulfillment (sell-in > 0)
    first_si_idx = final_temp[final_temp["sales_quantity_sellin"] > 0].index

    if len(first_si_idx) > 0:
        first_date = first_si_idx[0]
        first_value = final_temp.loc[first_date, "sales_quantity_sellin"]

        extra_stock = percentage * first_value

        # Add to first fulfillment
        final_temp.loc[first_date, "sales_quantity_sellin"] += extra_stock

    # -----------------------------
    # Stock remaining (cumulative)
    # -----------------------------
    final_temp["so_stock_remaining"] = (
        final_temp["sales_quantity_sellin"] - final_temp["sales_quantity"]
    ).cumsum()

    final_temp = final_temp.reset_index()

    # -----------------------------
    # Plot
    # -----------------------------
    x = final_temp["date"]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=final_temp["sales_quantity_sellin"],
            name="Sell-in",
            mode="lines+markers",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=final_temp["sales_quantity"],
            name="Sell-out",
            mode="lines+markers",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=final_temp["so_stock_remaining"],
            name="Stock Remaining",
            mode="lines+markers",
            line=dict(color="black", width=2),
        )
    )

    fig.update_layout(
        title="Sell-in vs Sell-out + Stock Remaining",
        xaxis_title="Date",
        yaxis_title="Quantity",
        template="plotly_white",
        width=1000,
        height=500,
    )

    return fig


import pandas as pd
import plotly.graph_objects as go


def fig_weekly(
    df_sellin: pd.DataFrame,
    df_sellout: pd.DataFrame,
    customer_code: str,
    sku_code: str,
    take_from_first_si: bool = False,
) -> go.Figure:
    """
    Row 2 Left — Weekly sell-in vs sell-out bar chart.
    """

    # -----------------------------
    # Filter customer + SKU
    # -----------------------------
    si = df_sellin[
        (df_sellin["customer_code"] == customer_code)
        & (df_sellin["sku_code"] == sku_code)
    ].copy()

    so = df_sellout[
        (df_sellout["customer_code"] == customer_code)
        & (df_sellout["sku_code"] == sku_code)
    ].copy()

    # Ensure datetime
    si["date"] = pd.to_datetime(si["date"])
    so["date"] = pd.to_datetime(so["date"])

    # -----------------------------
    # Optional: start from first valid sell-in date
    # -----------------------------
    if take_from_first_si:
        si_valid = si[si["sales_quantity"] > 0]

        if not si_valid.empty:
            first_si_date = si_valid["date"].min()

            si = si[si["date"] >= first_si_date]
            so = so[so["date"] >= first_si_date]

    # -----------------------------
    # Set index for resampling
    # -----------------------------
    si = si.set_index("date").sort_index()
    so = so.set_index("date").sort_index()

    # -----------------------------
    # Handle empty cases safely
    # -----------------------------
    if si.empty and so.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available.")
        return fig

    # -----------------------------
    # Weekly aggregation
    # -----------------------------
    weekly_si = (
        si["sales_quantity"].resample("W").sum()
        if not si.empty
        else pd.Series(dtype=float)
    )

    weekly_so = (
        so["sales_quantity"].resample("W").sum()
        if not so.empty
        else pd.Series(dtype=float)
    )

    # -----------------------------
    # Plot
    # -----------------------------
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=weekly_si.index,
            y=weekly_si.values,
            name="Sell-in",
        )
    )

    fig.add_trace(
        go.Bar(
            x=weekly_so.index,
            y=weekly_so.values,
            name="Sell-out",
        )
    )

    fig.update_layout(
        title="Weekly Sell-in vs Sell-out",
        xaxis_title="Week",
        yaxis_title="Quantity",
        barmode="group",
        template="plotly_white",
        height=380,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    return fig


def fig_monthly(
    df_sellin: pd.DataFrame,
    df_sellout: pd.DataFrame,
    customer_code: str,
    sku_code: str,
    take_from_first_si: bool = False,
) -> go.Figure:
    """
    Row 2 Right — Monthly sell-in vs sell-out bar chart.
    """

    # -----------------------------
    # Filter data
    # -----------------------------
    si = df_sellin[
        (df_sellin["customer_code"] == customer_code)
        & (df_sellin["sku_code"] == sku_code)
    ].copy()

    so = df_sellout[
        (df_sellout["customer_code"] == customer_code)
        & (df_sellout["sku_code"] == sku_code)
    ].copy()

    # Ensure datetime
    si["date"] = pd.to_datetime(si["date"])
    so["date"] = pd.to_datetime(so["date"])

    # -----------------------------
    # Optional: start from first sell-in date
    # -----------------------------
    if take_from_first_si:
        si_valid = si[si["sales_quantity"] > 0]

        if not si_valid.empty:
            first_si_date = si_valid["date"].min()

            si = si[si["date"] >= first_si_date]
            so = so[so["date"] >= first_si_date]

    # -----------------------------
    # Safety: set index + sort
    # -----------------------------
    si = si.set_index("date").sort_index()
    so = so.set_index("date").sort_index()

    # -----------------------------
    # Handle empty case
    # -----------------------------
    if si.empty and so.empty:
        fig = go.Figure()
        fig.update_layout(title="No data available.")
        return fig

    # -----------------------------
    # Monthly aggregation
    # -----------------------------
    monthly_si = (
        si["sales_quantity"].resample("M").sum()
        if not si.empty
        else pd.Series(dtype=float)
    )

    monthly_so = (
        so["sales_quantity"].resample("M").sum()
        if not so.empty
        else pd.Series(dtype=float)
    )

    # -----------------------------
    # Align months properly
    # -----------------------------
    all_months = monthly_si.index.union(monthly_so.index).sort_values()

    monthly_si = monthly_si.reindex(all_months, fill_value=0)
    monthly_so = monthly_so.reindex(all_months, fill_value=0)

    month_labels = all_months.strftime("%b-%Y")

    # -----------------------------
    # Plot
    # -----------------------------
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=month_labels,
            y=monthly_si.values,
            name="Sell-in",
        )
    )

    fig.add_trace(
        go.Bar(
            x=month_labels,
            y=monthly_so.values,
            name="Sell-out",
        )
    )

    fig.update_layout(
        title="Monthly Sell-in vs Sell-out",
        xaxis_title="Month",
        yaxis_title="Quantity",
        barmode="group",
        template="plotly_white",
        height=380,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    return fig
