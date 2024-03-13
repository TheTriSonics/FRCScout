import streamlit as st

from scout import (
    load_matches_data, load_opr_data, load_team_data, get_event_key, fix_session,
    load_event_data,
    get_secret_key
)


fix_session()

td = None
matches = None
if get_event_key():
    event = load_event_data(get_secret_key(), get_event_key())
    td = load_team_data(get_event_key())


def avail_teams():
    if td is None:
        return []
    selected_teams = []
    for x in range(8):
        try:
            selected_teams += alliance[x]['team_select']
        except KeyError:
            pass  # Ignore
    all_teams = [(row.number, row['name']) for idx, row in td.iterrows()]
    rem_teams = [t for t in all_teams if t not in selected_teams]
    return rem_teams


st.header('Match Breakdowns')
with st.expander('Instructions'):
    st.write("""
    TODO
    """)

event = load_event_data('4003data', '2024milac')
# st.dataframe(event)

matches = load_matches_data('2024milac')

newcols = ['red1', 'red2', 'red3', 'blue1', 'blue2', 'blue3', 'red1_opr']
for c in newcols:
    matches[c] = [''] * len(matches)
oprdata = load_opr_data('4003data', '2024milac')
st.dataframe(oprdata)
matches = matches[matches['comp_level'] == 'qm']
# Order the matches dataframe by the match_number column
matches = matches.sort_values(by='match_number').reset_index(drop=True)
# st.dataframe(matches)

for panda_idx, match in matches.iterrows():
    with st.container():
        # Display the match number
        st.subheader(f"Match {match['match_number']}")
        red, blue = st.columns(2)
        for container, color in zip([red, blue], ['red', 'blue']):
            with container:
                st.subheader(color.capitalize())
                tks = match['alliances'][color]['team_keys']
                for team_index, tk in enumerate(tks):
                    colname = f'{color}{team_index+1}\n'
                    team_num = tk.replace('frc', '')
                    # Select row from oprdata that matches a teamNumber
                    matches.loc[panda_idx, colname] = team_num
                    print('loking for', team_num)
                    opr_score = (
                        oprdata[oprdata['teamNumber'] == int(team_num)]['totalPoints']
                    ).item()
                    # matches.loc[panda_idx, 'red1_opr'] = str(opr)
                    st.write(team_num, opr_score)


st.dataframe(matches)