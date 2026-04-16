"""
app.py
======
Footfall Dashboard — Main entry point
Run with: streamlit run app.py
"""

import streamlit as st
from tabs import past_events, future_events, data_analysis

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

    tab_past, tab_future, tab_sales = st.tabs(
        ["📂 Past Events", "🔮 Future Events", "Data Analysis"]
    )

    with tab_past:
        past_events.render()

    with tab_future:
        future_events.render()

    with tab_sales:
        data_analysis.render()


if __name__ == "__main__":
    main()
