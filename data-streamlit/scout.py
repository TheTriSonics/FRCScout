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
        ret = str(st.query_params['secret_key'])
        st.session_state.secret_key = ret
    # Remove any leading or trailing whitespace from ret
    if ret:
        ret = ret.strip()
    return ret or ''


def get_event_key():
    ret = None
    if 'event_key' in st.session_state:
        ret = st.session_state.event_key
    if 'event_key' in st.query_params:
        ret = str(st.query_params['event_key'])
        st.session_state.event_key = ret
    # Remove any leading or trailing whitespace from ret
    if ret:
        ret = ret.strip()
    return ret or ''


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_team_data(event_key):
    if not event_key:
        return pd.DataFrame()
    url = get_team_list_url(event_key)
    print(url)
    df = pd.read_json(url)
    return df

@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_event_data(secret_key, event_key):
    if not secret_key or not event_key:
        return pd.DataFrame()
    url = get_scouted_data_url(secret_key, event_key)
    print(url)
    df = pd.read_json(url)
    if event_key.startswith('2025') and len(df.index) > 0:
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


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_matches_data(event_key):
    if not event_key:
        return pd.DataFrame()
    url = get_matches_data_url(event_key)
    print(url)
    df = pd.read_json(url)
    return df


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_statbot_matches_data(event_key):
    if not event_key:
        return pd.DataFrame()
    url = f'{base_url}/GetStatboticsMatches?event_key={event_key}'
    print('statbot url', url)
    df = pd.read_json(url)
    return df


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_pit_data(secret_key, event_key, team_key):
    if not secret_key or not event_key:
        return pd.DataFrame()
    url = get_pit_data_url(secret_key, event_key, team_key)
    print(url)
    pit_data = pd.read_json(url)
    return pit_data


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_opr_data(secret_key, event_key):
    if not secret_key or not event_key:
        return None
    url = get_opr_data_url(secret_key, event_key)
    print(url)
    try:
        opr_data = pd.read_json(url)
        return opr_data
    except:
        return None

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
        if _ is not None and len(_.index) > 0:
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


def config_page():
    """Config page - inline here to avoid circular imports"""
    if 'secret_key' not in st.session_state:
        st.session_state['secret_key'] = ''
    if 'event_key' not in st.session_state:
        st.session_state['event_key'] = ''

    with st.expander('Instructions'):
        st.write(instructions)
    if 'secret_key' in st.query_params:
        secret_key = str(st.query_params['secret_key'])
        st.session_state.secret_key = secret_key
    else:
        st.text_input("Secret key", key='secret_key')
    if 'event_key' in st.query_params:
        event_key = str(st.query_params['event_key'])
        st.session_state.event_key = event_key
    else:
        st.text_input("Event key", key='event_key')
    st.button('Load Data', on_click=load_data)


def main():
    st.set_page_config(
        layout="wide",
    )

    st.title("Trisonics FRC Scouting")

    # Import page functions lazily to avoid module-level execution
    from pages.team_detail import team_detail_page
    from pages.clusters import clusters_page
    from pages.picklist import picklist_page
    from pages.match_breakdowns import match_breakdowns_page
    from pages.what_if import what_if_page
    from pages.app_status import app_status_page
    from pages.pca import pca_page

    pg = st.navigation([
        st.Page(config_page, title='Config'),
        st.Page(team_detail_page, title='Team Details'),
        st.Page(clusters_page, title='Clustering'),
        st.Page(picklist_page, title='Pick Lists'),
        st.Page(match_breakdowns_page, title='Match Breakdowns'),
        st.Page(what_if_page, title='What If'),
        st.Page(pca_page, title='PCA'),
        st.Page(app_status_page, title='Workspace'),
    ])
    pg.run()


def load_dev_config():
    cfg = 'config.json'
    if exists(cfg):
        with open(cfg) as f:
            obj = json.load(f)
            st.session_state.update(obj)


if __name__ == '__main__':
    load_dev_config()
    main()
