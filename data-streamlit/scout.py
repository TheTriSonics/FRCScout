import numpy as np
import pandas as pd
import streamlit as st
import pygwalker as pyg
import streamlit.components.v1 as components

from plotnine import ggplot, aes, geom_point
from sklearn.cluster import KMeans

base_url = "https://trisonics-scouting-api.azurewebsites.net/api"

norm = np.linalg.norm


def get_team_list_url(event_key):
    return f"{base_url}/GetTeamsForEvent?event_key={event_key}"


def get_scouted_data_url(secret_key, event_key):
    return f"{base_url}/GetResults?secret_team_key={secret_key}&event_key={event_key}"  # noqa


def get_opr_data_url(secret_key, event_key):
    return f"{base_url}/GetOPRData?secret_team_key={secret_key}&event_key={event_key}"  # noqa


def get_pit_data_url(secret_key, event_key, team_key):
    return f"{base_url}/GetPitResults?secret_team_key={secret_key}&event_key={event_key}&team_key={team_key}"  # noqa


def show_raw_grid_panel(df):
    st.subheader("Raw")
    # st.write(data)

    # Generate the HTML using Pygwalker, a charting tool
    pyg_html = pyg.to_html(df)
    # Embed the HTML into the Streamlit app
    components.html(pyg_html, height=1000, scrolling=True)


def pick_panel(team_data):
    st.header('Pick Lists')
    teamlist = zip(
        team_data.number, team_data.name
    )
    dnp_teams = st.multiselect('Do NOT Pick Teams', teamlist, default=[],
                               format_func=lambda x: f'{x[0]} ({x[1]})')
    return dnp_teams


def show_cluster_panel(df, opr, dnp):
    print(dnp)
    dnp_nums = [x[0] for x in dnp]
    print(dnp_nums)
    df = df[~df.scouting_team.isin(dnp_nums)]
    st.subheader("KMeans clusters")
    score_vectors = (
        df
        .groupby("scouting_team")
        .mean(numeric_only=True)
        .reset_index()
    )

    score_vectors['comp_teleop_piece_points'] = (
        (score_vectors['teleop_cubes_high'] +
         score_vectors['teleop_cones_high']) * 5 +
        (score_vectors['teleop_cubes_medium'] +
         score_vectors['teleop_cones_medium']) * 3 +
        (score_vectors['teleop_cubes_low'] +
         score_vectors['teleop_cones_low']) * 2
    )

    score_vectors['comp_auto_piece_points'] = (
        (score_vectors['auto_cubes_high'] +
         score_vectors['auto_cones_high']) * 6 +
        (score_vectors['auto_cubes_medium'] +
         score_vectors['auto_cones_medium']) * 4 +
        (score_vectors['auto_cubes_low'] +
         score_vectors['auto_cones_low']) * 3
    )

    score_cols = [x for x in score_vectors.columns
                  if x.startswith(('auto', 'tele', 'endgame', 'comp'))]
    variances = {}
    # Okay, we could do this with linear algebra. Might change it out
    # Have code in kmeans.ipynb notebook in project, but this gives the same
    # values
    for sc in score_cols:
        v = np.var(score_vectors[sc])
        variances[sc] = v
    variances_by_val = sorted(variances.items(), key=lambda x: x[1],
                              reverse=True)
    variances = dict(variances_by_val)
    avail_cols = list(zip(variances.keys(), variances.values()))
    st.subheader("Variance of each column")
    col1 = variances.keys()
    col2 = variances.values()
    var_df = pd.DataFrame({'measure': col1, 'var': col2})
    st.dataframe(var_df, hide_index=True)
    data_cols = st.multiselect('Considered data', avail_cols,
                               format_func=lambda x: f'{x[0]} ({x[1]:0.2f})',
                               default=avail_cols[:8])

    if len(data_cols) == 0:
        return  # Can't go on. Just abort

    model = KMeans(int(cluster_count),
                   random_state=1,
                   init='random',
                   n_init=10,
                   max_iter=100)
    v = score_vectors.loc[:, [x[0] for x in data_cols]]
    if False:
        print(
            v.to_numpy()
        )
    model.fit(v.to_numpy())
    clusters = {}

    labels, centers = zip(
        *sorted(zip(set(model.labels_), model.cluster_centers_),
                reverse=True))
    for label, centroid in zip(labels, centers):
        clusters[label] = {
            'teams': [],
            'centroid_mag': norm(centroid),
            'opr_total': 0,
            'opr_avg': 0,
        }

    for (idx, row), label in zip(score_vectors.iterrows(), model.labels_):
        clusters[label]['teams'].append(str(int(row.scouting_team)))
        teamopr = opr_data[opr_data.teamNumber == row.scouting_team]
        if len(teamopr == 1):
            clusters[label]['opr_total'] += (
                teamopr.totalPoints.values[0]
            )
            clusters[label]['opr_avg'] = (
                clusters[label]['opr_total'] / len(clusters[label]['teams'])
            )
        else:
            print(f'{row.scouting_team}: {len(teamopr)}')
    idx = 1
    for cname, cluster in sorted(clusters.items(),
                                 key=lambda x: x[1]['opr_avg'],
                                 reverse=True):
        opr_avg = cluster['opr_total'] / len(cluster['teams'])
        st.header(f"Group {idx} ({opr_avg:0.2f} OPR Avg)")
        st.info(', '.join(cluster['teams']))
        idx += 1


@st.cache_data
def load_team_data(event_key):
    url = get_team_list_url(event_key)
    print(url)
    df = pd.read_json(url)
    return df


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


@st.cache_data
def load_opr_data(secret_key, event_key):
    url = get_opr_data_url(secret_key, event_key)
    print(url)
    opr_data = pd.read_json(url)
    return opr_data


st.set_page_config(layout="wide")
st.title("Trisonics FRC Scouting")

# List of competitions to offer in select box
event_key_list = ["2023micmp4", "2023miwmi"]

secret_key = st.text_input("Secret key")
event_key = st.selectbox("Event key", event_key_list)

if secret_key and event_key:
    data_load_state = st.text("Loading data...")
    scouted_data = load_event_data(secret_key, event_key)
    team_data = load_team_data(event_key)
    opr_data = load_opr_data(secret_key, event_key)
    data_load_state = st.text("Data loaded!")
    show_raw = st.checkbox("Show raw data")
    if show_raw:
        show_raw_grid_panel(scouted_data)

    dnp = pick_panel(team_data)

    show_clusters = st.checkbox("Show clusters")
    cluster_count = st.text_input("Cluster Count", 4)
    if show_clusters and len(cluster_count) > 0 and int(cluster_count) > 0:
        show_cluster_panel(scouted_data, opr_data, dnp)

team = None


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
        st.dataframe(tdf, hide_index=True)
        st.subheader("Team Raw Pit Data")
        st.dataframe(pdf, hide_index=True)

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
    cdf = tdf[['match_key'] + teleop_cols]
    team_breakdown = (
        cdf.melt(id_vars=['match_key'])
           .groupby(['match_key', 'variable'])['value']
           .sum(numeric_only=True)
           .reset_index()
    )
    ap = (
        ggplot(team_breakdown,
               aes('match_key', 'value')) + geom_point()
    )
    st.pyplot(ggplot.draw(ap))
    st.subheader("Auton")
    st.bar_chart(auton_df)

    st.subheader("Teleop")
    st.bar_chart(teleop_df)

    st.subheader("Endgame")
    st.bar_chart(endgame_df)
