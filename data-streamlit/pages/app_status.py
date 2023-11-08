import json
import streamlit as st
import clipboard

from scout import fix_session


def apply_state():
    obj = json.loads(ta)
    st.session_state.update(obj)


def copy_state():
    json_str = json.dumps(obj, indent=4, sort_keys=True)
    clipboard.copy(json_str)
    st.toast('Copy to clipboard complete!')


fix_session()

# Create text input that lets us paste in the JSON status of our app
# and then appply it to our session
st.subheader('Apply state')
ta = st.text_area(label='JSON')
apply = st.button('Apply', on_click=apply_state)

# Display the current session JSON to the user w/ a "copy" box in the
# top right
obj = dict(st.session_state)
st.subheader('Current state')
apply = st.button('Copy to clipboard', on_click=copy_state)
st.code(
    json.dumps(obj, indent=4, sort_keys=True),
    language="json",
)
