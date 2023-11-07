import numpy as np
import pandas as pd
import streamlit as st
from scout import (
    get_event_key, get_secret_key, load_event_data, load_team_data
)

# This only runs when the user has entered a key and selected an event
team = None
scout_data = load_event_data(get_secret_key(), get_event_key())
td = load_team_data(get_event_key())
all_teams = [(row.number, row['name']) for idx, row in td.iterrows()]
team = st.selectbox("Team", all_teams,
                    format_func=lambda x: f'{x[0]} ({x[1]})')
if team:
    (team_number, team_name) = team
    st.info(f'Details on {team_number}')

