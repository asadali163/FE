"""
tabs/data_analysis.py
=====================
Sales Analysis tab — Whole / Customer / SKU level analysis.
"""

import streamlit as st
import pandas as pd
from utils import load_sell_data, get_fmc_only, load_past_data
from tabs.funcs import sku_analysis, customer_analysis


def _render_sku_analysis(sellin: pd.DataFrame, sellout: pd.DataFrame):
    """SKU Level Analysis section."""
    st.markdown("### 📦 SKU Level Analysis")

    # ── Selectors ─────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        # customers = sorted(sellout["customer_code"].unique().tolist())
        customers = (
            sellout.groupby("customer_code")["sales_quantity"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )

        customer = st.selectbox("Customer Code", customers, key="sku_customer")

    with col2:
        # Filter SKUs available for selected customer
        # skus_for_customer = sorted(
        #     sellout[sellout["customer_code"] == customer]["sku_code"].unique().tolist()
        # )

        sku_for_customers = sellout[sellout["customer_code"] == customer].copy()
        skus_for_customer = (
            sku_for_customers.groupby("sku_code")["sales_quantity"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )

        sku = st.selectbox("SKU Code", skus_for_customer, key="sku_code_select")

    if not customer or not sku:
        st.warning("Please select a customer and SKU.")
        return
    else:
        # Write lat and long for given customer as caption
        c1, c2 = st.columns(2)

        with c1:
            customer_lat = sellout[sellout["customer_code"] == customer][
                "latitude"
            ].iloc[0]
            customer_lon = sellout[sellout["customer_code"] == customer][
                "longitude"
            ].iloc[0]

            st.caption(f"Lat: {customer_lat:.6f} | Lon: {customer_lon:.6f}")
        with c2:
            # Write SKU Name.
            sku_name = sellout[sellout["sku_code"] == sku]["sku_name"].iloc[0]
            st.caption(f"Name: {sku_name}")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        take_from_first_si = st.checkbox("Take from first sell-in", value=True)

    with col2:
        percentage = st.slider(
            "Percentage",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.01,
        )

    # ── Row 1 — Stock Remaining ──────────────────────────

    fig11 = sku_analysis.fig_stock_remaining(
        sellin.copy(),
        sellout.copy(),
        customer,
        sku,
        percentage=percentage,
        take_from_first_si=take_from_first_si,
    )
    st.plotly_chart(fig11, use_container_width=True)

    fig2 = sku_analysis.fig_weekly(sellin, sellout, customer, sku, take_from_first_si)
    fig3 = sku_analysis.fig_monthly(sellin, sellout, customer, sku, take_from_first_si)

    # ── Row 2 — Weekly + Monthly side by side ─────────────
    col_left, col_right = st.columns(2)
    with col_left:
        st.plotly_chart(fig2, use_container_width=True)
    with col_right:
        st.plotly_chart(fig3, use_container_width=True)


def _render_whole_analysis(sellin: pd.DataFrame, sellout: pd.DataFrame):
    """Whole Analysis section — placeholder for now."""
    st.markdown("### 🌍 Whole Analysis")
    st.info("Coming soon — you can define whole-level analysis functions here.")


def _render_customer_analysis(
    sellin: pd.DataFrame, sellout: pd.DataFrame, events: pd.DataFrame
):
    """Customer Level Analysis section — placeholder for now."""
    st.markdown("### 👤 Customer Level Analysis")
    # st.info("Coming soon — you can define customer-level analysis functions here.")
    sellin = get_fmc_only(sellin)
    sellout = get_fmc_only(sellout)

    customers_all = (
        sellout.groupby("customer_code")["sales_quantity"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )

    col1, col2 = st.columns(2)

    with col1:
        customer = st.selectbox("Customer Code", customers_all, key="customer_code")

    threshold = 1.5

    selected_customers = [
        "0011t000011b2KEAAY",
        "0011t000011b4TNAAY",
        "0011t000011b2XFAAY",
        "0011t000011bAopAAE",
        "0011t000011b5rGAAQ",
    ]
    with col2:
        customer = st.selectbox(
            "Spiked Customer Code", selected_customers, key="customer_code_selected"
        )
    # with col2:
    #     threshold = st.slider(
    #         "Threshold",
    #         min_value=0.0,
    #         max_value=5.0,
    #         value=2.0,
    #         step=0.5,
    #     )

    # Write caption with sellout_selected lat and long.
    customer_lat = sellout[sellout["customer_code"] == customer]["latitude"].iloc[0]
    customer_lon = sellout[sellout["customer_code"] == customer]["longitude"].iloc[0]

    st.session_state["selected_shop_lat"] = customer_lat
    st.session_state["selected_shop_lon"] = customer_lon

    st.caption(f"({customer_lat:.6f}, {customer_lon:.6f})")

    df_selected_sellin = sellin[sellin["customer_code"] == customer].copy()
    df_selected_sellout = sellout[sellout["customer_code"] == customer].copy()

    # Group by date
    df_selected_sellin = df_selected_sellin.groupby("date")["sales_quantity"].sum()

    # Create full date range
    full_range = pd.date_range(
        start=df_selected_sellin.index.min(),
        end=df_selected_sellin.index.max(),
        freq="D",
    )

    # Reindex and fill missing dates with 0
    df_selected_sellin = (
        df_selected_sellin.reindex(full_range, fill_value=0)
        .rename_axis("date")
        .reset_index()
    )

    df_selected = customer_analysis.process_customer(
        df_selected_sellout, events, threshold
    )

    # Plot the customer.
    fig = customer_analysis.plot_customer(df_selected, df_selected_sellin)

    st.plotly_chart(fig, use_container_width=True)


def render():
    """Render the Sales Analysis tab."""
    st.subheader("📊 Sales Analysis")

    # ── Load data ─────────────────────────────────────────
    sellin, sellout = load_sell_data()

    df_events = load_past_data()

    print(sellin.shape, sellout.shape)

    if sellin.empty or sellout.empty:
        st.error(
            "❌ Sell-in or sell-out data could not be loaded. Check your CSV files."
        )
        return

    st.caption(
        f"Sell-in: **{len(sellin):,}** rows | "
        f"Sell-out: **{len(sellout):,}** rows | "
        f"Customers: **{sellin['customer_code'].nunique()}** | "
        f"SKUs: **{sellin['sku_code'].nunique()}**"
    )
    st.markdown("---")

    # ── Analysis level buttons ────────────────────────────
    if "analysis_level" not in st.session_state:
        st.session_state.analysis_level = None

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🌍 Whole Analysis", use_container_width=True, key="btn_whole"):
            st.session_state.analysis_level = "whole"
    with col2:
        if st.button("👤 Customer Level", use_container_width=True, key="btn_customer"):
            st.session_state.analysis_level = "customer"
    with col3:
        if st.button("📦 SKU Level", use_container_width=True, key="btn_sku"):
            st.session_state.analysis_level = "sku"

    st.markdown("---")

    # ── Render selected section ───────────────────────────
    level = st.session_state.analysis_level

    if level is None:
        st.info("👆 Select an analysis level above to get started.")
    elif level == "whole":
        _render_whole_analysis(sellin, sellout)
    elif level == "customer":
        _render_customer_analysis(sellin, sellout, df_events)
    elif level == "sku":
        _render_sku_analysis(sellin, sellout)
