import pandas as pd
import streamlit as st
import altair as alt

import json as _json
import urllib.request

from scout import (
    load_opr_data, load_team_data, load_event_data, load_pit_data,
    load_parallel, get_event_key, get_secret_key, pretty_name, base_url,
)
from views.rankings import _fetch_rankings


def _load_saved_results(sk, ek):
    """Fetch saved scouting results from the API and seed session_state.
    Only runs once per session to avoid overwriting in-progress edits."""
    if st.session_state.get('_scouting_results_loaded'):
        return
    st.session_state['_scouting_results_loaded'] = True
    try:
        url = f'{base_url}/GetScoutingResults?secret_key={sk}&event_key={ek}'
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        if data and len(data) > 0:
            doc = data[0]
            for team in doc.get('teams', []):
                tn = team['team_number']
                if team.get('dnp'):
                    st.session_state[f'_pick_rank_{tn}'] = 'DNP'
                elif team.get('decline'):
                    st.session_state[f'_pick_rank_{tn}'] = 'Decline'
                elif team.get('ranking') is not None:
                    st.session_state[f'_pick_rank_{tn}'] = str(team['ranking'])
                notes = team.get('notes', '')
                if notes:
                    st.session_state[f'_pick_notes_{tn}'] = notes
    except Exception as e:
        st.warning(f"Could not load saved rankings: {e}")


def _get_ranked_teams(team_names):
    """Build a list of ranked teams from session_state for the summary table."""
    teams = []
    for k, v in sorted(st.session_state.items()):
        if not k.startswith('_pick_rank_'):
            continue
        tn = int(k.replace('_pick_rank_', ''))
        notes = st.session_state.get(f'_pick_notes_{tn}', '')
        teams.append({
            'Pick': int(v) if v not in ('Decline', 'DNP') else v,
            'Team': tn,
            'Name': team_names.get(tn, ''),
            'Notes': notes.strip() if notes else '',
        })
    # Sort: numeric picks first, then Decline/DNP
    teams.sort(key=lambda t: (isinstance(t['Pick'], str), t['Pick'] if isinstance(t['Pick'], int) else 0))
    return teams


