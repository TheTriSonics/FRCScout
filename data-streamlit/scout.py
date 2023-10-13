import streamlit as st
import pandas as pd

dataurl = "https://trisonics-scouting-api.azurewebsites.net/api/GetResults?secret_team_key=##TEAMKEY##&event_key=##EVENTKEY##"


@st.cache_data
def load_data(secreT_key, event_key):
    url = (dataurl.replace('##TEAMKEY##', secret_key)
                  .replace('##EVENTKEY##', event_key))
    print(url)
    data = pd.read_json(url)
    return data


st.set_page_config(layout='wide')
st.title("Event Scouting Data")

event_key_list = ['2023micmp4', '2023miwmi']

secret_key = st.text_input('Secret key')
event_key = st.selectbox('Event key', event_key_list)

if secret_key and event_key:
    data_load_state = st.text("Loading data...")
    data = load_data(secret_key, event_key)
    data_load_state.text("Done! (using st.cache_data)")
    team = st.selectbox("Team", sorted(data.scouting_team.unique()))


show_raw = st.checkbox("Show raw data")
if show_raw:
    st.subheader("Raw")
    st.write(data)


if team:
    tdf = data.loc[data.scouting_team == team]
    allcols = tdf.columns
    auton_cols = [c for c in allcols if c.startswith('auto')]
    auton_df = tdf[auton_cols]
    teleop_cols = [c for c in allcols if c.startswith('tele')]
    teleop_df = tdf[teleop_cols]
    endgame_cols = [c for c in allcols if c.startswith('endgame')]
    endgame_df = tdf[endgame_cols]
    if show_raw:
        st.subheader("Team Raw Data")
        st.write(auton_df)

    st.subheader("Auton")
    st.altair_chart(auton_df)

    st.subheader("Teleop")
    st.bar_chart(teleop_df)

    st.subheader("Endgame")
    st.bar_chart(endgame_df)

