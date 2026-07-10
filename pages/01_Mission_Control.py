import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.mission_control_repository import MissionControlRepository

st.set_page_config(layout="wide")

st.title("Mission Control")

repo = MissionControlRepository()
kpis = repo.get_kpis()

col1, col2, col3, col4 = st.columns(4)

col1.metric("Open Investigations", kpis["open_cases"])
col2.metric("High Risk Accounts", kpis["high_risk_accounts"])
col3.metric("Active Campaigns", kpis["active_campaigns"])
col4.metric("Average Risk", kpis["avg_risk"])

st.divider()

left, right = st.columns([2, 1])

with left:
    st.subheader("Recent Investigations")

    recent_cases = repo.get_recent_cases(limit=10)

    if recent_cases:
        st.dataframe(recent_cases, use_container_width=True)
    else:
        st.info("No cases found in the database.")

with right:
    st.subheader("Moderator Workload")

    moderators = repo.get_moderator_workload()

    if moderators:
        st.dataframe(moderators, use_container_width=True)
    else:
        st.info("No moderators found.")