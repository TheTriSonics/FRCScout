import json
import pandas as pd
import urllib
import streamlit as st

from os.path import exists

base_url = "https://trisonics-scouting-api.azurewebsites.net/api"
statbot_url = "https://api.statbotics.io/v3"


instructions = """
        Use this screen to enter your team's secret key. This is used to keep
        different team's data seperate. If you want to pool efforts with
        another team just use the same key.

        Once you've entered that and selected an event data will be loaded for
        the event.
"""


def fix_session():
    st.session_state.update(st.session_state)


def get_team_list_url(event_key):
    return f"{base_url}/GetTeamsForEvent?event_key={event_key}"


def get_scouted_data_url(secret_key, event_key):
    if secret_key:
        return f"{base_url}/GetResults?secret_team_key={secret_key}&event_key={event_key}"  # noqa
    else:
        raise ValueError('secret_key needs to be defined')


def get_matches_data_url(event_key):
    return f"{base_url}/GetMatchesForEvent?event_key={event_key}"  # noqa


def get_opr_data_url(secret_key, event_key):
    return f"{base_url}/GetOPRData?secret_team_key={secret_key}&event_key={event_key}"  # noqa


def get_pit_data_url(secret_key, event_key, team_key):
    return f"{base_url}/GetPitResults?secret_team_key={secret_key}&event_key={event_key}&team_key={team_key}"  # noqa


def get_secret_key():
    ret = None
    if 'secret_key' in st.session_state:
        ret = st.session_state.secret_key
    if 'secret_key' in st.query_params:
        ret = st.query_params.secret_key
        st.session_state.secret_key = ret
    # Remove any leading or trailing whitespace from ret
    ret = ret.strip()
    print(f'secret_key: {ret}')
    return ret


def get_event_key():
    ret = None
    if 'event_key' in st.session_state:
        ret = st.session_state.event_key
    if 'event_key' in st.query_params:
        ret = st.query_params.event_key
        st.session_state.event_key = ret
    ret = ret.strip()
    print(f'event_key: {ret}')
    return ret




def _gen_pages(stp_dir, secret_key=None, event_key=None):
    return [
        st.Page(f'{stp_dir}/scout.py', title='Config'),
        # st.Page(f'{stp_dir}/pages/explore.py', title='Explore Data'),
        st.Page(f'{stp_dir}/pages/team_detail.py', title='Team Details'),
        st.Page(f'{stp_dir}/pages/clusters.py', title='Clustering'),
        st.Page(f'{stp_dir}/pages/picklist.py', title='Pick Lists'),
        st.Page(f'{stp_dir}/pages/match_breakdowns.py',
                 title='Match Breakdowns'),
        st.Page(f'{stp_dir}/pages/what_if.py', title='What If'),
        st.Page(f'{stp_dir}/pages/app_status.py', title='Workspace'),
    ]

p = False


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
    # Add a auton_coral_total column that adds up level, level2, etc.
    df['auto_coral_total'] = (
        df['auto_coral1'] + df['auto_coral2'] +
        df['auto_coral3'] + df['auto_coral4']
    )

    df['teleop_coral_total'] = (
        df['teleop_coral1'] + df['auto_coral2'] +
        df['teleop_coral3'] + df['auto_coral4']
    )
    return df


@st.cache_data(persist=p)
def load_matches_data(event_key):
    url = get_matches_data_url(event_key)
    print(url)
    df = pd.read_json(url)
    return df


@st.cache_data(persist=p)
def load_statbot_matches_data(event_key):
    url = f'{base_url}/GetStatboticsMatches?event_key={event_key}'
    print('statbot url', url)
    df = pd.read_json(url)
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

def load_tba_opr_data(event_key):
    pass


def get_dnp():
    if 'pick_list_dnp' in st.session_state:
        data = st.session_state.pick_list_dnp
        return data
    else:
        return []


def get_fsp():
    if 'pick_list_fsp' in st.session_state:
        data = st.session_state.pick_list_fsp
        return data
    else:
        return []


def load_data():
    secret_key = get_secret_key()
    event_key = get_event_key()

    all_loaded = True
    st.cache_data.clear()
    _ = load_event_data(secret_key, event_key)

    if len(_.index) > 0:
        st.success("Scouted data loaded!")
    else:
        st.error("Scouting data not found.")
        all_loaded = False
    _ = load_team_data(event_key)

    if len(_.index) > 0:
        st.success("Event team list loaded!")
    else:
        st.error("Event team list failed.")
        all_loaded = False

    try:
        _ = load_opr_data(secret_key, event_key)
        if len(_.index) > 0:
            st.success("OPR calculations loaded")
        else:
            st.success("OPR calculation load failed.")
            all_loaded = False
    except urllib.error.HTTPError:  # noqa
        # Swallow eception
        st.success("OPR calculation not available yet.")
        pass
    if all_loaded:
        st.success("All data loaded! Proceed!")


def main():
    st.set_page_config(
        layout="wide",
    )

    st.title("Trisonics FRC Scouting")

    pg = st.navigation(_gen_pages('.'))
    pg.run()

    if 'secret_key' not in st.session_state:
        # import os
        # st.session_state['secret_key'] = os.environ.get('FRC_SECRET_KEY')
        st.session_state['secret_key'] = ''
    if 'event_key' not in st.session_state:
        st.session_state['event_key'] = ''

    with st.expander('Instructions'):
        st.write(instructions)
    if 'secret_key' in st.query_params:
        secret_key = st.query_params['secret_key']
        st.session_state.secret_key = secret_key
    else:
        st.text_input("Secret key", key='secret_key')
    if 'event_key' in st.query_params:
        event_key = st.query_params['event_key']
        st.session_state.event_key = event_key
    else:
        st.text_input("Event key", key='event_key')
    st.button('Load Data', on_click=load_data)


def load_dev_config():
    cfg = 'config.json'
    if exists(cfg):
        with open(cfg) as f:
            obj = json.load(f)
            st.session_state.update(obj)


if __name__ == '__main__':
    load_dev_config()
    fix_session()
    main()
