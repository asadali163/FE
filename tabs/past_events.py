"""
tabs/past_events.py
===================
Past Events tab — loads from events.csv
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils import load_past_data, display_results


default_lat = st.session_state.get("selected_shop_lat")
default_lon = st.session_state.get("selected_shop_lon")


def render():
    """Render the Past Events tab."""
    st.subheader("📂 Past Events")

    df = load_past_data()
    if df.empty:
        return

    # ── Shop selector ─────────────────────────────────────
    st.markdown("**📍 Select Shop Location**")
    unique_shops = (
        df[["shop_lat", "shop_lon"]]
        .drop_duplicates()
        .sort_values(["shop_lat", "shop_lon"])
        .reset_index(drop=True)
    )
    unique_shops["label"] = unique_shops.apply(
        lambda r: f"({r['shop_lat']:.6f}, {r['shop_lon']:.6f})", axis=1
    )

    selected_label = st.selectbox(
        "Shop (lat, lon)",
        options=unique_shops["label"].tolist(),
        index=0,
    )

    # Filter to selected shop
    # shop_df = df[(df["shop_lat"] == shop_lat) & (df["shop_lon"] == shop_lon)].copy()

    # Find default index from session state
    # default_index = 0

    # if default_lat is not None and default_lon is not None:
    #     match = unique_shops[
    #         (np.isclose(unique_shops["shop_lat"], default_lat))
    #         & (np.isclose(unique_shops["shop_lon"], default_lon))
    #     ]
    #     if not match.empty:
    #         default_index = match.index[0]

    # selected_label = st.selectbox(
    #     "Shop (lat, lon)",
    #     options=unique_shops["label"].tolist(),
    #     index=default_index,
    # )

    selected_row = unique_shops[unique_shops["label"] == selected_label].iloc[0]
    shop_lat = selected_row["shop_lat"]
    shop_lon = selected_row["shop_lon"]

    # Filter to selected shop
    shop_df = df[(df["shop_lat"] == shop_lat) & (df["shop_lon"] == shop_lon)].copy()

    # ── Date range selector ───────────────────────────────
    st.markdown("**📅 Select Date Range**")
    date_ranges = (
        shop_df[["query_date_from", "query_date_to"]]
        .drop_duplicates()
        .sort_values("query_date_from")
    )
    date_range_labels = date_ranges.apply(
        lambda r: f"{r['query_date_from']} → {r['query_date_to']}", axis=1
    ).tolist()

    selected_range = st.selectbox("Date Range", options=date_range_labels, index=0)
    selected_from, selected_to = selected_range.split(" → ")

    filtered_df = shop_df[
        (shop_df["query_date_from"] == selected_from)
        & (shop_df["query_date_to"] == selected_to)
    ].copy()

    # ── Event date filter ─────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        try:
            min_date = pd.to_datetime(selected_from).date()
            max_date = pd.to_datetime(selected_to).date()
        except Exception:
            min_date = datetime.now().date()
            max_date = (datetime.now() + timedelta(days=90)).date()
        date_from_filter = st.date_input(
            "Show events from",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
        )
    with col2:
        date_to_filter = st.date_input(
            "Show events to",
            value=max_date,
            min_value=min_date,
            max_value=max_date,
        )

    if "date" in filtered_df.columns:
        filtered_df["date_parsed"] = pd.to_datetime(
            filtered_df["date"], errors="coerce"
        )
        filtered_df = filtered_df[
            (filtered_df["date_parsed"].dt.date >= date_from_filter)
            & (filtered_df["date_parsed"].dt.date <= date_to_filter)
        ]

    # ── Source filter ─────────────────────────────────────
    st.markdown("**📡 Filter by Source**")
    all_sources = sorted(filtered_df["source"].dropna().unique().tolist())
    sel_sources = st.multiselect("Source", all_sources, default=all_sources)
    filtered_df = filtered_df[filtered_df["source"].isin(sel_sources)]

    st.caption(
        f"Showing **{len(filtered_df)}** events for shop at ({shop_lat}, {shop_lon})"
    )
    st.markdown("---")

    if filtered_df.empty:
        st.warning("No events found for the selected filters.")
        return

    display_results(filtered_df, shop_lat, shop_lon)
