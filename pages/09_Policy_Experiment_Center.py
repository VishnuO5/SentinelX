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


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header
import src.ui.theme as theme
apply_theme()
sidebar_user()
page_header("🧪", "Policy Experiment Center", "What happens to precision and recall if we move the high-risk threshold? " "Ground truth proxy: accounts confirmed to belong to a real campaign cluster.")

repo = PolicyExperimentRepository()

# ── Pre-generated experiments ────────────────────────────────────────────
st.markdown(f'<div class="sx-card">{card_header("🗃️", "Recorded Experiments")}', unsafe_allow_html=True)
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
st.markdown("</div>", unsafe_allow_html=True)

# ── Live interactive threshold test ──────────────────────────────────────
st.markdown(f'<div class="sx-card">{card_header("🎚️", "Test Any Threshold Live")}', unsafe_allow_html=True)

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

# 95% Wilson score confidence intervals -- precision and recall are both
# proportions over a finite, real sample (not population parameters), so
# a raw point estimate overstates certainty, especially at thresholds
# where few accounts get flagged. This is exactly what "apply advanced
# statistical methods to understand impact" means in practice, not just
# reporting the metric.
prec_lo, prec_hi = theme.wilson_ci(live["tp"], live["tp"] + live["fp"])
rec_lo, rec_hi = theme.wilson_ci(live["tp"], live["tp"] + live["fn"])
ci_col1, ci_col2, _, _ = st.columns(4)
ci_col1.caption(f"95% CI: [{prec_lo:.3f}, {prec_hi:.3f}]")
ci_col2.caption(f"95% CI: [{rec_lo:.3f}, {rec_hi:.3f}]")

# ── Confusion matrix, visualized ─────────────────────────────────────────
# The tp/fp/fn/tn caption below states the same four numbers as text --
# this heatmap makes the actual trade-off (what gets caught vs. what
# gets missed vs. what gets wrongly flagged) legible at a glance instead
# of requiring the reader to do the arithmetic themselves.
cm_col, caption_col = st.columns([1, 1])
with cm_col:
    z = [[live["fn"], live["tp"]], [live["tn"], live["fp"]]]
    cm_fig = go.Figure(go.Heatmap(
        z=z,
        x=["Predicted: not high-risk", "Predicted: high-risk"],
        y=["Actual: not a campaign", "Actual: real campaign"],
        text=z, texttemplate="%{text}",
        textfont=dict(size=16),
        colorscale=[[0, "rgba(124,58,237,0.05)"], [1, theme.CHART_PRIMARY]],
        showscale=False,
    ))
    cm_fig.update_layout(
        height=260, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=theme.CHART_NEUTRAL),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(cm_fig, width="stretch")
with caption_col:
    st.markdown(
        f"""
        <div style="padding-top:1.5rem; display:flex; flex-direction:column; gap:0.5rem;">
            <div><b>{live['tp']}</b> true positives — real campaign accounts correctly flagged.</div>
            <div><b>{live['fp']}</b> false positives — organic accounts incorrectly flagged.</div>
            <div><b>{live['fn']}</b> false negatives — real campaign accounts missed at this threshold.</div>
            <div><b>{live['tn']}</b> true negatives — organic accounts correctly left alone.</div>
        </div>
        """.strip(),
        unsafe_allow_html=True,
    )
st.markdown("</div>", unsafe_allow_html=True)

# ── Full precision/recall sweep ──────────────────────────────────────────
st.markdown(f'<div class="sx-card">{card_header("📉", "Precision vs. Recall Across All Thresholds")}', unsafe_allow_html=True)

sweep = repo.sweep_thresholds(step=0.05)
prec_lo_band = [theme.wilson_ci(s["tp"], s["tp"] + s["fp"])[0] for s in sweep]
prec_hi_band = [theme.wilson_ci(s["tp"], s["tp"] + s["fp"])[1] for s in sweep]
rec_lo_band = [theme.wilson_ci(s["tp"], s["tp"] + s["fn"])[0] for s in sweep]
rec_hi_band = [theme.wilson_ci(s["tp"], s["tp"] + s["fn"])[1] for s in sweep]
x_vals = [s["threshold"] for s in sweep]

fig = go.Figure()
# Shaded 95% Wilson CI bands, drawn first so the point-estimate lines sit
# on top. Wider band = fewer accounts flagged at that threshold = less
# certain that number is -- visible instead of implied.
fig.add_trace(go.Scatter(
    x=x_vals + x_vals[::-1], y=prec_hi_band + prec_lo_band[::-1],
    fill="toself", fillcolor="rgba(124,58,237,0.12)",
    line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip", showlegend=False,
))
fig.add_trace(go.Scatter(
    x=x_vals + x_vals[::-1], y=rec_hi_band + rec_lo_band[::-1],
    fill="toself", fillcolor="rgba(225,29,72,0.10)",
    line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip", showlegend=False,
))
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
    height=380, margin=dict(l=20, r=20, t=20, b=20),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig, width="stretch")
st.caption("Shaded bands are 95% Wilson score confidence intervals -- wider where fewer accounts are flagged at that threshold.")
st.markdown("</div>", unsafe_allow_html=True)

sidebar_status()