import numpy as np
import pandas as pd
import streamlit as st
from scout import (
    get_event_key, get_secret_key, load_event_data, load_team_data,
    load_pit_data, fix_session,
)

fix_session()
# This only runs when the user has entered a key and selected an event
team = None
scout_data = load_event_data(get_secret_key(), get_event_key())
td = load_team_data(get_event_key())
all_teams = [(row.number, row['name']) for idx, row in td.iterrows()]
team = st.selectbox("Team", all_teams,
                    format_func=lambda x: f'{x[0]} ({x[1]})')
if team:
    scouted_data = load_event_data(get_secret_key(), get_event_key())
    (team_number, team_name) = team
    st.info(f'Details on {team_number}')
    # Trim team data down from the full event data to just theirs w/ Pandas
    tdf = scouted_data.loc[scouted_data.scouting_team == team_number]
    # Load in pit data
    pdf = load_pit_data(get_secret_key(), get_event_key(), team_number)
    # Gets a list of every column name in the dataframe
    allcols = tdf.columns
    # Now we can create new dataframes where we only see the auto columns
    auton_cols = [c for c in allcols if c.startswith("auto")]
    auton_df = tdf[auton_cols]
    # And then teleop...
    teleop_cols = [c for c in allcols if c.startswith("tele")]
    teleop_df = tdf[teleop_cols]
    # And endgame.
    endgame_cols = [c for c in allcols if c.startswith("endgame")]
    endgame_df = tdf[endgame_cols]

    # And our computed ones
    comp_cols = [c for c in allcols if c.startswith("comp")]
    comp_df = tdf[comp_cols]

    st.subheader("Computed")
    st.bar_chart(comp_df)

    st.subheader("Auton")
    st.bar_chart(auton_df)

    st.subheader("Teleop")
    st.bar_chart(teleop_df)

    st.subheader("Endgame")
    st.bar_chart(endgame_df)

