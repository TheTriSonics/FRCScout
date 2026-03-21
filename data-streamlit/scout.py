import json
import os
import altair as alt
import pandas as pd
import streamlit as st

from os.path import exists

pd.options.mode.copy_on_write = True

_DEFAULT_API = "https://trisonics-scouting-api.azurewebsites.net/api"
base_url = os.environ.get("SCOUT_API_URL", _DEFAULT_API)
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

def _get_key(name):
    """Get a key value. Priority: query params > session state.
    Always syncs session state values up to query params so the URL
    carries keys across page navigations."""
    # Query params are the source of truth (persist in URL, shareable)
    if name in st.query_params:
        val = str(st.query_params[name]).strip()
        if val:
            st.session_state[name] = val
            return val
    # Fall back to session state (set by config.json or prior interaction)
    val = st.session_state.get(name, '')
    if isinstance(val, str):
        val = val.strip()
    if val:
        # Sync to query params so URL always reflects current keys
        st.query_params[name] = val
        return val
    return None


def _set_key(name, value):
    """Set a key in both session state and query params."""
    value = str(value).strip()
    if value:
        st.session_state[name] = value
        st.query_params[name] = value
    else:
        st.session_state.pop(name, None)
        if name in st.query_params:
            del st.query_params[name]


def get_secret_key():
    return _get_key('secret_key')


def get_event_key():
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


@st.cache_data(ttl=86400, show_spinner=False)
def load_events(year):
    """Load event list from TBA via our API."""
    try:
        url = f"{base_url}/GetEvents?year={year}"
        df = pd.read_json(url)
        if len(df.index) > 0 and 'key' in df.columns and 'name' in df.columns:
            return df[['key', 'name', 'state_prov']].sort_values('name').reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


def load_team_data(event_key):
    if _keys_missing(event_key):
        return pd.DataFrame()
    url = get_team_list_url(event_key)
    df = pd.read_json(url)
    return df

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


def load_matches_data(event_key):
    if _keys_missing(event_key):
        return pd.DataFrame()
    url = get_matches_data_url(event_key)
    df = pd.read_json(url)
    return df


def load_statbot_matches_data(event_key):
    if _keys_missing(event_key):
        return pd.DataFrame()
    url = f'{base_url}/GetStatboticsMatches?event_key={event_key}'
    df = pd.read_json(url)
    return df


def load_pit_data(secret_key, event_key, team_key):
    if _keys_missing(secret_key, event_key):
        return pd.DataFrame()
    url = get_pit_data_url(secret_key, event_key, team_key)
    pit_data = pd.read_json(url)
    return pit_data


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
    """Config page — set secret key and event, changes take effect immediately."""
    with st.expander('Instructions'):
        st.write("""
        Enter your team's secret key and select an event. Changes take
        effect immediately — just navigate to another page. Keys are stored
        in the URL so you can bookmark or share the link.
        """)

    # --- Secret Key ---
    def _on_secret_change():
        _set_key('secret_key', st.session_state._sk_input)

    st.text_input(
        "Secret key",
        value=get_secret_key() or '',
        key='_sk_input',
        on_change=_on_secret_change,
    )

    # --- Event Key: text input + browser ---
    def _on_event_change():
        _set_key('event_key', st.session_state._ek_input)

    st.text_input(
        "Event key",
        value=get_event_key() or '',
        key='_ek_input',
        on_change=_on_event_change,
    )

    # Event browser from TBA
    with st.expander("Browse events"):
        year = st.selectbox("Year", [2026, 2025], key='event_year')
        events = load_events(year)
        if len(events.index) > 0:
            event_options = [(row.key, f"{row['name']} ({row.state_prov})") for _, row in events.iterrows()]
            selected_event = st.selectbox(
                "Select an event",
                event_options,
                format_func=lambda x: x[1],
                key='event_picker',
            )
            if selected_event and st.button("Use this event"):
                _set_key('event_key', selected_event[0])
                st.rerun()

    # --- Status ---
    sk = get_secret_key()
    ek = get_event_key()
    if sk and ek:
        st.success(f"Ready — secret key: `{sk[:4]}...`, event: `{ek}`")
    else:
        missing = []
        if not sk:
            missing.append("secret key")
        if not ek:
            missing.append("event key")
        st.warning(f"Missing: {', '.join(missing)}")

    st.button('Reload All Data', on_click=load_data)


def main():
    st.set_page_config(
        layout="wide",
    )

    st.title("Trisonics FRC Scouting")

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
        st.Page(config_page, title='Config', url_path='config'),
        st.Page(_lazy('pages.rankings', 'rankings_page'), title='Rankings', url_path='rankings'),
        st.Page(_lazy('pages.team_detail', 'team_detail_page'), title='Team Details', url_path='team_detail'),
        st.Page(_lazy('pages.team_search', 'team_search_page'), title='Team Search', url_path='team_search'),
        st.Page(_lazy('pages.heatmap', 'heatmap_page'), title='Heatmap', url_path='heatmap'),
        st.Page(_lazy('pages.clusters', 'clusters_page'), title='Clustering', url_path='clusters'),
        st.Page(_lazy('pages.picklist', 'picklist_page'), title='Pick Lists', url_path='picklist'),
        st.Page(_lazy('pages.head_to_head', 'head_to_head_page'), title='Head to Head', url_path='head_to_head'),
        st.Page(_lazy('pages.match_breakdowns', 'match_breakdowns_page'), title='Match Breakdowns', url_path='match_breakdowns'),
        st.Page(_lazy('pages.scouting_accuracy', 'scouting_accuracy_page'), title='Scouting Accuracy', url_path='scouting_accuracy'),
        st.Page(_lazy('pages.what_if', 'what_if_page'), title='Alliance Builder', url_path='alliance_builder'),
        st.Page(_lazy('pages.pca', 'pca_page'), title='PCA', url_path='pca'),
        st.Page(_lazy('pages.app_status', 'app_status_page'), title='Workspace', url_path='workspace'),
    ])
    pg.run()


def load_dev_config():
    global base_url
    cfg = 'config.json'
    if exists(cfg):
        with open(cfg) as f:
            obj = json.load(f)
            # Pull api_url out before updating session state
            if 'api_url' in obj:
                base_url = obj.pop('api_url')
            st.session_state.update(obj)


if __name__ == '__main__':
    load_dev_config()
    main()
