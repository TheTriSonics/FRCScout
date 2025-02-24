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

def add_pca_components(df, feature_columns):
    from sklearn.preprocessing import StandardScaler
    # Extract features
    X = df[feature_columns].values

    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Calculate covariance matrix
    cov_matrix = np.cov(X_scaled.T)

    # Calculate eigenvalues and eigenvectors
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

    # Sort eigenvectors by eigenvalues in descending order
    idx = eigenvalues.argsort()[::-1]
    eigenvectors = eigenvectors[:, idx]

    # Get first two principal components
    pca_transform = eigenvectors[:, :2]

    # Project data onto first two principal components
    pca_result = np.dot(X_scaled, pca_transform)

    # Add PCA components to DataFrame
    df_result = df.copy()
    df_result['pca1'] = pca_result[:, 0]
    df_result['pca2'] = pca_result[:, 1]

    return df_result


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
    st.write(opr)
    with st.expander('Instructions'):
        st.write(
"""
This allows us to break teams into groups that share similar attributes with one
another.

If you were to pick two numbers upon which to group robots and graph them out on
an X/Y plane you can generally see which ones are similar based on their
distance from one another. But, that only lets you consider two metrics. For
Reefscape you could do something like add up all of the coral points a team gets
and all of the algae points a team gets and use them as your X and Y values. And
that kind of tells you something. But, what if you want to consider everything
we collect?  The number of corals scored on level 4, level 3, level 1, the
trough, etc.  Every number. Well, you end up with more than the two dimensions
you can graph in the X/Y plane. For most FRC games we collect 12-20 metrics and
that means we're working in 12-20 dimensions.

And while it's not intuitive to work in those higher dimensions, we have math to
guide the way. What we're doing in KMeans clustering is finding thigns that are
related to one another based on their distance from one another in those higher
dimensions. To find the distance between two points in two dimensions you use
the Pythagorean theorem.
        """)
        st.latex(
"""
distance = \sqrt{xdistance^2 + ydistance^2}"""
        )
        st.write(
"""
And in three dimensions you just add the third measurement to the mix.  """)
        st.latex(
"""
distance = \sqrt{x^2 + y^2 + z^2}""")
        st.write(
"""
But now we call it a Euclidian distance and it keeps on working in the 4th, 5th,
and so on. We use this fundamental idea to find groups of teams that are similar
using an algorithm known as KMeans clustering. It identifies groups that are
near each other and works in higher dimensional spaces.  A suitable explanation
of it can be found here: https://stanford.edu/~cpiech/cs221/handouts/kmeans.html

In this particular tool if you set your clustering algorithm to only include
two dimensions, or two things we measure, you'll be able to visually see that
the groups are indeed members that are close to one another. It's just hard
to present that relationship in any dimension higher than 3, even with the 3D
capabilities of a computer at our disposal.
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
    scouted_score_vectors = (
        df
        .groupby("scouting_team")
        .mean(numeric_only=True)
        .reset_index()
    )
    # Conver teamNumber column to a string
    opr['teamNumber'] = opr['teamNumber'].astype(str)
    opr_score_vectors = (
        opr
        .groupby("teamNumber")
        .mean(numeric_only=True)
        .reset_index()
    )
    scouted_score_cols = [
        x
        for x in scouted_score_vectors.columns
        if x.startswith(("auto", "tele", "endgame", "comp"))
    ]
    opr_score_cols = [x for x in opr_score_vectors.columns if x != 'teamNumber']
    variances = {}

    # Okay, we could do this with linear algebra. Might change it out
    # Have code in kmeans.ipynb notebook in project, but this gives the same
    # values
    for sc in scouted_score_cols:
        v = np.var(scouted_score_vectors[sc])
        variances[sc] = v
    for sc in opr_score_cols:
        v = np.var(opr_score_vectors[sc])
        variances[sc] = v
    variances_by_val = sorted(variances.items(), key=lambda x: x[1],
                              reverse=True)
    variances = dict(variances_by_val)
    avail_cols = list(zip(variances.keys(), variances.values()))
    with st.expander("Variance of each column (informational)"):
        col1 = variances.keys()
        col2 = variances.values()
        var_df = pd.DataFrame({'measure': col1, 'var': col2})
        st.dataframe(var_df, hide_index=True)
    scouted_data_cols = st.multiselect(
        'Dimensions (scouted data)', avail_cols,
        format_func=lambda x: f'{x[0]} ({x[1]:0.2f})',
        default=[col for col in avail_cols if not col[0].startswith('pca')]
    )

    if len(scouted_data_cols) == 0:
        return  # Can't go on. Just abort

    model = KMeans(int(cluster_count),
                   random_state=1,
                   init='random',
                   n_init=10,
                   max_iter=100)

    # make sure scouting_team and teamNumber are both strings
    scouted_score_vectors['scouting_team'] = scouted_score_vectors['scouting_team'].astype(str)
    # merge scouted score vectors with opr data
    merged_score_vectors = scouted_score_vectors.merge(
        opr_score_vectors, left_on='scouting_team', right_on='teamNumber'
    )
    merged_score_vectors = add_pca_components(merged_score_vectors, [x[0] for x in scouted_data_cols])
    v = merged_score_vectors.loc[:, [x[0] for x in scouted_data_cols]]
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

    for (idx, row), label in zip(merged_score_vectors.iterrows(), model.labels_):
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

    merged_score_vectors['group_label'] = [
        get_cluster_name(clusters, x) for x in merged_score_vectors.scouting_team
    ]
    pca_axes = st.checkbox(f'Use PCA for chart axis')
    if pca_axes:
        x_axis = 'pca1'
        y_axis = 'pca2'
    else:
        x_axis = scouted_data_cols[0][0]
        y_axis = scouted_data_cols[1][0]

    simp = alt.Chart(merged_score_vectors).mark_circle().encode(
        x=x_axis, y=y_axis,
        color='group_label',
        tooltip='scouting_team',
    ).interactive()

    simp_text = simp.mark_text(
        align='left',
        baseline='top',
        color='blue',
        fontSize=20,
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
