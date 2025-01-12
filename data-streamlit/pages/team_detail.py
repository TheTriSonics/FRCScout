import streamlit as st
from scout import (
    get_event_key, get_secret_key, load_event_data, load_team_data,
    load_pit_data, fix_session,
)

fix_session()

team = None
scout_data = load_event_data(get_secret_key(), get_event_key())
td = load_team_data(get_event_key())
all_teams = [(row.number, row['name']) for idx, row in td.iterrows()]
st.header("Team Details")
with st.expander('Instructions'):
    st.write("""
    Select a team to see their detailed data.
    """)
team = st.selectbox("Team", all_teams,
                    format_func=lambda x: f'{x[0]} ({x[1]})')
show_raw = st.checkbox('Show raw data')
if team:
    scouted_data = load_event_data(get_secret_key(), get_event_key())
    (team_number, team_name) = team
    # Trim team data down from the full event data to just theirs w/ Pandas
    tdf = scouted_data.loc[scouted_data.scouting_team == team_number]
    # Load in pit data
    pdf = load_pit_data(get_secret_key(), get_event_key(), team_number)

    if show_raw:
        st.subheader("Team Raw Scouting Data")
        st.dataframe(tdf, hide_index=True)
        st.subheader("Team Raw Pit Data")
        st.dataframe(pdf, hide_index=True)

    # Gets a list of every column name in the dataframe
    allcols = tdf.columns
    # Now we can create new dataframes where we only see the auto columns
    auton_cols = [c for c in allcols if c.startswith("auto") or c == 'match_key']
    auton_df = tdf[auton_cols]
    # And then teleop...
    teleop_cols = [c for c in allcols if c.startswith("tele") or c == 'match_key']
    teleop_df = tdf[teleop_cols]
    # And endgame.
    endgame_cols = [c for c in allcols if c.startswith("endgame") or c == 'match_key']
    endgame_df = tdf[endgame_cols]
    # And our computed ones
    # comp_cols = [c for c in allcols if c.startswith("comp")]
    # comp_df = tdf[comp_cols]

    # st.subheader("Computed")
    # st.bar_chart(comp_df)

    st.subheader("Auton")
    st.bar_chart(auton_df, x='match_key')

    st.subheader("Teleop")
    st.bar_chart(teleop_df, x='match_key')

    st.subheader("Endgame")
    st.bar_chart(endgame_df, x='match_key')

    # Show the pit scouting data
    st.header("Pit Scouting")
    if len(pdf.index) == 0:
        # If we don't have data let the user know
        st.subheader("No pit scouting data")
    # Iterate through the pit scouting results (likely only one) and show
    # them on the UI.
    for idx, row in pdf.iterrows():
        st.subheader(row.scouter_name)
        st.info(row.robot_notes or "no notes")
        wheel_types = []
        if row.wheel_omni:
            wheel_types.append('Omni')
        if row.wheel_inflated:
            wheel_types.append('Inflated')
        if row.wheel_mec:
            wheel_types.append('Mecanum')
        if row.wheel_solid:
            wheel_types.append('Solid')
        if len(wheel_types) == 0:
            wheel_types = ['N/A']
        rating = f'{row.robot_rating}/10' if row.robot_rating else 'N/A'
        st.write(f"#### Wheel type(s): {', '.join(wheel_types)}  ")
        st.write(f"#### Drive Train: {row.drive_train}  ")
        st.write(f"#### Rating: {rating}  ")
        for i in row.image_names:
            st.image(i)
