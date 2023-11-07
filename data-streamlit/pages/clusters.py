import pandas as pd
import numpy as np
import streamlit as st

from sklearn.cluster import KMeans

from scout import (
    load_event_data, load_opr_data, get_event_key, get_secret_key,
    get_dnp_list, fix_session,
)

norm = np.linalg.norm


def show_cluster_panel(df, opr, dnp_nums):
    cluster_count = st.text_input("Cluster Count", 4)
    df = df[~df.scouting_team.isin(dnp_nums)]
    st.subheader("KMeans clusters")
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
    st.subheader("Variance of each column")
    col1 = variances.keys()
    col2 = variances.values()
    var_df = pd.DataFrame({'measure': col1, 'var': col2})
    st.dataframe(var_df, hide_index=True)
    data_cols = st.multiselect('Considered data', avail_cols,
                               format_func=lambda x: f'{x[0]} ({x[1]:0.2f})',
                               default=avail_cols[:8])

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
    for cname, cluster in sorted(clusters.items(),
                                 key=lambda x: x[1]['opr_avg'],
                                 reverse=True):
        opr_avg = cluster['opr_total'] / len(cluster['teams'])
        st.header(f"Group {idx} ({opr_avg:0.2f} OPR Avg)")
        st.info(', '.join(cluster['teams']))
        idx += 1


fix_session()
scouted_data = load_event_data(get_secret_key(), get_event_key())
opr_data = load_opr_data(get_secret_key(), get_event_key())
dnp = get_dnp_list()
show_cluster_panel(scouted_data, opr_data, dnp)
