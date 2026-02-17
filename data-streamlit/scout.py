import json
import pandas as pd
import urllib
import streamlit as st
import extra_streamlit_components as stx

from os.path import exists

base_url = "https://trisonics-scouting-api.azurewebsites.net/api"
statbot_url = "https://api.statbotics.io/v3"

def init_cookies():
    """Initialize cookie manager and read cookies. Call once at the top of main()."""
    # Must create CookieManager every render so its hidden JS component stays
    # in the page. Caching it in session_state and skipping creation on later
    # renders meant the iframe never re-rendered and get_all() returned stale
    # data.
    st.session_state.cookie_manager = stx.CookieManager(key='cookie_manager_main')
    cookies = st.session_state.cookie_manager.get_all()
    if cookies:
        st.session_state.cookies = cookies
    elif 'cookies_checked' not in st.session_state:
        # First render: the browser JS component hasn't reported cookies yet.
        # Mark as checked and rerun so the component gets a full round-trip.
        st.session_state.cookies_checked = True
        st.rerun()


def get_cookies():
    """Return cached cookies dict (populated by init_cookies)."""
    return st.session_state.get('cookies', {})


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
    """Get secret key, checking cookies → query params → session state"""
    ret = None
    cookies = get_cookies()

    # Priority 1: Query params (from URL - for sharing)
    if 'secret_key' in st.query_params:
        ret = str(st.query_params['secret_key'])
    # Priority 2: Cookies (for persistence across sessions)
    elif cookies and 'secret_key' in cookies:
        ret = cookies['secret_key']
    # Priority 3: Session state
    elif 'secret_key' in st.session_state:
        ret = st.session_state.secret_key

    # Clean and sync
    if ret:
        ret = ret.strip()
        if ret:
            st.session_state.secret_key = ret

    return ret if ret else None


def get_event_key():
    """Get event key, checking cookies → query params → session state"""
    ret = None
    cookies = get_cookies()

    # Priority 1: Query params (from URL - for sharing)
    if 'event_key' in st.query_params:
        ret = str(st.query_params['event_key'])
    # Priority 2: Cookies (for persistence across sessions)
    elif cookies and 'event_key' in cookies:
        ret = cookies['event_key']
    # Priority 3: Session state
    elif 'event_key' in st.session_state:
        ret = st.session_state.event_key

    # Clean and sync
    if ret:
        ret = ret.strip()
        if ret:
            st.session_state.event_key = ret

    return ret if ret else None


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_team_data(event_key):
    if event_key is None or event_key == '':
        return pd.DataFrame()
    url = get_team_list_url(event_key)
    print(url)
    df = pd.read_json(url)
    return df

