"""
pages/10_Counterfactual_Simulator.py
=======================================
Counterfactual Simulator: "what would have happened under a different
policy?" Each scenario is computed against real report/account/timeline
data by scripts/generate_counterfactual_runs.py -- including scenarios
where the honest answer is "nothing would have changed," which is
itself a real finding about how much overlap exists between signals.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.counterfactual_repository import CounterfactualRepository


from src.ui.theme import apply_theme, sidebar_user, sidebar_status
import src.ui.theme as theme
apply_theme()
sidebar_user()
st.title("Counterfactual Simulator")
st.caption("What would have happened to real cases under a different policy -- computed, not guessed.")

repo = CounterfactualRepository()
runs = repo.list_runs()

if not runs:
    st.info("No counterfactual runs found. Run scripts/generate_counterfactual_runs.py, then reload the database.")
    st.stop()

fig = go.Figure()
fig.add_trace(go.Bar(
    x=[r["run_id"] for r in runs], y=[r["cases_would_have_flagged"] for r in runs],
    name="Would have flagged (new)", marker_color=theme.CHART_SECONDARY,
))
fig.add_trace(go.Bar(
    x=[r["run_id"] for r in runs], y=[r["cases_would_have_missed"] for r in runs],
    name="Would have missed (dropped)", marker_color=theme.CHART_PRIMARY,
))
fig.update_layout(
    barmode="group", height=400,
    xaxis_title="Scenario", yaxis_title="Accounts",
    margin=dict(l=20, r=20, t=20, b=20),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Scenario Detail")

for r in runs:
    with st.container(border=True):
        st.write(f"**{r['run_id']}: {r['policy_description']}**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Accounts Affected", r["cases_affected_count"])
        c2.metric("Newly Flagged", r["cases_would_have_flagged"])
        c3.metric("Would Have Missed", r["cases_would_have_missed"])

        if r["cases_affected_count"] == 0:
            st.caption(
                "No change -- every account this policy would target is already "
                "captured by the current detection signals (device reuse, report "
                "volume, and account age already correlate strongly with real "
                "campaign membership in this dataset)."
            )

sidebar_status()