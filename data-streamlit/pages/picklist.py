import streamlit as st

from scout import (
    load_team_data, get_event_key, fix_session
)


def pick_panel(team_data):
    st.header('Pick Lists')
    dnp_teamlist = zip(
        team_data.number, team_data.name
    )
    fsp_teamlist = zip(
        team_data.number, team_data.name
    )
    dnp_teams = st.multiselect('Do NOT Pick Teams', dnp_teamlist,
                               format_func=lambda x: f'{x[0]} ({x[1]})',
                               key='pick_list_dnp')
    fsp_teams = st.multiselect('First Pick Teams', fsp_teamlist,
                               format_func=lambda x: f'{x[0]} ({x[1]})',
                               key='pick_list_fsp')
    return dnp_teams, fsp_teams


fix_session()
team_data = load_team_data(get_event_key())
pick_panel(team_data)
