import streamlit as st

from scout import load_team_data, get_event_key, fix_session


fix_session()

td = load_team_data(get_event_key())


def avail_teams():
    selected_teams = []
    for x in range(8):
        try:
            selected_teams += alliance[x]['team_select']
        except KeyError:
            pass  # Ignore
    all_teams = [(row.number, row['name']) for idx, row in td.iterrows()]
    rem_teams = [t for t in all_teams if t not in selected_teams]
    return rem_teams


alliance = {}
for x in range(8):
    alliance[x] = {}
    with st.container():
        st.subheader(f'Alliance {x+1}')
        alliance[x]['team_select'] = st.multiselect(
            'Members', avail_teams(),
            max_selections=3,
            format_func=lambda x: f'{x[0]} ({x[1]})',
            key=f'alliance_{x}_multiselect'
        )
        st.info('Footer')