def fuel_opr_page():
    """2026 Rebuilt — Scouting Breakdown"""
    sk = get_secret_key()
    ek = get_event_key()

    if sk is None or ek is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    st.header("Scouting Breakdown")
    st.caption("2026 Rebuilt — fuel scored by phase, ranked by total OPR")

    opr_data = load_opr_data(sk, ek)
    if opr_data is None or len(opr_data.index) == 0:
        st.warning("No OPR data available yet. Qualification matches need to be played first.")
        st.stop()

    td = load_team_data(ek)
    team_names = {row.number: row['name'] for _, row in td.iterrows()}

    # Check for required columns
    required = ['hubScore_autoCount', 'hubScore_teleopCount', 'hubScore_endgameCount', 'teamNumber']
    missing = [c for c in required if c not in opr_data.columns]
    if missing:
        st.warning(f"OPR data missing fuel columns: {', '.join(missing)}")
        st.stop()

    # Load saved results from API (once per session)
    _load_saved_results(sk, ek)

    # Fetch official event rankings from TBA
    rankings_data = _fetch_rankings(ek)
    official_ranks = {}
    if rankings_data and 'rankings' in rankings_data:
        for r in rankings_data['rankings']:
            tn = int(r['team_key'].replace('frc', ''))
            official_ranks[tn] = r['rank']

    # Build display data
    df = opr_data[['teamNumber', 'hubScore_autoCount', 'hubScore_teleopCount', 'hubScore_endgameCount']].copy()
    df['teamNumber'] = df['teamNumber'].astype(int)
    df['total'] = df['hubScore_autoCount'] + df['hubScore_teleopCount'] + df['hubScore_endgameCount']
    df['team_name'] = df['teamNumber'].apply(lambda t: team_names.get(t, ''))
    df = df.sort_values('total', ascending=False).reset_index(drop=True)
    df['rank'] = df['teamNumber'].map(official_ranks)
    df['team_label'] = df.apply(
        lambda r: f"{r['teamNumber']} · #{int(r['rank'])}" if pd.notna(r['rank']) else str(r['teamNumber']),
        axis=1,
    )

    # ---- Our Pick Rankings summary table ----
    ranked_teams = _get_ranked_teams(team_names)
    if ranked_teams:
        st.markdown("**Our Pick Rankings**")
        html = (
            '<table style="width:100%;border-collapse:collapse;font-size:14px">'
            '<tr style="border-bottom:2px solid #555;text-align:left">'
            '<th style="width:50px;padding:4px">Pick</th>'
            '<th style="width:60px;padding:4px">Team</th>'
            '<th style="width:140px;padding:4px">Name</th>'
            '<th style="padding:4px">Notes</th></tr>'
        )
        for r in ranked_teams:
            html += (
                f'<tr style="border-bottom:1px solid #333">'
                f'<td style="padding:4px;white-space:nowrap">{r["Pick"]}</td>'
                f'<td style="padding:4px;white-space:nowrap">{r["Team"]}</td>'
                f'<td style="padding:4px;white-space:nowrap">{r["Name"]}</td>'
                f'<td style="padding:4px">{r["Notes"]}</td></tr>'
            )
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)

    # Toggle to hide already-ranked teams from the chart
    ranked_team_nums = {t['Team'] for t in ranked_teams} if ranked_teams else set()
    hide_ranked = st.toggle("Hide ranked teams from chart", value=False, key='_hide_ranked') if ranked_teams else False

    if hide_ranked:
        df = df[~df['teamNumber'].isin(ranked_team_nums)].reset_index(drop=True)
        team_order = df['team_label'].tolist()
        melted = df.melt(
            id_vars=['team_label', 'team_name', 'total'],
            value_vars=['hubScore_autoCount', 'hubScore_teleopCount', 'hubScore_endgameCount'],
            var_name='phase',
            value_name='fuel_opr',
        )
        melted['phase'] = melted['phase'].map({
            'hubScore_autoCount': 'Auto',
            'hubScore_teleopCount': 'Teleop',
            'hubScore_endgameCount': 'Endgame',
        })
    else:
        team_order = df['team_label'].tolist()
        melted = df.melt(
            id_vars=['team_label', 'team_name', 'total'],
            value_vars=['hubScore_autoCount', 'hubScore_teleopCount', 'hubScore_endgameCount'],
            var_name='phase',
            value_name='fuel_opr',
        )
        melted['phase'] = melted['phase'].map({
            'hubScore_autoCount': 'Auto',
            'hubScore_teleopCount': 'Teleop',
            'hubScore_endgameCount': 'Endgame',
        })

    selection = alt.selection_point(name="team_select", fields=['team_label'])

    chart = alt.Chart(melted).mark_bar().encode(
        y=alt.Y('team_label:N', sort=team_order, title='Team'),
        x=alt.X('fuel_opr:Q', title='Fuel OPR'),
        color=alt.Color('phase:N',
                        sort=['Auto', 'Teleop', 'Endgame'],
                        scale=alt.Scale(
                            domain=['Auto', 'Teleop', 'Endgame'],
                            range=['#4e79a7', '#59a14f', '#f28e2b']),
                        title='Phase'),
        order=alt.Order('phase:N', sort='ascending'),
        opacity=alt.condition(selection, alt.value(1), alt.value(0.3)),
        tooltip=[
            alt.Tooltip('team_label:N', title='Team'),
            alt.Tooltip('team_name:N', title='Name'),
            alt.Tooltip('phase:N', title='Phase'),
            alt.Tooltip('fuel_opr:Q', format='.1f', title='Fuel OPR'),
            alt.Tooltip('total:Q', format='.1f', title='Total'),
        ],
    ).add_params(selection).properties(height=max(len(team_order) * 25, 400))

    event = st.altair_chart(chart, width='stretch', on_select='rerun')

    # Summary table
    with st.expander("Details"):
        table = df[['team_label', 'team_name', 'hubScore_autoCount',
                     'hubScore_teleopCount', 'hubScore_endgameCount', 'total']].copy()
        table.columns = ['Team', 'Name', 'Auto', 'Teleop', 'Endgame', 'Total']
        st.dataframe(
            table.style.format({'Auto': '{:.1f}', 'Teleop': '{:.1f}',
                                'Endgame': '{:.1f}', 'Total': '{:.1f}'}),
            hide_index=True, use_container_width=True,
        )

    # --- Team detail on click ---
    selected = event.selection.get('team_select', []) if event else []
    if selected:
        st.session_state['_selected_team_label'] = selected[0]['team_label']
    if '_selected_team_label' not in st.session_state:
        return

    team_num = int(st.session_state['_selected_team_label'].split('·')[0].strip())
    team_name = team_names.get(team_num, '')
    rank_val = official_ranks.get(team_num, '?')

    st.divider()
    st.subheader(f"Ranked {rank_val} — Team {team_num}  ·  {team_name}")

    # ---- Pick Ranking ----
    # _pick_* keys = committed (saved) data, shown in summary table
    # _edit_* keys = widget state, per-team so Streamlit creates fresh widgets
    save_rank_key = f'_pick_rank_{team_num}'
    save_notes_key = f'_pick_notes_{team_num}'
    edit_rank_key = f'_edit_rank_{team_num}'
    edit_notes_key = f'_edit_notes_{team_num}'

    taken = set()
    for k, v in st.session_state.items():
        if k.startswith('_pick_rank_') and k != save_rank_key and v not in ('Decline', 'DNP'):
            taken.add(v)

    saved_rank = st.session_state.get(save_rank_key, None)
    rank_options = [
        r for r in [str(i) for i in range(1, 24)]
        if r not in taken or r == saved_rank
    ] + ['Decline', 'DNP']

    # Seed edit keys from saved data on first view of this team
    if edit_rank_key not in st.session_state:
        st.session_state[edit_rank_key] = saved_rank if saved_rank in rank_options else rank_options[0]
    if edit_notes_key not in st.session_state:
        st.session_state[edit_notes_key] = st.session_state.get(save_notes_key, '')

    col_rank, col_save = st.columns([2, 1])
    with col_rank:
        st.selectbox("Pick Number", rank_options, key=edit_rank_key)
    st.text_area(
        "Summary Notes", height=120,
        placeholder="Your assessment of this team based on scouting data...",
        key=edit_notes_key,
    )
    with col_save:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button("Save", key=f'_pick_save_{team_num}', type='primary'):
            # Commit edit state to saved state
            st.session_state[save_rank_key] = st.session_state[edit_rank_key]
            st.session_state[save_notes_key] = st.session_state[edit_notes_key].strip()

            # Build payload for all ranked teams
            teams = []
            for k, v in sorted(st.session_state.items()):
                if not k.startswith('_pick_rank_'):
                    continue
                tn = int(k.replace('_pick_rank_', ''))
                notes_val = st.session_state.get(f'_pick_notes_{tn}', '')
                is_decline = v == 'Decline'
                is_dnp = v == 'DNP'
                teams.append({
                    'team_number': tn,
                    'ranking': int(v) if v not in ('Decline', 'DNP') else None,
                    'decline': is_decline,
                    'dnp': is_dnp,
                    'notes': notes_val.strip() if notes_val else '',
                })
            teams.sort(key=lambda t: (t['ranking'] is None, t['ranking'] or 0))
            payload = {
                'event_key': ek,
                'secret_key': sk,
                'teams': teams,
            }
            try:
                req_data = _json.dumps(payload).encode('utf-8')
                http_req = urllib.request.Request(
                    f'{base_url}/PostScoutingResults',
                    data=req_data,
                    headers={'Content-Type': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(http_req, timeout=15) as resp:
                    resp.read()
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")

    with st.spinner(f"Loading data for Team {team_num}..."):
        scouted, pit = load_parallel(
            (load_event_data, sk, ek),
            (load_pit_data, sk, ek, team_num),
        )

    # ---- Match Notes ----
    tdf = scouted[scouted['team_number'] == team_num].sort_values('match_number')
    note_cols = [c for c in ['match_notes', 'auto_notes'] if c in tdf.columns]
    has_notes = any(
        tdf[c].dropna().astype(str).str.strip().str.len().sum() > 0
        for c in note_cols
    )

    if has_notes:
        st.markdown("**Match Notes**")
        rows = []
        for _, mrow in tdf.iterrows():
            match_num = mrow.get('match_number', '?')
            scouter = mrow.get('scouter_name', '')
            auto = str(mrow.get('auto_notes', '')).strip() if 'auto_notes' in note_cols else ''
            match = str(mrow.get('match_notes', '')).strip() if 'match_notes' in note_cols else ''
            if auto or match:
                rows.append({
                    'Match': match_num,
                    'Scouter': scouter,
                    'Auto Notes': auto,
                    'Match Notes': match,
                })
        if rows:
            html = (
                '<table style="width:100%;border-collapse:collapse;font-size:14px">'
                '<tr style="border-bottom:2px solid #555;text-align:left">'
                '<th style="width:50px;padding:4px">Match</th>'
                '<th style="width:100px;padding:4px">Scouter</th>'
                '<th style="padding:4px">Auto Notes</th>'
                '<th style="padding:4px">Match Notes</th></tr>'
            )
            for r in rows:
                html += (
                    f'<tr style="border-bottom:1px solid #333">'
                    f'<td style="padding:4px;white-space:nowrap">{r["Match"]}</td>'
                    f'<td style="padding:4px;white-space:nowrap">{r["Scouter"]}</td>'
                    f'<td style="padding:4px">{r["Auto Notes"]}</td>'
                    f'<td style="padding:4px">{r["Match Notes"]}</td></tr>'
                )
            html += '</table>'
            st.markdown(html, unsafe_allow_html=True)
    else:
        st.caption("No match notes recorded.")

    # ---- Pit Scouting ----
    if pit is not None and len(pit.index) > 0:
        skip_fields = {
            'scouter_name', 'secret_team_key', 'event_key',
            'team_number', 'timestamp', 'image_names',
        }
        for pit_idx in range(len(pit.index)):
            pit_row = pit.iloc[pit_idx]
            scouter = pit_row.get('scouter_name', 'Unknown')
            ts = pit_row.get('timestamp', '')
            st.markdown(f"**Pit Scout:** {scouter} — {ts}")

            display_rows = []
            for field in pit.columns:
                if field in skip_fields:
                    continue
                val = pit_row.get(field)
                if val is None or (isinstance(val, str) and not val.strip()):
                    continue
                label = pretty_name(field)
                is_bool = isinstance(val, bool) or (
                    val in (0, 1) and field not in ('fuel_capacity', 'hanging_level')
                )
                display_rows.append({
                    'Field': label,
                    'Value': ('Yes' if val else 'No') if is_bool else str(val),
                })
            if display_rows:
                mid = (len(display_rows) + 1) // 2
                col1, col2 = st.columns(2)
                col1.table(pd.DataFrame(display_rows[:mid]).set_index('Field'))
                col2.table(pd.DataFrame(display_rows[mid:]).set_index('Field'))
    else:
        st.caption("No pit scouting data.")
