"""
app.py
======
Footfall Dashboard — Simple Streamlit app
Run with: streamlit run app.py
"""

import csv
import os
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import pandas as pd
from datetime import datetime, timedelta

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Footfall Dashboard",
    page_icon="📍",
    layout="wide",
)

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


# ── Load Past Data ────────────────────────────────────────────────────────────
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


# ── Future CSV Helpers ────────────────────────────────────────────────────────
def _check_future_cache(
    lat: float,
    lon: float,
    date_from: str,
    date_to: str,
    radius_m: int,
) -> pd.DataFrame | None:
    """Check if future_events.csv has data for this lat/lon + date range + radius."""
    try:
        df = pd.read_csv(FUTURE_CSV, low_memory=False)
        df["venue_lat"] = pd.to_numeric(df["venue_lat"], errors="coerce")
        df["venue_lon"] = pd.to_numeric(df["venue_lon"], errors="coerce")
        cached = df[
            (df["shop_lat"].round(4) == round(lat, 4))
            & (df["shop_lon"].round(4) == round(lon, 4))
            & (df["query_date_from"] == date_from)
            & (df["query_date_to"] == date_to)
            & (df["query_radius_m"] == radius_m)
        ]
        return cached if not cached.empty else None
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _save_future_events(
    events: list[dict],
    lat: float,
    lon: float,
    date_from: str,
    date_to: str,
    radius_m: int,
):
    """Append future events to future_events.csv."""
    rows = []
    for event in events:
        cap = event.get("capacity", {}) or {}
        cap_range = cap.get("capacity_range", []) or []
        dist_km = event.get("distance_km")
        rows.append(
            {
                "shop_lat": round(lat, 4),
                "shop_lon": round(lon, 4),
                "query_date_from": date_from,
                "query_date_to": date_to,
                "query_radius_m": radius_m,
                "source": event.get("source", ""),
                "id": event.get("id", ""),
                "name": event.get("name", ""),
                "date": event.get("date", ""),
                "time": event.get("time", ""),
                "end_time": event.get("end_time", ""),
                "venue": event.get("venue", ""),
                "city": event.get("city", ""),
                "address": event.get("address", ""),
                "venue_lat": event.get("venue_lat", ""),
                "venue_lon": event.get("venue_lon", ""),
                "segment": event.get("segment", ""),
                "genre": event.get("genre", ""),
                "sub_genre": event.get("sub_genre", ""),
                "distance_km": dist_km,
                "distance_m": round(dist_km * 1000) if dist_km is not None else "",
                "sales_status": event.get("sales_status", ""),
                "sales_end": event.get("sales_end", ""),
                "price_min": event.get("price_min", ""),
                "price_max": event.get("price_max", ""),
                "price_currency": event.get("price_currency", ""),
                "url": event.get("url", ""),
                "recurrent_event": event.get("recurrent_event", False),
                "recurrence_type": event.get("recurrence_type", "none"),
                "venue_type": cap.get("venue_type", ""),
                "estimated_capacity": cap.get("estimated_capacity", ""),
                "capacity_range_min": cap_range[0] if len(cap_range) > 0 else "",
                "capacity_range_max": cap_range[1] if len(cap_range) > 1 else "",
                "capacity_confidence": cap.get("confidence", ""),
            }
        )

    if not rows:
        return

    file_exists = os.path.exists(FUTURE_CSV)
    with open(FUTURE_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FUTURE_CSV_COLS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


# ── Map Builder ───────────────────────────────────────────────────────────────
def build_map(
    shop_lat: float,
    shop_lon: float,
    events: pd.DataFrame,
    max_markers: int = MAX_MAP_MARKERS,
) -> folium.Map:
    """Build a Folium map with shop marker and clustered event pins."""
    m = folium.Map(location=[shop_lat, shop_lon], zoom_start=14)

    # Shop marker
    folium.Marker(
        location=[shop_lat, shop_lon],
        tooltip="🏪 Your Shop",
        popup=folium.Popup("Your Shop", max_width=200),
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(m)

    # Cluster
    cluster = MarkerCluster(
        options={"maxClusterRadius": 40, "disableClusteringAtZoom": 15}
    ).add_to(m)

    # Cap markers for performance
    events_to_plot = events.head(max_markers)
    if len(events) > max_markers:
        st.caption(
            f"⚠️ Map showing first {max_markers} of {len(events)} events for performance. "
            f"Full list available in the table below."
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

        # Capacity
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

        # Distance
        dist_m = event.get("distance_m", "")
        dist_str = (
            f"{int(dist_m)} m"
            if pd.notna(dist_m) and str(dist_m).strip() not in ("", "nan")
            else "N/A"
        )

        # Price
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
def _display_results(df_events: pd.DataFrame, lat: float, lon: float):
    """Shared map + metrics + table display for both tabs."""

    total = len(df_events)
    recurrent = (
        int(df_events["recurrent_event"].sum())
        if "recurrent_event" in df_events.columns
        else 0
    )

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Events", total)
    c2.metric("Non-Recurrent", total - recurrent)
    c3.metric("Recurrent", recurrent)
    c4.metric(
        "Unique Venues",
        df_events["venue"].nunique() if "venue" in df_events.columns else 0,
    )
    st.markdown("---")

    # Map
    st.subheader("📍 Event Map")
    m = build_map(lat, lon, df_events)
    st_folium(m, use_container_width=True, height=500)
    st.markdown(
        "🔴 Ticketmaster &nbsp;&nbsp; 🔵 OpenAgenda &nbsp;&nbsp; "
        "🟢 Google Events &nbsp;&nbsp; ⚫ Your Shop &nbsp;&nbsp; "
        "⚪ Daily Recurrent &nbsp;&nbsp; 🔘 Weekly Recurrent"
    )

    # Table
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


# ── PAST EVENTS TAB ───────────────────────────────────────────────────────────
def render_past_tab():
    """Past events tab — load from events.csv."""
    st.subheader("📂 Past Events")

    df = load_past_data()
    if df.empty:
        return

    # Shop selector
    st.markdown("**📍 Select Shop Location**")
    unique_shops = (
        df[["shop_lat", "shop_lon"]]
        .drop_duplicates()
        .sort_values(["shop_lat", "shop_lon"])
        .reset_index(drop=True)
    )
    unique_shops["label"] = unique_shops.apply(
        lambda r: f"({r['shop_lat']}, {r['shop_lon']})", axis=1
    )

    selected_label = st.selectbox(
        "Shop (lat, lon)",
        options=unique_shops["label"].tolist(),
        index=0,
    )

    selected_row = unique_shops[unique_shops["label"] == selected_label].iloc[0]
    shop_lat = selected_row["shop_lat"]
    shop_lon = selected_row["shop_lon"]

    # Filter to selected shop
    shop_df = df[(df["shop_lat"] == shop_lat) & (df["shop_lon"] == shop_lon)].copy()

    # Date range selector
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

    # Filter to selected date range
    filtered_df = shop_df[
        (shop_df["query_date_from"] == selected_from)
        & (shop_df["query_date_to"] == selected_to)
    ].copy()

    # Event date filter
    col1, col2 = st.columns(2)
    with col1:
        try:
            min_date = pd.to_datetime(selected_from).date()
            max_date = pd.to_datetime(selected_to).date()
        except Exception:
            min_date = datetime.now().date()
            max_date = (datetime.now() + timedelta(days=90)).date()
        date_from_filter = st.date_input(
            "Show events from", value=min_date, min_value=min_date, max_value=max_date
        )
    with col2:
        date_to_filter = st.date_input(
            "Show events to", value=max_date, min_value=min_date, max_value=max_date
        )

    if "date" in filtered_df.columns:
        filtered_df["date_parsed"] = pd.to_datetime(
            filtered_df["date"], errors="coerce"
        )
        filtered_df = filtered_df[
            (filtered_df["date_parsed"].dt.date >= date_from_filter)
            & (filtered_df["date_parsed"].dt.date <= date_to_filter)
        ]

    # Source filter
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

    _display_results(filtered_df, shop_lat, shop_lon)


# ── FUTURE EVENTS TAB ─────────────────────────────────────────────────────────
def render_future_tab():
    """Future events tab — fetch live from APIs with CSV caching."""
    st.subheader("🔮 Future Events")
    st.info(
        "Fetches live events from Ticketmaster and OpenAgenda. Results are cached in `future_events.csv`."
    )

    # Session state init
    if "future_df" not in st.session_state:
        st.session_state.future_df = None
    if "future_lat" not in st.session_state:
        st.session_state.future_lat = None
    if "future_lon" not in st.session_state:
        st.session_state.future_lon = None

    # Inputs
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=48.8584, format="%.6f", key="fut_lat")
        lon = st.number_input("Longitude", value=2.2945, format="%.6f", key="fut_lon")
    with col2:
        radius_m = st.slider(
            "Radius (m)",
            min_value=50,
            max_value=2000,
            value=500,
            step=50,
            key="fut_radius",
        )
        days = st.slider(
            "Days ahead", min_value=1, max_value=90, value=30, key="fut_days"
        )

    st.markdown("**📡 Sources**")
    use_tm = st.checkbox("Ticketmaster", value=True, key="fut_tm")
    use_oa = st.checkbox("OpenAgenda", value=True, key="fut_oa")
    use_go = st.checkbox("Google Events (local only)", value=False, key="fut_go")

    date_from = datetime.utcnow().strftime("%Y-%m-%d")
    date_to = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")

    if st.button("🔍 Fetch Events", use_container_width=True, key="fut_fetch"):
        # Clear previous results
        st.session_state.future_df = None
        st.session_state.future_lat = None
        st.session_state.future_lon = None

        sources = []
        if use_tm:
            sources.append("ticketmaster")
        if use_oa:
            sources.append("openagenda")
        if use_go:
            sources.append("google")

        if not sources:
            st.warning("Please select at least one source.")
        else:
            # Check CSV cache first
            cached_df = _check_future_cache(lat, lon, date_from, date_to, radius_m)
            if cached_df is not None:
                st.success(f"⚡ Loaded {len(cached_df)} events from cache.")
                st.session_state.future_df = cached_df
                st.session_state.future_lat = lat
                st.session_state.future_lon = lon
            else:
                try:
                    from footfall_explorer.core.aggregator import aggregate_events
                    from footfall_explorer.core.capacity import (
                        enrich_events_with_capacity,
                    )

                    # Fetch
                    with st.spinner("⏳ Fetching events from sources..."):
                        result = aggregate_events(
                            lat=lat,
                            lon=lon,
                            radius_m=radius_m,
                            days=days,
                            sources=sources,
                        )
                        events_list = result.get("events", [])

                    if not events_list:
                        st.warning("No events found for this location.")
                    else:
                        # Capacity enrichment
                        with st.spinner("🤖 Estimating venue capacities..."):
                            events_list = enrich_events_with_capacity(events_list)

                        # Filter out recurrent events
                        clean_events = [
                            e
                            for e in events_list
                            if not e.get("recurrent_event", False)
                        ]

                        # Filter by distance
                        radius_km_val = radius_m / 1000
                        clean_events = [
                            e
                            for e in clean_events
                            if e.get("distance_km") is None
                            or e.get("distance_km") <= radius_km_val
                        ]

                        if not clean_events:
                            st.warning(
                                "No non-recurrent events found within the selected distance and date window."
                            )
                        else:
                            # Save to CSV
                            _save_future_events(
                                clean_events, lat, lon, date_from, date_to, radius_m
                            )
                            st.success(
                                f"✅ Found {len(clean_events)} events. Saved to `future_events.csv`."
                            )

                            # Build DataFrame
                            df_events = pd.DataFrame(clean_events)

                            # Flatten capacity dict
                            if "capacity" in df_events.columns:
                                df_events["venue_type"] = df_events["capacity"].apply(
                                    lambda x: (
                                        x.get("venue_type", "")
                                        if isinstance(x, dict)
                                        else ""
                                    )
                                )
                                df_events["estimated_capacity"] = df_events[
                                    "capacity"
                                ].apply(
                                    lambda x: (
                                        x.get("estimated_capacity", "")
                                        if isinstance(x, dict)
                                        else ""
                                    )
                                )
                                df_events["capacity_range_min"] = df_events[
                                    "capacity"
                                ].apply(
                                    lambda x: (
                                        x.get("capacity_range", [None])[0]
                                        if isinstance(x, dict)
                                        and len(x.get("capacity_range", [])) > 0
                                        else ""
                                    )
                                )
                                df_events["capacity_range_max"] = df_events[
                                    "capacity"
                                ].apply(
                                    lambda x: (
                                        x.get("capacity_range", [None, None])[1]
                                        if isinstance(x, dict)
                                        and len(x.get("capacity_range", [])) > 1
                                        else ""
                                    )
                                )
                                df_events["capacity_confidence"] = df_events[
                                    "capacity"
                                ].apply(
                                    lambda x: (
                                        x.get("confidence", "")
                                        if isinstance(x, dict)
                                        else ""
                                    )
                                )

                            # Convert distance to meters
                            if (
                                "distance_km" in df_events.columns
                                and "distance_m" not in df_events.columns
                            ):
                                df_events["distance_m"] = df_events[
                                    "distance_km"
                                ].apply(
                                    lambda x: round(x * 1000) if pd.notna(x) else ""
                                )

                            # Store in session state
                            st.session_state.future_df = df_events
                            st.session_state.future_lat = lat
                            st.session_state.future_lon = lon

                except ImportError:
                    st.error(
                        "❌ The `footfall_explorer` package is not installed. "
                        "Future events only work when running locally with the full project installed."
                    )

    # Display results — outside button block so it persists across reruns
    results_placeholder = st.empty()
    if st.session_state.future_df is not None:
        with results_placeholder.container():
            _display_results(
                st.session_state.future_df,
                st.session_state.future_lat,
                st.session_state.future_lon,
            )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    st.title("📍 Footfall Dashboard")
    st.markdown("View past events from saved data or fetch live future events.")
    st.markdown("---")

    tab_past, tab_future = st.tabs(["📂 Past Events", "🔮 Future Events"])

    with tab_past:
        render_past_tab()

    with tab_future:
        render_future_tab()


if __name__ == "__main__":
    main()
