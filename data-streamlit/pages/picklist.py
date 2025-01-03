import streamlit as st

from scout import (
    load_team_data, get_event_key, fix_session
)

def _make_team_label(team_data, team_number):
    team_name = team_data.loc[team_data.number == team_number, 'name'].values[0]
    return f'{team_number} ({team_name})'

def pick_panel(team_data):
    st.header('Pick Lists')
    dnp_teamlist = zip(
        team_data.number, team_data.name
    )
    fsp_teamlist = zip(
        team_data.number, team_data.name
    )
    # st.write('--- begin dnp --')
    # for dnp in dnp_teamlist:
    #     st.write(dnp)
    # st.write('--- end dnp --')
    dnp_teams = st.multiselect('Do NOT Pick Teams', dnp_teamlist,
                               format_func=lambda x: _make_team_label(team_data, x),
                               key='pick_list_dnp')
    fsp_teams = st.multiselect('First Pick Teams', fsp_teamlist,
                               format_func=lambda x: _make_team_label(team_data, x),
                               key='pick_list_fsp')
    return dnp_teams, fsp_teams


fix_session()
team_data = load_team_data(get_event_key())
pick_panel(team_data)