@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_event_data(secret_key, event_key):
    if secret_key is None or event_key is None or secret_key == '' or event_key == '':
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
            df['teleop_coral1'] + df['teleop_coral2'] +
            df['teleop_coral3'] + df['teleop_coral4']
        )
    elif event_key.startswith('2026') and len(df.index) > 0:
        df['auto_fuel_total'] = df['auto_fuel_scored'] + df['auto_fuel_missed']
        df['teleop_fuel_total'] = df['teleop_fuel_scored'] + df['teleop_fuel_missed']
        df['auto_fuel_accuracy'] = df['auto_fuel_scored'] / df['auto_fuel_total'].replace(0, float('nan'))
        df['teleop_fuel_accuracy'] = df['teleop_fuel_scored'] / df['teleop_fuel_total'].replace(0, float('nan'))
    return df


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_matches_data(event_key):
    if event_key is None or event_key == '':
        return pd.DataFrame()
    url = get_matches_data_url(event_key)
    print(url)
    df = pd.read_json(url)
    return df


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_statbot_matches_data(event_key):
    if event_key is None or event_key == '':
        return pd.DataFrame()
    url = f'{base_url}/GetStatboticsMatches?event_key={event_key}'
    print('statbot url', url)
    df = pd.read_json(url)
    return df


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_pit_data(secret_key, event_key, team_key):
    if secret_key is None or event_key is None or secret_key == '' or event_key == '':
        return pd.DataFrame()
    url = get_pit_data_url(secret_key, event_key, team_key)
    print(url)
    pit_data = pd.read_json(url)
    return pit_data


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_opr_data(secret_key, event_key):
    if secret_key is None or event_key is None or secret_key == '' or event_key == '':
        return None
    url = get_opr_data_url(secret_key, event_key)
    print(url)
    try:
        opr_data = pd.read_json(url)
        return opr_data
    except:
        return None


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
    load_event_data.clear()
    load_team_data.clear()
    load_opr_data.clear()
    load_matches_data.clear()
    load_statbot_matches_data.clear()
    load_pit_data.clear()
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
    # Load cookies once
    cookies = get_cookies()
    cookie_manager = st.session_state.get('cookie_manager')

    # Initialize session state
    if 'secret_key' not in st.session_state:
        st.session_state['secret_key'] = ''
    if 'event_key' not in st.session_state:
        st.session_state['event_key'] = ''

    with st.expander('Instructions'):
        st.write(instructions)

    # Show text inputs for keys (pre-filled from cookies/query params)
    secret_key_input = st.text_input("Secret key", value=get_secret_key() or '', key='secret_key_input')
    event_key_input = st.text_input("Event key", value=get_event_key() or '', key='event_key_input')

    col1, col2 = st.columns(2)

    with col1:
        # Save button that sets cookies, query params, and session state
        if st.button('💾 Save Keys', type='primary'):
            if cookie_manager:
                if secret_key_input:
                    sk = secret_key_input.strip()
                    cookie_manager.set('secret_key', sk, expires_at=None, key='set_secret_key')  # Never expires
                    st.query_params['secret_key'] = sk
                    st.session_state.secret_key = sk
                    st.session_state.cookies['secret_key'] = sk
                if event_key_input:
                    ek = event_key_input.strip()
                    cookie_manager.set('event_key', ek, expires_at=None, key='set_event_key')
                    st.query_params['event_key'] = ek
                    st.session_state.event_key = ek
                    st.session_state.cookies['event_key'] = ek
                st.success('Keys saved! They will persist across sessions. Reload the page to confirm.')

    with col2:
        # Clear button to remove saved keys
        if st.button('🗑️ Clear Saved Keys'):
            if cookie_manager:
                cookie_manager.delete('secret_key')
                cookie_manager.delete('event_key')
            st.query_params.clear()
            st.session_state.secret_key = ''
            st.session_state.event_key = ''
            if 'cookies' in st.session_state:
                st.session_state.cookies = {}
            st.success('Keys cleared!')
            st.rerun()

    st.button('Load Data', on_click=load_data)


def main():
    st.set_page_config(
        layout="wide",
    )

    st.title("Trisonics FRC Scouting")

    # Read cookies once per render (before any page code runs)
    init_cookies()

    def _lazy(module, func):
        """Return a wrapper that imports a page function on first use."""
        def wrapper():
            import importlib
            mod = importlib.import_module(module)
            getattr(mod, func)()
        wrapper.__name__ = func
        wrapper.__qualname__ = func
        return wrapper

    pg = st.navigation([
        st.Page(config_page, title='Config'),
        st.Page(_lazy('pages.team_detail', 'team_detail_page'), title='Team Details'),
        st.Page(_lazy('pages.clusters', 'clusters_page'), title='Clustering'),
        st.Page(_lazy('pages.picklist', 'picklist_page'), title='Pick Lists'),
        st.Page(_lazy('pages.match_breakdowns', 'match_breakdowns_page'), title='Match Breakdowns'),
        st.Page(_lazy('pages.what_if', 'what_if_page'), title='What If'),
        st.Page(_lazy('pages.pca', 'pca_page'), title='PCA'),
        st.Page(_lazy('pages.app_status', 'app_status_page'), title='Workspace'),
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
