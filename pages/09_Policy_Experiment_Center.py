"""
pages/09_Policy_Experiment_Center.py
=======================================
Policy Experiment Center: "what if we changed the threshold?" Every
number on this page is a real precision/recall/F1 computed against
actual account data -- either pre-generated (scripts/
generate_policy_experiments.py) or live via the slider below.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.repositories.policy_experiment_repository import PolicyExperimentRepository


from src.ui.theme import apply_theme, sidebar_user, sidebar_status
import src.ui.theme as theme
apply_theme()
sidebar_user()
st.title("Policy Experiment Center")
st.caption(
    "What happens to precision and recall if we move the high-risk threshold? "
    "Ground truth proxy: accounts confirmed to belong to a real campaign cluster."
)

repo = PolicyExperimentRepository()

# ── Pre-generated experiments ────────────────────────────────────────────
st.subheader("Recorded Experiments")
experiments = repo.list_experiments()

if experiments:
    st.dataframe(
        experiments,
        width="stretch",
        column_config={
            "baseline_precision": st.column_config.NumberColumn("Baseline Precision", format="%.3f"),
            "baseline_recall": st.column_config.NumberColumn("Baseline Recall", format="%.3f"),
            "tested_precision": st.column_config.NumberColumn("Tested Precision", format="%.3f"),
            "tested_recall": st.column_config.NumberColumn("Tested Recall", format="%.3f"),
        },
    )
else:
    st.info("No experiments found. Run scripts/generate_policy_experiments.py, then reload the database.")

st.divider()

# ── Live interactive threshold test ──────────────────────────────────────
st.subheader("Test Any Threshold Live")

col1, col2 = st.columns([2, 1])
with col1:
    threshold = st.slider(
        "High-risk threshold (composite_risk_score >=)",
        min_value=0.0, max_value=1.0, value=config.HIGH_RISK_THRESHOLD, step=0.01,
    )
with col2:
    st.metric("Current production value", config.HIGH_RISK_THRESHOLD)

live = repo.compute_live_metrics(threshold)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Precision", f"{live['precision']:.3f}")
m2.metric("Recall", f"{live['recall']:.3f}")
m3.metric("F1 Score", f"{live['f1']:.3f}")
m4.metric("Flagged Accounts", live["tp"] + live["fp"])

st.caption(
    f"True positives: {live['tp']} · False positives: {live['fp']} · "
    f"False negatives: {live['fn']} · True negatives: {live['tn']}"
)

st.divider()

# ── Full precision/recall sweep ──────────────────────────────────────────
st.subheader("Precision vs. Recall Across All Thresholds")

sweep = repo.sweep_thresholds(step=0.05)
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=[s["threshold"] for s in sweep], y=[s["precision"] for s in sweep],
    name="Precision", line=dict(color=theme.CHART_PRIMARY, width=2),
))
fig.add_trace(go.Scatter(
    x=[s["threshold"] for s in sweep], y=[s["recall"] for s in sweep],
    name="Recall", line=dict(color=theme.CHART_SECONDARY, width=2),
))
fig.add_trace(go.Scatter(
    x=[s["threshold"] for s in sweep], y=[s["f1"] for s in sweep],
    name="F1", line=dict(color=theme.CHART_ACCENT_TEAL, width=2, dash="dot"),
))
fig.add_vline(x=threshold, line_dash="dash", line_color="gray",
              annotation_text="selected threshold")
fig.update_layout(
    xaxis_title="Threshold", yaxis_title="Score", yaxis_range=[0, 1.05],
    height=400, margin=dict(l=20, r=20, t=20, b=20),
)
st.plotly_chart(fig, width="stretch")

sidebar_status()