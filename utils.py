"""
utils.py
========
Shared constants, data loaders, and map/display helpers
used across all tabs.
"""

import csv
import os
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import pandas as pd

# ── Constants ─────────────────────────────────────────────────────────────────
EVENTS_CSV = "events.csv"
FUTURE_CSV = "future_events.csv"
MAX_MAP_MARKERS = 200

SOURCE_COLORS = {
    "Ticketmaster": "red",
    "OpenAgenda": "blue",
    "Google Events": "green",
}

RECURRENCE_COLORS = {
    "daily": "gray",
    "weekly": "lightgray",
    "none": None,
}

FUTURE_CSV_COLS = [
    "shop_lat",
    "shop_lon",
    "query_date_from",
    "query_date_to",
    "query_radius_m",
    "source",
    "id",
    "name",
    "date",
    "time",
    "end_time",
    "venue",
    "city",
    "address",
    "venue_lat",
    "venue_lon",
    "segment",
    "genre",
    "sub_genre",
    "distance_km",
    "distance_m",
    "sales_status",
    "sales_end",
    "price_min",
    "price_max",
    "price_currency",
    "url",
    "recurrent_event",
    "recurrence_type",
    "venue_type",
    "estimated_capacity",
    "capacity_range_min",
    "capacity_range_max",
    "capacity_confidence",
]


# ── Data Loader ───────────────────────────────────────────────────────────────
@st.cache_data
def load_past_data() -> pd.DataFrame:
    """Load and cache the past events CSV."""
    try:
        df = pd.read_csv(EVENTS_CSV, low_memory=False)
        df["shop_lat"] = pd.to_numeric(df["shop_lat"], errors="coerce")
        df["shop_lon"] = pd.to_numeric(df["shop_lon"], errors="coerce")
        df["venue_lat"] = pd.to_numeric(df["venue_lat"], errors="coerce")
        df["venue_lon"] = pd.to_numeric(df["venue_lon"], errors="coerce")
        df = df.dropna(subset=["shop_lat", "shop_lon"])
        return df
    except FileNotFoundError:
        st.error(
            f"❌ Could not find `{EVENTS_CSV}`. Make sure it is in the same folder as `app.py`."
        )
        return pd.DataFrame()


