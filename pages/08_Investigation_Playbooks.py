"""
pages/08_Investigation_Playbooks.py
======================================
Investigation Playbooks: case-type-specific recommended investigation
steps. An analyst picks a case type (or jumps in from a specific open
case) and gets the actual checklist to work through.
"""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.playbook_repository import PlaybookRepository

st.set_page_config(layout="wide")
st.title("Investigation Playbooks")
st.caption("Case-type-specific recommended steps -- spam gets a different playbook than harassment.")

repo = PlaybookRepository()
case_types = repo.list_case_types()

if not case_types:
    st.info("No playbooks found. Run scripts/generate_playbooks.py, then reload the database.")
    st.stop()

col1, col2 = st.columns([1, 2])
with col1:
    selected_type = st.selectbox("Case type", options=case_types)

with col2:
    open_cases = repo.list_open_cases_by_type(selected_type)
    st.caption(f"{len(open_cases)} open case(s) of this type right now")

steps = repo.get_playbook(selected_type)

st.divider()
st.subheader(f"Playbook: {selected_type.replace('_', ' ').title()}")

if not steps:
    st.warning(f"No playbook defined for '{selected_type}'.")
else:
    checked_count = 0
    for step in steps:
        key = f"playbook_{selected_type}_{step['playbook_id']}"
        is_required = bool(step["checklist_item"])
        label = f"**Step {step['step_order']}.** {step['step_description']}"
        if is_required:
            label += "  \n:small_red_triangle: *required before closing*"
        checked = st.checkbox(label, key=key)
        if checked:
            checked_count += 1

    st.progress(checked_count / len(steps), text=f"{checked_count} / {len(steps)} steps completed")

st.divider()

st.subheader(f"Open cases of type '{selected_type}'")
if open_cases:
    st.dataframe(open_cases, use_container_width=True)
else:
    st.info("No open cases of this type right now.")