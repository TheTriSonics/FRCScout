import json
import altair as alt
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx

from os.path import exists

pd.options.mode.copy_on_write = True

base_url = "http://localhost:7071/api"
statbot_url = "https://api.statbotics.io/v3"

# --- Shared column sets ---

# Columns that are binary (0/1 per match)
BINARY_COLS = {
    'auto_depot_pickup', 'auto_did_nothing', 'auto_human_station_pickup',
    'auto_middle_pickup', 'fuel_depot_pickup', 'fuel_ground_pickup',
    'fuel_human_pickup', 'teleop_inactive_collected_fuel',
    'teleop_inactive_collected_fuel_lobby',
    'teleop_inactive_collected_fuel_push',
    'teleop_inactive_collected_fuel_refill',
    'teleop_shoot_on_fly', 'win_auto',
}

# Columns to skip from charts (metadata, detail, computed totals)
SKIP_COLS = {
    'team_number', 'match_number', 'event_key', 'secret_team_key',
    'scouter_name', 'timestamp', 'match_notes', 'auto_notes',
    'teleop_active_defense_quality', 'teleop_inactive_defense_quality',
    'volley_accuracy_list', 'volley_missed_list', 'volley_scored_list',
    'auto_fuel_scored', 'auto_fuel_accuracy', 'auto_fuel_missed',
    'teleop_fuel_scored', 'teleop_fuel_accuracy', 'teleop_fuel_missed',
    'endgame_fuel_scored', 'endgame_fuel_accuracy', 'endgame_fuel_missed',
    'total_fuel_made', 'total_fuel_shot', 'total_fuel_missed',
}

# Sections for organizing charts by game phase
SECTIONS = [
    ('Auto', lambda c: c.startswith('auto_')),
    ('Teleop', lambda c: c.startswith('teleop_')),
    ('Endgame', lambda c: c.startswith('endgame_')),
    ('General', lambda c: not c.startswith(('auto_', 'teleop_', 'endgame_'))),
]

# --- Altair theme ---
CHART_COLORS = ['#4e79a7', '#59a14f', '#f28e2b', '#e15759',
                '#76b7b2', '#edc948', '#b07aa1', '#ff9da7',
                '#9c755f', '#bab0ac']

@alt.theme.register('trisonics', enable=True)
def chart_theme():
    return alt.theme.ThemeConfig({
        'config': {
            'range': {'category': CHART_COLORS},
            'bar': {'color': CHART_COLORS[0]},
            'axis': {'labelFontSize': 12, 'titleFontSize': 13},
            'title': {'fontSize': 14},
        }
    })

# --- Scouted-to-OPR column mapping for 2026 ---
# Each entry: (scouted_col, opr_col, label)
# Used for side-by-side comparison and scouting accuracy validation
SCOUTED_OPR_MAP = [
    ('auto_fuel_made', 'hubScore_autoCount', 'Auto Fuel Made'),
    ('teleop_fuel_made', 'hubScore_teleopCount', 'Teleop Fuel Made'),
    ('endgame_fuel_made', 'hubScore_endgameCount', 'Endgame Fuel Made'),
    ('total_fuel_made', 'hubScore_totalCount', 'Total Fuel Made'),
    ('auto_tower_level', 'autoTowerPoints', 'Auto Tower'),
    ('endgame_tower_level', 'endGameTowerPoints', 'Endgame Tower'),
]


def pretty_name(col):
    """Convert column_name to Display Label."""
    return col.replace('_', ' ').title()

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
        different team's data separate. If you want to pool efforts with
        another team just use the same key.

        Once you've entered that and selected an event data will be loaded for
        the event.