# ── Map Builder ───────────────────────────────────────────────────────────────
def build_map(
    shop_lat: float,
    shop_lon: float,
    events: pd.DataFrame,
    max_markers: int = MAX_MAP_MARKERS,
) -> folium.Map:
    """Build a Folium map with shop marker and clustered event pins."""
    m = folium.Map(location=[shop_lat, shop_lon], zoom_start=14)

    folium.Marker(
        location=[shop_lat, shop_lon],
        tooltip="🏪 Your Shop",
        popup=folium.Popup("Your Shop", max_width=200),
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(m)

    cluster = MarkerCluster(
        options={"maxClusterRadius": 40, "disableClusteringAtZoom": 15}
    ).add_to(m)

    events_to_plot = events.head(max_markers)
    if len(events) > max_markers:
        st.caption(
            f"⚠️ Map showing first {max_markers} of {len(events)} events for performance. "
            f"Full list in the table below."
        )

    for _, event in events_to_plot.iterrows():
        v_lat = event.get("venue_lat")
        v_lon = event.get("venue_lon")
        if pd.isna(v_lat) or pd.isna(v_lon):
            continue

        source = event.get("source", "Unknown")
        recurrence = str(event.get("recurrence_type", "none")).lower()
        color = RECURRENCE_COLORS.get(recurrence) or SOURCE_COLORS.get(source, "gray")
        icon_name = (
            "refresh"
            if recurrence == "daily"
            else "calendar" if recurrence == "weekly" else "music"
        )

        cap_est = event.get("estimated_capacity", "")
        cap_min = event.get("capacity_range_min", "")
        cap_max = event.get("capacity_range_max", "")
        cap_conf = event.get("capacity_confidence", "N/A")

        try:
            cap_est_str = (
                f"{int(float(cap_est)):,}"
                if pd.notna(cap_est) and str(cap_est).strip() not in ("", "N/A", "nan")
                else "N/A"
            )
        except (ValueError, TypeError):
            cap_est_str = "N/A"

        try:
            cap_range_str = (
                f"{int(float(cap_min)):,} – {int(float(cap_max)):,}"
                if pd.notna(cap_min) and str(cap_min).strip() not in ("", "N/A", "nan")
                else "N/A"
            )
        except (ValueError, TypeError):
            cap_range_str = "N/A"

        dist_m = event.get("distance_m", "")
        dist_str = (
            f"{int(dist_m)} m"
            if pd.notna(dist_m) and str(dist_m).strip() not in ("", "nan")
            else "N/A"
        )

        price_min = event.get("price_min", "")
        price_max = event.get("price_max", "")
        currency = event.get("price_currency", "")
        price_str = (
            f"{price_min} – {price_max} {currency}"
            if pd.notna(price_min) and str(price_min).strip() not in ("", "nan")
            else "N/A"
        )

        recurrent_label = (
            "Daily 📆"
            if recurrence == "daily"
            else "Weekly 🗓️" if recurrence == "weekly" else "No"
        )

        event_url = event.get("url", "")
        url_html = (
            f"<a href='{event_url}' target='_blank'>🎟️ View Event</a>"
            if pd.notna(event_url) and str(event_url).strip() not in ("", "nan")
            else ""
        )

        popup_html = f"""
        <div style="font-family: Arial; min-width: 240px; font-size: 13px;">
            <h4 style="margin:0 0 8px 0; color:#333;">{event.get('name', 'Unknown')}</h4>
            <b>📅 Date:</b> {event.get('date', 'N/A')} {event.get('time', '')}<br>
            <b>🏟️ Venue:</b> {event.get('venue', 'N/A')}<br>
            <b>🏙️ City:</b> {event.get('city', 'N/A')}<br>
            <b>🎭 Segment:</b> {event.get('segment', 'N/A')} → {event.get('genre', '')}<br>
            <b>📏 Distance:</b> {dist_str}<br>
            <b>💰 Price:</b> {price_str}<br>
            <b>📡 Source:</b> {source}<br>
            <b>🔁 Recurrent:</b> {recurrent_label}<br>
            <hr style="margin:6px 0;">
            <b>🏛️ Venue Type:</b> {event.get('venue_type', 'N/A')}<br>
            <b>👥 Est. Capacity:</b> {cap_est_str}<br>
            <b>📊 Capacity Range:</b> {cap_range_str}<br>
            <b>🎯 Confidence:</b> {cap_conf}<br>
            {url_html}
        </div>
        """

        folium.Marker(
            location=[v_lat, v_lon],
            tooltip=f"{'🔄 ' if recurrence != 'none' else ''}{event.get('name', 'Event')} — {event.get('date', '')}",
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color=color, icon=icon_name, prefix="fa"),
        ).add_to(cluster)

    return m


# ── Shared Display ────────────────────────────────────────────────────────────
def display_results(df_events: pd.DataFrame, lat: float, lon: float):
    """Shared map + metrics + table display used by all tabs."""
    total = len(df_events)
    recurrent = (
        int(df_events["recurrent_event"].sum())
        if "recurrent_event" in df_events.columns
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Events", total)
    c2.metric("Non-Recurrent", total - recurrent)
    c3.metric("Recurrent", recurrent)
    c4.metric(
        "Unique Venues",
        df_events["venue"].nunique() if "venue" in df_events.columns else 0,
    )
    st.markdown("---")

    st.subheader("📍 Event Map")
    m = build_map(lat, lon, df_events)
    st_folium(m, use_container_width=True, height=500)
    st.markdown(
        "🔴 Ticketmaster &nbsp;&nbsp; 🔵 OpenAgenda &nbsp;&nbsp; "
        "🟢 Google Events &nbsp;&nbsp; ⚫ Your Shop &nbsp;&nbsp; "
        "⚪ Daily Recurrent &nbsp;&nbsp; 🔘 Weekly Recurrent"
    )

    st.markdown("---")
    st.subheader("📊 Event Table")
    display_cols = [
        "source",
        "name",
        "date",
        "time",
        "venue",
        "city",
        "segment",
        "genre",
        "distance_m",
        "recurrent_event",
        "recurrence_type",
        "venue_type",
        "estimated_capacity",
        "capacity_range_min",
        "capacity_range_max",
        "capacity_confidence",
        "price_min",
        "price_max",
        "price_currency",
        "url",
    ]
    display_cols = [c for c in display_cols if c in df_events.columns]
    st.dataframe(df_events[display_cols], use_container_width=True)
