import os
import numpy as np
import pandas as pd
import streamlit as st
import st_pages as stp
import pygwalker as pyg
import streamlit.components.v1 as components

from plotnine import ggplot, aes, geom_point

base_url = "https://trisonics-scouting-api.azurewebsites.net/api"


def fix_session():
    st.session_state.update(st.session_state)


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


stp_dir = os.environ.get('STP_DIR')
stp.show_pages(
    [
        stp.Page(f'{stp_dir}/scout.py', 'Config'),
        stp.Page(f'{stp_dir}/pages/explore.py', 'Explore Data'),
        stp.Page(f'{stp_dir}/pages/team_detail.py', 'Team Details'),
        stp.Page(f'{stp_dir}/pages/clusters.py', 'Clustering'),
        stp.Page(f'{stp_dir}/pages/picklist.py', 'Pick Lists'),
        stp.Page(f'{stp_dir}/pages/what_if.py', 'What If'),
        stp.Page(f'{stp_dir}/pages/app_status.py', 'Workspace'),
    ]
)


p=True
@st.cache_data(persist=p)
def load_team_data(event_key):
    url = get_team_list_url(event_key)
    print(url)
    df = pd.read_json(url)
    return df


@st.cache_data(persist=p)
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


@st.cache_data(persist=p)
def load_pit_data(secret_key, event_key, team_key):
    url = get_pit_data_url(secret_key, event_key, team_key)
    print(url)
    pit_data = pd.read_json(url)
    return pit_data


@st.cache_data(persist=p)
def load_opr_data(secret_key, event_key):
    url = get_opr_data_url(secret_key, event_key)
    print(url)
    opr_data = pd.read_json(url)
    return opr_data


def get_dnp():
    if 'pick_list_dnp' in st.session_state:
        data = st.session_state.pick_list_dnp
        return [x[0] for x in data]
    else:
        return []


def get_secret_key():
    if 'secret_key' in st.session_state:
        return st.session_state.secret_key
    return None


def get_event_key():
    if 'event_key' in st.session_state:
        return st.session_state.event_key
    return None


def get_dnp_list():
    if 'pick_list_dnp' in st.session_state:
        return [x[0] for x in st.session_state.pick_list_dnp]


def load_data():
    secret_key = get_secret_key()
    event_key = get_event_key()

    try:
        _ = load_event_data(secret_key, event_key)
        st.success("Scouted data loaded!")
        _ = load_team_data(event_key)
        st.success("Event team list loaded!")
        _ = load_opr_data(secret_key, event_key)
        st.success("OPR calculations loaded")
        st.success("All data loaded! Proceed!")
    except BaseException as e:
        st.error(e)


def main():
    st.set_page_config(
        layout="wide",
        page_title="Config",
    )

    st.title("Trisonics FRC Scouting")

    # List of competitions to offer in select box
    event_key_list = ["2023micmp4", "2023miwmi"]

    if 'secret_key' not in st.session_state:
        # import os
        # st.session_state['secret_key'] = os.environ.get('FRC_SECRET_KEY')
        st.session_state['secret_key'] = ''

    with st.expander('Instructions'):
        st.write("""
Use this screen to enter your team's secret key. This is used to keep
different team's data seperate. If you want to pool efforts with
another team just use the same key.

Once you've entered that and selected an event data will be loaded for
the event.
        """)
    secret_key = st.text_input("Secret key", key='secret_key')
    event_key = st.selectbox("Event key", event_key_list, key='event_key')

    if secret_key and event_key:
        st.button('Load Data', on_click=load_data)

    # As earlier, this only runs when a team has been selected
    if False:

        # Use the earlier select box to determine if we're showing the raw
        # dataframes
        if show_raw:
            st.subheader("Team Raw Scouting Data")
            st.dataframe(tdf, hide_index=True)
            st.subheader("Team Raw Pit Data")
            st.dataframe(pdf, hide_index=True)



if __name__ == '__main__':
    fix_session()
    main()
