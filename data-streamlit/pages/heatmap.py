import pandas as pd
import streamlit as st

from scout import (
    load_event_data, load_team_data, get_event_key, get_secret_key,
    BINARY_COLS, SKIP_COLS, SECTIONS, pretty_name,
)


def heatmap_page():
    """Event Heatmap — teams vs attributes, color-coded by percentile."""
    sk = get_secret_key()
    ek = get_event_key()

    if sk is None or ek is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    st.header("Event Heatmap")
    with st.expander("Instructions"):
        st.write("""
        Every team and every attribute at a glance. Cells are color-coded
        by percentile — dark green = top of the event, dark red = bottom.
        Use the section filters to focus on the attributes you care about.
        """)

    scouted_data = load_event_data(sk, ek)
    if len(scouted_data.index) == 0:
        st.warning("No scouting data available.")
        st.stop()

    td = load_team_data(ek)
    team_names = {row.number: row['name'] for _, row in td.iterrows()}

    # Per-team averages
    team_avgs = scouted_data.groupby('team_number').mean(numeric_only=True).reset_index()

    all_cols = [c for c in team_avgs.select_dtypes(include='number').columns
                if c not in SKIP_COLS and c != 'team_number' and c != 'match_number']

    # Section filter
    selected_sections = st.multiselect(
        "Show sections",
        [s[0] for s in SECTIONS],
        default=[s[0] for s in SECTIONS],
    )
    active_tests = {name: test for name, test in SECTIONS if name in selected_sections}
    visible_cols = [c for c in all_cols if any(test(c) for test in active_tests.values())]

    if not visible_cols:
        st.info("Select at least one section.")
        return

    sort_by = st.selectbox("Sort teams by", visible_cols, format_func=pretty_name)

    # Build display dataframe
    display = team_avgs[['team_number'] + visible_cols].copy()
    display['team_number'] = display['team_number'].apply(
        lambda t: f"{int(t)} ({team_names.get(int(t), '')})"
    )
    display = display.set_index('team_number')
    display.columns = [pretty_name(c) for c in display.columns]
    display = display.sort_values(pretty_name(sort_by), ascending=False)

    # Apply percentile-based color gradient
    styled = display.style.background_gradient(
        cmap='RdYlGn', axis=0
    ).format('{:.1f}')

    st.dataframe(styled, use_container_width=True, height=min(len(display) * 35 + 50, 800))
