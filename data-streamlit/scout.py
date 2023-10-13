import streamlit as st
import pandas as pd

base_url = 'https://trisonics-scouting-api.azurewebsites.net/api'


def get_scouted_data_url(secret_key, event_key):
    return f'{base_url}/GetResults?secret_team_key={secret_key}&event_key={event_key}'  # noqa


def get_pit_data_url(secret_key, event_key, team_key):
    return f'{base_url}/GetPitResults?secret_team_key={secret_key}&event_key={event_key}&team_key={team_key}'  # noqa


@st.cache_data
def load_event_data(secret_key, event_key):
    url = get_scouted_data_url(secret_key, event_key)
    print(url)
    scouted_data = pd.read_json(url)
    return scouted_data


@st.cache_data
def load_pit_data(secret_key, event_key, team_key):
    url = get_pit_data_url(secret_key, event_key, team_key)
    print(url)
    pit_data = pd.read_json(url)
    return pit_data


st.set_page_config(layout='wide')
st.title("Event Scouting Data")

event_key_list = ['2023micmp4', '2023miwmi']

secret_key = st.text_input('Secret key')
event_key = st.selectbox('Event key', event_key_list)

team = None

if secret_key and event_key:
    data_load_state = st.text("Loading data...")
    data = load_event_data(secret_key, event_key)
    data_load_state.text("Done! (using st.cache_data)")
    team = st.selectbox("Team", sorted(data.scouting_team.unique()))


show_raw = st.checkbox("Show raw data")
if show_raw:
    st.subheader("Raw")
    st.write(data)


if team:
    # Trim team data down from the full event data to just theirs
    tdf = data.loc[data.scouting_team == team]
    # Load in pit data
    print('Loading', team)
    pdf = load_pit_data(secret_key, event_key, team)
    allcols = tdf.columns
    auton_cols = [c for c in allcols if c.startswith('auto')]
    auton_df = tdf[auton_cols]
    teleop_cols = [c for c in allcols if c.startswith('tele')]
    teleop_df = tdf[teleop_cols]
    endgame_cols = [c for c in allcols if c.startswith('endgame')]
    endgame_df = tdf[endgame_cols]
    if show_raw:
        st.subheader("Team Raw Scouting Data")
        st.write(tdf)
        st.subheader("Team Raw Pit Data")
        st.write(pdf)

    st.header("Pit Scouting")
    if len(pdf.index) == 0:
        st.subheader('No pit scouting data')
    for idx, row in pdf.iterrows():
        st.subheader(row.scouter_name)
        st.info(row.robot_notes or 'no notes')
        for i in row.image_names:
            st.image(i)

    st.header("Scouted Data")
    st.subheader("Auton")
    st.bar_chart(auton_df)

    st.subheader("Teleop")
    st.bar_chart(teleop_df)

    st.subheader("Endgame")
    st.bar_chart(endgame_df)

