import pandas as pd
import numpy as np
import streamlit as st

from scout import (
    load_event_data, load_opr_data, load_team_data, get_event_key,
    get_secret_key, fix_session, get_dnp_list
)


def pick_panel(team_data):
    st.header('Pick Lists')
    teamlist = zip(
        team_data.number, team_data.name
    )
    dnp_teams = st.multiselect('Do NOT Pick Teams', teamlist,
                               format_func=lambda x: f'{x[0]} ({x[1]})',
                               key='pick_list_dnp')
    return dnp_teams


fix_session()
team_data = load_team_data(get_event_key())
dnp = pick_panel(team_data)
