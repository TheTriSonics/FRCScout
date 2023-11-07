import numpy as np
import pandas as pd
import streamlit as st
import st_pages as stp
import pygwalker as pyg
import streamlit.components.v1 as components

from plotnine import ggplot, aes, geom_point

base_url = "https://trisonics-scouting-api.azurewebsites.net/api"


def get_team_list_url(event_key):
    return f"{base_url}/GetTeamsForEvent?event_key={event_key}"


def get_scouted_data_url(secret_key, event_key):
    if secret_key:
        return f"{base_url}/GetResults?secret_team_key={secret_key}&event_key={event_key}"  # noqa
    else:
        raise ValueError('secret_key needs to be defined')


def get_opr_data_url(secret_key, event_key):
    return f"{base_url}/GetOPRData?secret_team_key={secret_key}&event_key={event_key}"  # noqa


def get_pit_data_url(secret_key, event_key, team_key):
    return f"{base_url}/GetPitResults?secret_team_key={secret_key}&event_key={event_key}&team_key={team_key}"  # noqa


stp.show_pages(
    [
        stp.Page('scout.py', 'Config'),
        stp.Page('pages/explore.py', 'Explore Data'),
        stp.Page('pages/team_detail.py', 'Team Details'),
        stp.Page('pages/clusters.py', 'Clustering'),
        stp.Page('pages/picklist.py', 'Pick Lists'),
        stp.Page('pages/what_if.py', 'What If'),
    ]
)


@st.cache_data(persist=True)
def load_team_data(event_key):
    url = get_team_list_url(event_key)
    print(url)
    df = pd.read_json(url)
    return df


@st.cache_data(persist=True)
def load_event_data(secret_key, event_key):
    url = get_scouted_data_url(secret_key, event_key)
    print(url)
    df = pd.read_json(url)

    # Create some computed columns out of our scouted data

    df['comp_teleop_piece_points'] = (
        (df['teleop_cubes_high'] +
         df['teleop_cones_high']) * 5 +
        (df['teleop_cubes_medium'] +
         df['teleop_cones_medium']) * 3 +
        (df['teleop_cubes_low'] +
         df['teleop_cones_low']) * 2
    )

    df['comp_auto_piece_points'] = (
        (df['auto_cubes_high'] +
         df['auto_cones_high']) * 6 +
        (df['auto_cubes_medium'] +
         df['auto_cones_medium']) * 4 +
        (df['auto_cubes_low'] +
         df['auto_cones_low']) * 3
    )

    return df


@st.cache_data(persist=True)
def load_pit_data(secret_key, event_key, team_key):
    url = get_pit_data_url(secret_key, event_key, team_key)
    print(url)
    pit_data = pd.read_json(url)
    return pit_data


@st.cache_data(persist=True)
def load_opr_data(secret_key, event_key):
    url = get_opr_data_url(secret_key, event_key)
    print(url)
    opr_data = pd.read_json(url)
    return opr_data


def get_secret_key():
    dead_code = """
    if 'secret_key' in st.session_state:
        return st.session_state.secret_key
    """
    import os
    secret_key = os.environ.get('FRC_SECRET_KEY')
    return secret_key


def get_event_key():
    if 'event_key' in st.session_state:
        return st.session_state.event_key
    return '2023micmp4'  # TODO: Ugh. Figure out session state issues


def main():
    st.set_page_config(
        layout="wide",
        page_title="Config",
    )

    st.title("Trisonics FRC Scouting")

    # List of competitions to offer in select box
    event_key_list = ["2023micmp4", "2023miwmi"]

    if 'secret_key' not in st.session_state:
        import os
        st.session_state['secret_key'] = os.environ.get('FRC_SECRET_KEY')

    secret_key = st.text_input("Secret key", key='secret_key')
    event_key = st.selectbox("Event key", event_key_list, key='event_key')

    if secret_key and event_key:
        data_load_state = st.text("Loading data...")
        scouted_data = load_event_data(secret_key, event_key)
        team_data = load_team_data(event_key)
        opr_data = load_opr_data(secret_key, event_key)
        data_load_state = st.text("Data loaded! Proceed!")

    # As earlier, this only runs when a team has been selected
    if False:
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


if __name__ == '__main__':
    main()