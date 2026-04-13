"""
tabs/future_events.py
=====================
Future Events tab — fetches live from APIs with CSV caching
"""

import csv
import os
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils import display_results, FUTURE_CSV, FUTURE_CSV_COLS


# ── Cache Helpers ─────────────────────────────────────────────────────────────
def _check_future_cache(
    lat: float,
    lon: float,
    date_from: str,
    date_to: str,
    radius_m: int,
) -> pd.DataFrame | None:
    """Check if future_events.csv has data for this query."""
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


def _flatten_capacity(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten capacity dict column into separate flat columns."""
    if "capacity" not in df.columns:
        return df
    df["venue_type"] = df["capacity"].apply(
        lambda x: x.get("venue_type", "") if isinstance(x, dict) else ""
    )
    df["estimated_capacity"] = df["capacity"].apply(
        lambda x: x.get("estimated_capacity", "") if isinstance(x, dict) else ""
    )
    df["capacity_range_min"] = df["capacity"].apply(
        lambda x: (
            x.get("capacity_range", [None])[0]
            if isinstance(x, dict) and len(x.get("capacity_range", [])) > 0
            else ""
        )
    )
    df["capacity_range_max"] = df["capacity"].apply(
        lambda x: (
            x.get("capacity_range", [None, None])[1]
            if isinstance(x, dict) and len(x.get("capacity_range", [])) > 1
            else ""
        )
    )
    df["capacity_confidence"] = df["capacity"].apply(
        lambda x: x.get("confidence", "") if isinstance(x, dict) else ""
    )
    return df


# ── Main Render ───────────────────────────────────────────────────────────────
def render():
    """Render the Future Events tab."""
    st.subheader("🔮 Future Events")
    st.info("Fetches live events from APIs. Results cached in `future_events.csv`.")

    # Session state init
    for key in ["future_df", "future_lat", "future_lon"]:
        if key not in st.session_state:
            st.session_state[key] = None

    # ── Inputs ────────────────────────────────────────────
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
            # ── Check cache ───────────────────────────────
            cached_df = _check_future_cache(lat, lon, date_from, date_to, radius_m)
            if cached_df is not None:
                st.success(f"⚡ Loaded {len(cached_df)} events from cache.")
                st.session_state.future_df = cached_df
                st.session_state.future_lat = lat
                st.session_state.future_lon = lon
            else:
                # ── Fresh fetch ───────────────────────────
                try:
                    from footfall_explorer.core.aggregator import aggregate_events
                    from footfall_explorer.core.capacity import (
                        enrich_events_with_capacity,
                    )

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
                        with st.spinner("🤖 Estimating venue capacities..."):
                            events_list = enrich_events_with_capacity(events_list)

                        # Filter recurrent + distance
                        radius_km_val = radius_m / 1000
                        clean_events = [
                            e
                            for e in events_list
                            if not e.get("recurrent_event", False)
                            and (
                                e.get("distance_km") is None
                                or e.get("distance_km") <= radius_km_val
                            )
                        ]

                        if not clean_events:
                            st.warning(
                                "No non-recurrent events found within the selected distance and date window."
                            )
                        else:
                            _save_future_events(
                                clean_events, lat, lon, date_from, date_to, radius_m
                            )
                            st.success(
                                f"✅ Found {len(clean_events)} events. Saved to `future_events.csv`."
                            )

                            df_events = pd.DataFrame(clean_events)
                            df_events = _flatten_capacity(df_events)

                            if (
                                "distance_km" in df_events.columns
                                and "distance_m" not in df_events.columns
                            ):
                                df_events["distance_m"] = df_events[
                                    "distance_km"
                                ].apply(
                                    lambda x: round(x * 1000) if pd.notna(x) else ""
                                )

                            st.session_state.future_df = df_events
                            st.session_state.future_lat = lat
                            st.session_state.future_lon = lon

                except ImportError:
                    st.error(
                        "❌ The `footfall_explorer` package is not installed. "
                        "Future events only work when running locally with the full project installed."
                    )

    # ── Display — outside button block so it persists ─────
    results_placeholder = st.empty()
    if st.session_state.future_df is not None:
        with results_placeholder.container():
            display_results(
                st.session_state.future_df,
                st.session_state.future_lat,
                st.session_state.future_lon,
            )
