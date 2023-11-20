import numpy as np
import streamlit as st

from scout import (
    load_team_data, load_event_data, get_event_key,
    get_secret_key, fix_session
)


fix_session()
st.header('Principal Component Analysis')
scouted_data = load_event_data(get_secret_key(), get_event_key())
score_vectors = (
    scouted_data
    .groupby("scouting_team")
    .mean(numeric_only=True)
    .reset_index()
)
st.dataframe(score_vectors)

A = score_vectors
N = A.shape[1]
C = 1/N*(A@A.T)
r = np.linalg.eigh(C)
eigens = [np.real(x) for x in r.eigenvalues]
norm = np.linalg.norm
Q = np.array([
    r.eigenvectors[0],
    r.eigenvectors[1],
]).T
proj = Q.T @ A