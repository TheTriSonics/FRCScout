import numpy as np
import pandas as pd
import streamlit as st
import pygwalker as pyg
import streamlit.components.v1 as components

from sklearn.cluster import KMeans

base_url = "https://trisonics-scouting-api.azurewebsites.net/api"


def get_scouted_data_url(secret_key, event_key):
    return f"{base_url}/GetResults?secret_team_key={secret_key}&event_key={event_key}"  # noqa


def get_pit_data_url(secret_key, event_key, team_key):
    return f"{base_url}/GetPitResults?secret_team_key={secret_key}&event_key={event_key}&team_key={team_key}"  # noqa


def show_raw_grid_panel(df):
    st.subheader("Raw")
    # st.write(data)

    # Generate the HTML using Pygwalker, a charting tool
    pyg_html = pyg.to_html(df)
    # Embed the HTML into the Streamlit app
    components.html(pyg_html, height=1000, scrolling=True)


def show_cluster_panel(df):
    st.subheader("KMeans clusters")
    score_vectors = (
        df
        .groupby("scouting_team")
        .sum(numeric_only=True)
        .reset_index()
    )

    avail_cols = set(score_vectors.columns) - set('scouting_team')
    avail_cols = sorted(list(avail_cols))
    data_cols = st.multiselect('Considered data', avail_cols,
                               default=avail_cols)

    if len(data_cols) == 0:
        return  # Can't go on. Just abort
    v = score_vectors.loc[:, data_cols]
    model = KMeans(int(cluster_count), n_init=100)
    model.fit(v.to_numpy())
    clusters = {}
    for label in set(model.labels_):
        clusters[label] = []
    for (idx, row), label in zip(score_vectors.iterrows(), model.labels_):
        clusters[label].append(row.scouting_team)

    for cluster_label, cluster_teams in clusters.items():
        cluster_data = score_vectors.loc[
            score_vectors.scouting_team.isin(cluster_teams)
        ]
        allcols = data_cols
        # Now we can create new dataframes where we only see the auto columns
        auton_cols = [c for c in allcols if c.startswith("auto")]
        auton_df = cluster_data[['scouting_team'] + auton_cols]
        teleop_cols = [c for c in allcols if c.startswith("tele")]
        teleop_df = cluster_data[['scouting_team'] + teleop_cols]
        st.header(f'Group {cluster_label+1}')
        st.info(', '.join(map(str, cluster_data['scouting_team'])))
        st.subheader("Auton Breakdown")
        st.bar_chart(auton_df, x='scouting_team')
        st.subheader("Teleop Breakdown")
        st.bar_chart(teleop_df, x='scouting_team')
        # print(auton_df.head())
        pass


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


st.set_page_config(layout="wide")
st.title("Trisonics FRC Scouting")

# List of competitions to offer in select box
event_key_list = ["2023micmp4", "2023miwmi"]

secret_key = st.text_input("Secret key")
event_key = st.selectbox("Event key", event_key_list)

if secret_key and event_key:
    data_load_state = st.text("Loading data...")
    scouted_data = load_event_data(secret_key, event_key)
    data_load_state = st.text("Data loaded!")

team = None

show_raw = st.checkbox("Show raw data")
if show_raw:
    show_raw_grid_panel()

show_clusters = st.checkbox("Show clusters")
cluster_count = st.text_input("Cluster Count", 4)
if show_clusters and len(cluster_count) > 0 and int(cluster_count) > 0:
    show_cluster_panel(scouted_data)

# This only runs when the user has entered a key and selected an event
if secret_key and event_key:
    team = st.selectbox("Team", sorted(scouted_data.scouting_team.unique()))


# As earlier, this only runs when a team has been selected
if team:
    # Trim team data down from the full event data to just theirs w/ Pandas
    tdf = scouted_data.loc[scouted_data.scouting_team == team]
    # Load in pit data
    print("Loading", team)
    pdf = load_pit_data(secret_key, event_key, team)
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

    # Use the earlier select box to determine if we're showing the raw
    # dataframes
    if show_raw:
        st.subheader("Team Raw Scouting Data")
        st.write(tdf)
        st.subheader("Team Raw Pit Data")
        st.write(pdf)

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
        for i in row.image_names:
            st.image(i)

    # Now show our auton, teleop, and endgame dataframes in bar chart form
    st.header("Scouted Data")
    st.subheader("Auton")
    st.bar_chart(auton_df)

    st.subheader("Teleop")
    st.bar_chart(teleop_df)

    st.subheader("Endgame")
    st.bar_chart(endgame_df)
