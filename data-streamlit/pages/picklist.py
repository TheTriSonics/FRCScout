import streamlit as st

from scout import (
    load_team_data, get_event_key
)


def pick_panel(team_data):
    st.header('Pick Lists')
    dnp_teamlist = list(zip(
        team_data.number, team_data.name
    ))
    fsp_teamlist = list(zip(
        team_data.number, team_data.name
    ))
    dnp_teams = st.multiselect('Do NOT Pick Teams', dnp_teamlist,
                               format_func=lambda x: f'{x[0]} ({x[1]})',
                               key='pick_list_dnp')
    fsp_teams = st.multiselect('First Pick Teams', fsp_teamlist,
                               format_func=lambda x: f'{x[0]} ({x[1]})',
                               key='pick_list_fsp')
    return dnp_teams, fsp_teams


def picklist_page():
    """Picklist page"""
    event_key = get_event_key()

    if event_key is None:
        st.warning("Please set event key in the Config page first.")
        st.stop()

    team_data = load_team_data(event_key)
    pick_panel(team_data)
