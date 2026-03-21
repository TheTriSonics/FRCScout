import streamlit as st

from scout import (
    load_team_data, get_event_key
)


def pick_panel(team_data):
    st.header('Pick Lists')
    teamlist = list(zip(team_data.number, team_data.name))
    fmt = lambda x: f'{x[0]} ({x[1]})'
    st.multiselect('Do NOT Pick Teams', teamlist, format_func=fmt, key='pick_list_dnp')
    st.multiselect('First Pick Teams', teamlist, format_func=fmt, key='pick_list_fsp')


def picklist_page():
    """Picklist page"""
    event_key = get_event_key()

    if event_key is None:
        st.warning("Please set event key in the Config page first.")
        st.stop()

    team_data = load_team_data(event_key)
    pick_panel(team_data)