"""


def _get_key(name):
    """Get a key value, checking query params -> cookies -> session state."""
    ret = None
    cookies = get_cookies()

    # Priority 1: Query params (from URL - for sharing)
    if name in st.query_params:
        ret = str(st.query_params[name])
    # Priority 2: Cookies (for persistence across sessions)
    elif cookies and name in cookies:
        ret = cookies[name]
    # Priority 3: Session state
    elif name in st.session_state:
        ret = st.session_state[name]

    # Clean and sync
    if ret:
        ret = ret.strip()
        if ret:
            st.session_state[name] = ret

    return ret if ret else None


def get_secret_key():
    """Get secret key, checking query params -> cookies -> session state."""
    return _get_key('secret_key')


def get_event_key():
    """Get event key, checking query params -> cookies -> session state."""
    return _get_key('event_key')


def get_team_list_url(event_key):
    return f"{base_url}/GetTeamsForEvent?event_key={event_key}"


def get_scouted_data_url(secret_key, event_key):
    if secret_key:
        return f"{base_url}/GetResults?secret_team_key={secret_key}&event_key={event_key}"
    else:
        raise ValueError('secret_key needs to be defined')


def get_matches_data_url(event_key):
    return f"{base_url}/GetMatchesForEvent?event_key={event_key}"


def get_opr_data_url(secret_key, event_key):
    return f"{base_url}/GetOPRData?secret_team_key={secret_key}&event_key={event_key}"


def get_pit_data_url(secret_key, event_key, team_key):
    return f"{base_url}/GetPitResults?secret_team_key={secret_key}&event_key={event_key}&team_key={team_key}"


def _keys_missing(*args):
    """Return True if any of the given keys are None or empty."""
    return any(a is None or a == '' for a in args)


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_team_data(event_key):
    if _keys_missing(event_key):
        return pd.DataFrame()
    url = get_team_list_url(event_key)
    df = pd.read_json(url)
    return df

@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_event_data(secret_key, event_key):
    if _keys_missing(secret_key, event_key):
        return pd.DataFrame()
    url = get_scouted_data_url(secret_key, event_key)
    df = pd.read_json(url)
    if len(df.index) > 0:
        # Normalize legacy column names
        if 'scouting_team' in df.columns:
            df.rename(columns={'scouting_team': 'team_number'}, inplace=True)
        if 'match_key' in df.columns:
            df.rename(columns={'match_key': 'match_number'}, inplace=True)
    if event_key.startswith('2025') and len(df.index) > 0:
        df['auto_coral_total'] = (
            df['auto_coral1'] + df['auto_coral2'] +
            df['auto_coral3'] + df['auto_coral4']
        )

        df['teleop_coral_total'] = (
            df['teleop_coral1'] + df['teleop_coral2'] +
            df['teleop_coral3'] + df['teleop_coral4']
        )
    elif event_key.startswith('2026') and len(df.index) > 0:
        # *_fuel_scored is shots attempted, *_fuel_accuracy is hit %
        # Compute actual makes and misses per phase
        for phase in ['auto', 'teleop', 'endgame']:
            shot_col = f'{phase}_fuel_scored'
            acc_col = f'{phase}_fuel_accuracy'
            if shot_col in df.columns and acc_col in df.columns:
                df[f'{phase}_fuel_made'] = (df[shot_col] * df[acc_col] / 100).round().astype(int)
                df[f'{phase}_fuel_missed'] = df[shot_col] - df[f'{phase}_fuel_made']
        # Totals across all phases
        made_cols = [c for c in df.columns if c.endswith('_fuel_made')]
        df['total_fuel_made'] = df[made_cols].sum(axis=1)
        shot_cols = [c for c in ['auto_fuel_scored', 'teleop_fuel_scored', 'endgame_fuel_scored'] if c in df.columns]
        df['total_fuel_shot'] = df[shot_cols].sum(axis=1)
        df['total_fuel_missed'] = df['total_fuel_shot'] - df['total_fuel_made']
    return df


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_matches_data(event_key):
    if _keys_missing(event_key):
        return pd.DataFrame()
    url = get_matches_data_url(event_key)
    df = pd.read_json(url)
    return df


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_statbot_matches_data(event_key):
    if _keys_missing(event_key):
        return pd.DataFrame()
    url = f'{base_url}/GetStatboticsMatches?event_key={event_key}'
    df = pd.read_json(url)
    return df


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_pit_data(secret_key, event_key, team_key):
    if _keys_missing(secret_key, event_key):
        return pd.DataFrame()
    url = get_pit_data_url(secret_key, event_key, team_key)
    pit_data = pd.read_json(url)
    return pit_data


@st.cache_data(ttl=300, max_entries=10, show_spinner=False)
def load_opr_data(secret_key, event_key):
    if _keys_missing(secret_key, event_key):
        return None
    url = get_opr_data_url(secret_key, event_key)
    try:
        opr_data = pd.read_json(url)
        return opr_data
    except Exception:
        return None


def _get_pick_list(key):
    """Return the pick list stored in session state, or an empty list."""
    return st.session_state.get(key, [])


def get_dnp():
    return _get_pick_list('pick_list_dnp')


def get_fsp():
    return _get_pick_list('pick_list_fsp')


def get_dnp_nums():
    """Return set of DNP team numbers."""
    return {t[0] for t in get_dnp()}


def get_fsp_nums():
    """Return set of first-pick team numbers."""
    return {t[0] for t in get_fsp()}


def team_status_label(team_num):
    """Return a status suffix for display: ' [DNP]', ' [1st]', or ''."""
    if team_num in get_dnp_nums():
        return ' [DNP]'
    elif team_num in get_fsp_nums():
        return ' [1st]'
    return ''


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

    event_data = load_event_data(secret_key, event_key)
    if len(event_data.index) > 0:
        st.success("Scouted data loaded!")
    else:
        st.error("Scouting data not found.")
        all_loaded = False

    team_data = load_team_data(event_key)
    if len(team_data.index) > 0:
        st.success("Event team list loaded!")
    else:
        st.error("Event team list failed.")
        all_loaded = False

    opr_data = load_opr_data(secret_key, event_key)
    if opr_data is not None and len(opr_data.index) > 0:
        st.success("OPR calculations loaded")
    else:
        st.warning("OPR calculation not available yet.")
        all_loaded = False

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
        if st.button('Save Keys', type='primary'):
            if cookie_manager:
                if secret_key_input:
                    sk = secret_key_input.strip()
                    cookie_manager.set('secret_key', sk, expires_at=None, key='set_secret_key')
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
        if st.button('Clear Saved Keys'):
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
        st.Page(_lazy('pages.team_search', 'team_search_page'), title='Team Search'),
        st.Page(_lazy('pages.heatmap', 'heatmap_page'), title='Heatmap'),
        st.Page(_lazy('pages.clusters', 'clusters_page'), title='Clustering'),
        st.Page(_lazy('pages.picklist', 'picklist_page'), title='Pick Lists'),
        st.Page(_lazy('pages.head_to_head', 'head_to_head_page'), title='Head to Head'),
        st.Page(_lazy('pages.match_breakdowns', 'match_breakdowns_page'), title='Match Breakdowns'),
        st.Page(_lazy('pages.what_if', 'what_if_page'), title='Alliance Builder'),
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
