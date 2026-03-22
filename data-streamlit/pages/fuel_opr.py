import pandas as pd
import streamlit as st
import altair as alt

from scout import (
    load_opr_data, load_team_data, get_event_key, get_secret_key, pretty_name,
)


def fuel_opr_page():
    """2026 Rebuilt — Fuel OPR Breakdown"""
    sk = get_secret_key()
    ek = get_event_key()

    if sk is None or ek is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    st.header("Fuel OPR Breakdown")
    st.caption("2026 Rebuilt — fuel scored by phase, ranked by total OPR")

    opr_data = load_opr_data(sk, ek)
    if opr_data is None or len(opr_data.index) == 0:
        st.warning("No OPR data available yet. Qualification matches need to be played first.")
        st.stop()

    td = load_team_data(ek)
    team_names = {row.number: row['name'] for _, row in td.iterrows()}

    # Check for required columns
    required = ['hubScore_autoCount', 'hubScore_teleopCount', 'hubScore_endgameCount', 'teamNumber']
    missing = [c for c in required if c not in opr_data.columns]
    if missing:
        st.warning(f"OPR data missing fuel columns: {', '.join(missing)}")
        st.stop()

    # Build display data
    df = opr_data[['teamNumber', 'hubScore_autoCount', 'hubScore_teleopCount', 'hubScore_endgameCount']].copy()
    df['teamNumber'] = df['teamNumber'].astype(int)
    df['total'] = df['hubScore_autoCount'] + df['hubScore_teleopCount'] + df['hubScore_endgameCount']
    df['team_label'] = df['teamNumber'].apply(lambda t: str(t))
    df['team_name'] = df['teamNumber'].apply(lambda t: team_names.get(t, ''))
    df = df.sort_values('total', ascending=False).reset_index(drop=True)

    team_order = df['team_label'].tolist()

    # Melt for stacked bar
    melted = df.melt(
        id_vars=['team_label', 'team_name', 'total'],
        value_vars=['hubScore_autoCount', 'hubScore_teleopCount', 'hubScore_endgameCount'],
        var_name='phase',
        value_name='fuel_opr',
    )
    melted['phase'] = melted['phase'].map({
        'hubScore_autoCount': 'Auto',
        'hubScore_teleopCount': 'Teleop',
        'hubScore_endgameCount': 'Endgame',
    })

    chart = alt.Chart(melted).mark_bar().encode(
        x=alt.X('team_label:N', sort=team_order, title='Team'),
        y=alt.Y('fuel_opr:Q', title='Fuel OPR'),
        color=alt.Color('phase:N',
                        sort=['Auto', 'Teleop', 'Endgame'],
                        scale=alt.Scale(
                            domain=['Auto', 'Teleop', 'Endgame'],
                            range=['#4e79a7', '#59a14f', '#f28e2b']),
                        title='Phase'),
        order=alt.Order('phase:N', sort='ascending'),
        tooltip=[
            alt.Tooltip('team_label:N', title='Team'),
            alt.Tooltip('team_name:N', title='Name'),
            alt.Tooltip('phase:N', title='Phase'),
            alt.Tooltip('fuel_opr:Q', format='.1f', title='Fuel OPR'),
            alt.Tooltip('total:Q', format='.1f', title='Total'),
        ],
    ).properties(height=450)

    st.altair_chart(chart, use_container_width=True)

    # Summary table
    with st.expander("Details"):
        table = df[['team_label', 'team_name', 'hubScore_autoCount',
                     'hubScore_teleopCount', 'hubScore_endgameCount', 'total']].copy()
        table.columns = ['Team', 'Name', 'Auto', 'Teleop', 'Endgame', 'Total']
        st.dataframe(
            table.style.format({'Auto': '{:.1f}', 'Teleop': '{:.1f}',
                                'Endgame': '{:.1f}', 'Total': '{:.1f}'}),
            hide_index=True, use_container_width=True,
        )
