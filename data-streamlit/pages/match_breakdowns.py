import urllib
import streamlit as st
import pandas as pd

from scout import (
    load_matches_data, load_opr_data, load_team_data, get_event_key,
    load_event_data, load_statbot_matches_data, get_secret_key
)

def match_breakdowns_page():
    """Match Breakdowns Page"""
    
    pd.options.mode.copy_on_write = True
    
    
    sk = get_secret_key()
    ek = get_event_key()
    
    td = None
    matches = None
    if ek:
        event = load_event_data(get_secret_key(), get_event_key())
        td = load_team_data(get_event_key())
    
    st.header('Match Breakdowns')
    with st.expander('Instructions'):
        st.write("""
        TODO
        """)
    
    event = load_event_data(sk, ek)
    # st.dataframe(event)
    
    matches = load_matches_data(ek)
    types = matches.comp_level.unique()
    team_data = load_team_data(ek)
    
    qm_filter = st.checkbox('Qualifying Matches', True)
    po_filter = st.checkbox('Playoff Matches', True)
    
    match_types = []
    if qm_filter:
        match_types.append('qm')
    if po_filter:
        for level in ['sf', 'f']:
            match_types.append(level)
    print(types)
    print(match_types)
    team_filter = st.multiselect('Team', team_data, placeholder='Select a team')
    
    try:
        oprdata = load_opr_data(sk, ek)
        opr_totalpoints = oprdata[['teamNumber', 'totalPoints']]
    except urllib.error.HTTPError:
        oprdata = None
        opr_totalpoints = None
    matches = matches[matches['comp_level'].isin(match_types)]
    # Order the matches dataframe by the match_number column
    matches = matches.sort_values(by='match_number').reset_index(drop=True)
    # st.dataframe(matches)
    
    if len(matches.index) == 0:
        st.subheader('No match data available yet.')
    else:
        n1 = pd.json_normalize(matches['alliances'])
        bluen2 = pd.json_normalize(n1['blue.team_keys'])
        redn2 = pd.json_normalize(n1['red.team_keys'])
    
        blueteams = pd.DataFrame(n1['blue.team_keys'].explode())
        redteams = pd.DataFrame(n1['red.team_keys'].explode())
        blueteams['blue.team_keys'] = blueteams['blue.team_keys'].str.replace('frc', '').astype(int)
        redteams['red.team_keys'] = redteams['red.team_keys'].str.replace('frc', '').astype(int)
        blueteams['robot_num'] = blueteams.groupby(blueteams.index).rank()
        redteams['robot_num'] = redteams.groupby(redteams.index).rank()
        pblue = blueteams.pivot(columns='robot_num', values='blue.team_keys')
        pred = redteams.pivot(columns='robot_num', values='red.team_keys')
        pblue.columns = ['blue1', 'blue2', 'blue3']
        pred.columns = ['red1', 'red2', 'red3']
        matches = matches.join(pblue).join(pred)
    
        if team_filter:
            print(team_filter)
            matches = matches[(matches['red1'].isin(team_filter)) |
                        (matches['red2'].isin(team_filter)) |
                        (matches['red3'].isin(team_filter)) |
                        (matches['blue1'].isin(team_filter)) |
                        (matches['blue2'].isin(team_filter)) |
                        (matches['blue3'].isin(team_filter))]
    
        if opr_totalpoints is not None:
            for color in ['blue', 'red']:
                for index in [1, 2, 3]:
                    matches = matches.join(
                        opr_totalpoints.set_index('teamNumber'),
                        on=f'{color}{index}'
                    )
                    matches.rename(
                        columns={'totalPoints': f'{color}{index}_totalPoints'},
                        inplace=True
                    )
        # st.dataframe(matches)
    
        statbotics = load_statbot_matches_data(get_event_key())
        if statbotics.index.size == 0:
            st.subheader('No statbotics data available yet.')
            pred_detail = None
            actual_detail = None
        else:
            preds = statbotics[['comp_level', 'match_number', 'pred']]
            preds = preds[preds['comp_level'] == 'qm']
            pred_detail = preds.join(pd.json_normalize(preds['pred']))
    
            actual = statbotics[['comp_level', 'match_number', 'result']]
            actual = actual[actual['comp_level'] == 'qm']
            actual_detail = actual.join(pd.json_normalize(actual['result']))
        # st.dataframe(pred_detail)
    
        if pred_detail is not None:
            matches = matches.join(pred_detail.set_index('match_number')
                                            .add_suffix('_pred'),
                                on='match_number')
    
        if actual_detail is not None:
            matches = matches.join(actual_detail.set_index('match_number')
                                                .add_suffix('_actual'),
                                on='match_number')
    
    
        for panda_idx, match in matches.iterrows():
            with st.container(border=8):
                # Display the match number
                st.subheader(f"Match {match['match_number']}")
                red, blue = st.columns(2)
                stats = {}
                for container, color in zip([red, blue], ['red', 'blue']):
                    with container:
                        with st.container(border=True):
                            alliance_opr_total = 0
                            team_nums = []
                            total_point_oprs = []
                            for bot in [1, 2, 3]:
                                team_num = match[f'{color}{bot}']
                                team_nums.append(team_num)
                                if opr_totalpoints is not None:
                                    opr_total = match[f'{color}{bot}_totalPoints']
                                else:
                                    opr_total = 0
                                total_point_oprs.append(opr_total)
                                alliance_opr_total += opr_total
                            pred_winner, actual_winner, redpct = 'none', 'none', 0
                            if 'winner_pred' in match.keys():
                                pred_winner = match['winner_pred'] == color
                                actual_winner = match['winner_actual'] == color
                                redpct = match['red_win_prob_pred'] * 100
                            pct = redpct if color == 'red' else 100 - redpct
                            show_star = '*' if actual_winner else ''
                            st.markdown(f"""
                                ### {show_star}{color.capitalize()} ({pct:.1f}%)
                            """)
                            team_breakdown = pd.DataFrame({
                                'Team': team_nums,
                                'TP OPR': total_point_oprs
                            }).set_index('Team')
                            st.table(team_breakdown.style.format(precision=1))
                            score_pred, score_actual = 0, 0
                            if f'{color}_score_pred' in match.keys():
                                score_pred = match[f'{color}_score_pred']
                                score_actual = match[f'{color}_score_actual']
                            stats[color] = [
                                alliance_opr_total,
                                score_pred,
                                score_actual
                            ]
                # JJB: I'm not thrilled with my indent level above
                misc_breakdown = pd.DataFrame({
                    'Label': ['Total TP OPR',
                            'Score Predicted',
                            'Score Actual'],
                    'Red': stats['red'],
                    'Blue': stats['blue'],
                }).set_index('Label')
                st.table(misc_breakdown.style.format(precision=1))
