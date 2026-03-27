import pandas as pd
import streamlit as st

from scout import (
    load_event_data, load_team_data, get_event_key, get_secret_key,
    BINARY_COLS, SKIP_COLS, SECTIONS, pretty_name, team_status_label,
)


def heatmap_page():
    """Event Heatmap — attributes vs teams, color-coded by percentile."""
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
        Teams go across the top, attributes down the left. Use the filters
        to show/hide sections or specific teams.
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

    # Team filter — default to all
    all_team_options = []
    for _, row in team_avgs.iterrows():
        tn = int(row['team_number'])
        label = f"{tn} ({team_names.get(tn, '')}){team_status_label(tn)}"
        all_team_options.append((tn, label))

    selected_teams = st.multiselect(
        "Teams",
        all_team_options,
        default=all_team_options,
        format_func=lambda x: x[1],
    )

    if not selected_teams:
        st.info("Select at least one team.")
        return

    selected_team_nums = [t[0] for t in selected_teams]
    filtered = team_avgs[team_avgs['team_number'].isin(selected_team_nums)]

    # Build display: attributes as rows, teams as columns
    display = filtered[['team_number'] + visible_cols].copy()
    display['team_number'] = display['team_number'].apply(
        lambda t: f"{int(t)}{team_status_label(int(t))}"
    )
    display = display.set_index('team_number')
    display.columns = [pretty_name(c) for c in display.columns]
    # Transpose: attributes down the left, teams across the top
    display = display.T

    # Apply percentile-based color gradient (across columns = across teams)
    try:
        styled = display.style.background_gradient(
            cmap='RdYlGn', axis=1
        ).format('{:.1f}')
    except ImportError:
        styled = display.style.background_gradient(
            axis=1
        ).format('{:.1f}')

    st.dataframe(styled, use_container_width=True,
                 height=min(len(display) * 35 + 50, 800))
