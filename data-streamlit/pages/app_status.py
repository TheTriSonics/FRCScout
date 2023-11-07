import json
import streamlit as st

from scout import fix_session


fix_session()


def apply_state():
    obj = json.loads(ta)
    st.session_state.update(obj)


st.subheader('Apply state')
ta = st.text_area(label='JSON')
apply = st.button('Apply', on_click=apply_state)

obj = dict(st.session_state)
st.subheader('Current state')
st.code(
    json.dumps(obj, indent=4, sort_keys=True),
    language="json",
)
