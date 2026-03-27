import json
import pandas as pd
import streamlit as st
import altair as alt
import urllib.request

from scout import (
    get_event_key, get_secret_key, base_url, load_team_data, pretty_name,
)


def _fetch_rankings(event_key):
    """Fetch rankings from our API (which proxies TBA). Never cached."""
    url = f"{base_url}/GetRankings?event_key={event_key}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return data
    except Exception:
        return None


def rankings_page():
    """Official Event Rankings from TBA."""
    ek = get_event_key()
    sk = get_secret_key()

    if ek is None:
        st.warning("Please set event key in the Config page first.")
        st.stop()

    st.header("Event Rankings")

    data = _fetch_rankings(ek)
    if data is None or 'rankings' not in data or len(data['rankings']) == 0:
        st.warning("No rankings data available yet for this event.")
        st.stop()

    rankings = data['rankings']
    sort_info = data.get('sort_order_info', [])
    extra_info = data.get('extra_stats_info', [])

    # Load team names
    td = load_team_data(ek)
    team_names = {row.number: row['name'] for _, row in td.iterrows()}

    # Build display table
    rows = []
    for r in rankings:
        tn = int(r['team_key'].replace('frc', ''))
        name = team_names.get(tn, '')
        rec = r.get('record', {})
        row = {
            'Rank': r['rank'],
            'Team': f"{tn}",
            'Name': name,
            'W-L-T': f"{rec.get('wins', 0)}-{rec.get('losses', 0)}-{rec.get('ties', 0)}",
            'Played': r.get('matches_played', 0),
            'DQ': r.get('dq', 0),
        }
        # Add sort order columns (game-specific ranking criteria)
        for i, val in enumerate(r.get('sort_orders', [])):
            col_name = sort_info[i]['name'] if i < len(sort_info) else f'Sort {i+1}'
            precision = sort_info[i].get('precision', 2) if i < len(sort_info) else 2
            row[col_name] = round(val, precision)
        # Add extra stats
        for i, val in enumerate(r.get('extra_stats', [])):
            col_name = extra_info[i]['name'] if i < len(extra_info) else f'Extra {i+1}'
            precision = extra_info[i].get('precision', 0) if i < len(extra_info) else 0
            row[col_name] = round(val, int(precision))
        rows.append(row)

    df = pd.DataFrame(rows)

    # Team detail links
    if sk:
        df['Details'] = df['Team'].apply(
            lambda t: f"/team_detail?secret_key={sk}&event_key={ek}&team_detail_number={t}"
        )
        col_config = {
            'Details': st.column_config.LinkColumn('Details', width='small', display_text='View'),
        }
    else:
        col_config = {}

    st.dataframe(df, hide_index=True, width='stretch',
                 column_config=col_config)

    # Ranking score distribution chart
    if sort_info:
        primary_col = sort_info[0]['name']
        if primary_col in df.columns:
            chart = alt.Chart(df).mark_bar().encode(
                x=alt.X('Team:N', sort=df['Team'].tolist(), title='Team (by rank)'),
                y=alt.Y(f'{primary_col}:Q', title=primary_col),
                tooltip=['Rank', 'Team', 'Name', f'{primary_col}:Q'],
            ).properties(height=350, title=f'{primary_col} by Rank')
            st.altair_chart(chart, width='stretch')

    # W-L record chart
    wl_data = []
    for _, r in df.iterrows():
        parts = r['W-L-T'].split('-')
        wl_data.append({'Team': r['Team'], 'Result': 'Wins', 'Count': int(parts[0])})
        wl_data.append({'Team': r['Team'], 'Result': 'Losses', 'Count': int(parts[1])})
        if int(parts[2]) > 0:
            wl_data.append({'Team': r['Team'], 'Result': 'Ties', 'Count': int(parts[2])})
    wl_df = pd.DataFrame(wl_data)

    wl_chart = alt.Chart(wl_df).mark_bar().encode(
        x=alt.X('Team:N', sort=df['Team'].tolist(), title='Team (by rank)'),
        y=alt.Y('Count:Q', title='Matches'),
        color=alt.Color('Result:N',
                        scale=alt.Scale(domain=['Wins', 'Losses', 'Ties'],
                                        range=['#59a14f', '#e15759', '#f28e2b']),
                        title=''),
        tooltip=['Team', 'Result', 'Count'],
        order=alt.Order('Result:N', sort='descending'),
    ).properties(height=300, title='Win-Loss Record')
    st.altair_chart(wl_chart, width='stretch')
