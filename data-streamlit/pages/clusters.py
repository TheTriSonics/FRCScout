import pandas as pd
import numpy as np
import streamlit as st
import altair as alt

from sklearn.cluster import KMeans

from scout import (
    load_event_data, load_opr_data, get_event_key, get_secret_key,
    get_dnp, get_fsp, fix_session,
)

norm = np.linalg.norm


# TODO: Clean this up so we're not duplicating code
def get_cluster_name(clusters, team_number):
    team_number = str(team_number)
    idx = 1
    for cname, cluster in sorted(clusters.items(),
                                 key=lambda x: x[1]['opr_avg'],
                                 reverse=True):
        if team_number in cluster['teams']:
            return str(idx)
        idx += 1
    return 'bob'


def show_cluster_panel(df, opr, dnp_nums, fsp_nums):
    st.header("KMeans clusters")
    with st.expander('Instructions'):
        st.write("""
        This allows us to break teams into groups that share similar
        attributes with one another.

        Also a topic that likely needs a link to details.
        """)
    dnp_show = 'none' if len(dnp_nums) == 0 else ', '.join(map(str, dnp_nums))
    fsp_show = 'none' if len(fsp_nums) == 0 else ', '.join(map(str, fsp_nums))
    exclude_dnp = st.checkbox(f'Exclude do not pick teams ({dnp_show})')
    exclude_fsp = st.checkbox(f'Exclude first pick teams ({fsp_show})')
    cluster_count = st.text_input("Cluster Count", 4)
    # Filter out any team we are NOT picking from custering
    if dnp_nums is not None and exclude_dnp:
        df = df[~df.scouting_team.isin(dnp_nums)]
    if fsp_nums is not None and exclude_fsp:
        df = df[~df.scouting_team.isin(fsp_nums)]
    score_vectors = (
        df
        .groupby("scouting_team")
        .mean(numeric_only=True)
        .reset_index()
    )
    score_cols = [x for x in score_vectors.columns
                  if x.startswith(('auto', 'tele', 'endgame', 'comp'))]
    variances = {}
    # Okay, we could do this with linear algebra. Might change it out
    # Have code in kmeans.ipynb notebook in project, but this gives the same
    # values
    for sc in score_cols:
        v = np.var(score_vectors[sc])
        variances[sc] = v
    variances_by_val = sorted(variances.items(), key=lambda x: x[1],
                              reverse=True)
    variances = dict(variances_by_val)
    avail_cols = list(zip(variances.keys(), variances.values()))
    with st.expander("Variance of each column"):
        col1 = variances.keys()
        col2 = variances.values()
        var_df = pd.DataFrame({'measure': col1, 'var': col2})
        st.dataframe(var_df, hide_index=True)
    data_cols = st.multiselect('Considered data', avail_cols,
                               format_func=lambda x: f'{x[0]} ({x[1]:0.2f})',
                               default=avail_cols[:2])

    if len(data_cols) == 0:
        return  # Can't go on. Just abort

    model = KMeans(int(cluster_count),
                   random_state=1,
                   init='random',
                   n_init=10,
                   max_iter=100)

    v = score_vectors.loc[:, [x[0] for x in data_cols]]
    if False:
        print(
            v.to_numpy()
        )
    model.fit(v.to_numpy())

    clusters = {}

    labels, centers = zip(
        *sorted(zip(set(model.labels_), model.cluster_centers_),
                reverse=True))
    for label, centroid in zip(labels, centers):
        clusters[label] = {
            'teams': [],
            'centroid_mag': norm(centroid),
            'opr_total': 0,
            'opr_avg': 0,
        }

    for (idx, row), label in zip(score_vectors.iterrows(), model.labels_):
        clusters[label]['teams'].append(str(int(row.scouting_team)))
        teamopr = opr_data[opr_data.teamNumber == row.scouting_team]
        if len(teamopr == 1):
            clusters[label]['opr_total'] += (
                teamopr.totalPoints.values[0]
            )
            clusters[label]['opr_avg'] = (
                clusters[label]['opr_total'] / len(clusters[label]['teams'])
            )
        else:
            # Ignore team that's not in the tournament
            # print(f'{row.scouting_team}: {len(teamopr)}')
            pass
    idx = 1

    score_vectors['group_label'] = [
        get_cluster_name(clusters, x) for x in score_vectors.scouting_team
    ]

    if len(data_cols) >= 2:
        simp = alt.Chart(score_vectors).mark_circle().encode(
            x=data_cols[0][0], y=data_cols[1][0],
            color='group_label',
            tooltip='scouting_team',
        ).interactive()

        simp_text = simp.mark_text(
            align='left',
            baseline='top',
            color='blue',
            dx=5,
        ).encode(
            text='scouting_team'
        )
        st.altair_chart(simp_text + simp,
                        theme="streamlit",
                        use_container_width=True)
    for cname, cluster in sorted(clusters.items(),
                                 key=lambda x: x[1]['opr_avg'],
                                 reverse=True):
        opr_avg = cluster['opr_total'] / len(cluster['teams'])
        st.header(f"Group {idx} ({opr_avg:0.2f} OPR Avg)")
        main_teams = cluster['teams']
        dnp_in_cluster = [t for t in main_teams if int(t) in dnp_nums]
        fsp_in_cluster = [t for t in main_teams if int(t) in fsp_nums]
        if not exclude_dnp:
            main_teams = [t for t in main_teams if t not in dnp_nums]
        if not exclude_fsp:
            main_teams = [t for t in main_teams if t not in fsp_nums]
        info_md = ', '.join(main_teams) + '  \n'
        if len(dnp_in_cluster) > 0:
            info_md += f"DNP members: {', '.join(dnp_in_cluster)}  \n"
        if len(fsp_in_cluster) > 0:
            info_md += f"1st pick members: {', '.join(fsp_in_cluster)}  \n"
        st.info(info_md)
        idx += 1


fix_session()
scouted_data = load_event_data(get_secret_key(), get_event_key())
opr_data = load_opr_data(get_secret_key(), get_event_key())
dnp = get_dnp()
fsp = get_fsp()
show_cluster_panel(scouted_data, opr_data, dnp, fsp)
