from pathlib import Path

import streamlit as st

st.set_page_config(

    page_title="SentinelX",

    page_icon="🛡️",

    layout="wide",

    initial_sidebar_state="expanded",

)

css = Path("assets/style.css").read_text()

st.markdown(

    f"<style>{css}</style>",

    unsafe_allow_html=True,

)

st.markdown(

"""

<div class="big-title">

🛡️ SentinelX

</div>

<div class="subtitle">

AI-Powered Trust & Safety Intelligence Platform

</div>

""",

unsafe_allow_html=True,

)

st.divider()

st.info(

"Select a module from the sidebar."

)