import pandas as pd
import streamlit as st

from scout import (
    load_team_data, load_event_data, get_event_key, get_secret_key,
    BINARY_COLS, SKIP_COLS, pretty_name,
)


def picklist_page():
    """Picklist page with weighted scoring"""
    sk = get_secret_key()
    ek = get_event_key()

    if ek is None:
        st.warning("Please set event key in the Config page first.")
        st.stop()

    team_data = load_team_data(ek)
    teamlist = list(zip(team_data.number, team_data.name))
    fmt = lambda x: f'{x[0]} ({x[1]})'

    st.header('Pick Lists')
    st.multiselect('Do NOT Pick Teams', teamlist, format_func=fmt, key='pick_list_dnp')
    st.multiselect('First Pick Teams', teamlist, format_func=fmt, key='pick_list_fsp')

    # --- Weighted Draft Board ---
    st.header('Weighted Draft Board')
    with st.expander('Instructions'):
        st.write("""
        Assign weights to each attribute using the sliders below. The system
        computes a composite score for each team based on their percentile
        rank in each attribute multiplied by your weight. Higher weight =
        more important to your alliance strategy. Teams are ranked by
        total weighted score.
        """)

    if sk is None:
        st.warning("Please set secret key to use the draft board.")
        st.stop()

    scouted_data = load_event_data(sk, ek)
    if len(scouted_data.index) == 0:
        st.warning("No scouting data available.")
        return

    team_avgs = scouted_data.groupby('team_number').mean(numeric_only=True).reset_index()
    score_cols = [c for c in team_avgs.select_dtypes(include='number').columns
                  if c not in SKIP_COLS and c != 'team_number' and c != 'match_number'
                  and c not in BINARY_COLS]

    if not score_cols:
        st.info("No numeric attributes available for scoring.")
        return

    # Weight sliders
    weights = {}
    slider_cols = st.columns(min(len(score_cols), 3))
    for i, col in enumerate(sorted(score_cols)):
        with slider_cols[i % len(slider_cols)]:
            weights[col] = st.slider(pretty_name(col), 0, 10, 5, key=f'weight_{col}')

    # Compute percentiles and weighted score
    active_weights = {k: v for k, v in weights.items() if v > 0}
    if not active_weights:
        st.info("Set at least one weight above 0.")
        return

    result = team_avgs[['team_number']].copy()
    total_weight = sum(active_weights.values())
    result['score'] = 0.0

    for col, weight in active_weights.items():
        vals = team_avgs[col]
        col_min, col_max = vals.min(), vals.max()
        col_range = col_max - col_min
        if col_range > 0:
            pct = (vals - col_min) / col_range * 100
        else:
            pct = pd.Series(50, index=vals.index)
        result['score'] += pct * (weight / total_weight)

    result['score'] = result['score'].round(1)
    result = result.sort_values('score', ascending=False).reset_index(drop=True)
    result['rank'] = range(1, len(result) + 1)

    # Add team names
    team_names = {row.number: row['name'] for _, row in team_data.iterrows()}
    result['team'] = result['team_number'].apply(
        lambda t: f"{int(t)} ({team_names.get(int(t), '')})"
    )

    # Mark DNP/FSP
    dnp_nums = [t[0] for t in st.session_state.get('pick_list_dnp', [])]
    fsp_nums = [t[0] for t in st.session_state.get('pick_list_fsp', [])]
    result['status'] = result['team_number'].apply(
        lambda t: 'DNP' if t in dnp_nums else ('1st Pick' if t in fsp_nums else '')
    )

    display = result[['rank', 'team', 'score', 'status']].copy()
    display.columns = ['Rank', 'Team', 'Score', 'Status']

    def _status_color(val):
        if val == 'DNP':
            return 'color: #e15759; font-weight: bold'
        elif val == '1st Pick':
            return 'color: #59a14f; font-weight: bold'
        return ''

    styled = display.set_index('Rank').style.map(_status_color, subset=['Status'])
    st.dataframe(styled, use_container_width=True, height=min(len(display) * 35 + 50, 600))
