"""
app.py
======
Footfall Dashboard — Main entry point
Run with: streamlit run app.py
"""

import streamlit as st
from tabs import past_events, future_events

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Footfall Dashboard",
    page_icon="📍",
    layout="wide",
)


def main():
    st.title("📍 Footfall Dashboard")
    st.markdown("View past events from saved data or fetch live future events.")
    st.markdown("---")

    tab_past, tab_future = st.tabs(["📂 Past Events", "🔮 Future Events"])

    with tab_past:
        past_events.render()

    with tab_future:
        future_events.render()


if __name__ == "__main__":
    main()
