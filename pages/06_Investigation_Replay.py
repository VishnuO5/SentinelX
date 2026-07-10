"""
pages/06_Investigation_Replay.py
===================================
Investigation Replay: timeline reconstruction of how a case unfolded,
from the initial flag through to resolution.

Events come from case_timeline (see scripts/generate_case_timeline.py),
which derives every event directly from that case's real opened_at/
status/resolved_at -- the replay can never show a timeline that
contradicts the case's actual recorded outcome.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.case_timeline_repository import CaseTimelineRepository

st.set_page_config(layout="wide")
st.title("Investigation Replay")
st.caption("Step through how a case actually unfolded, from first flag to resolution.")

repo = CaseTimelineRepository()
cases = repo.list_cases_with_timeline(limit=100)

if not cases:
    st.info("No case timelines found. Run scripts/generate_case_timeline.py, then reload the database.")
    st.stop()

case_options = {
    f"{c['case_id']} — {c['case_type']} ({c['priority']}, {c['status']})": c["case_id"]
    for c in cases
}
choice = st.selectbox("Select a case to replay", options=list(case_options.keys()))
selected_case_id = case_options[choice]

summary = repo.get_case_summary(selected_case_id)
timeline = repo.get_timeline(selected_case_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Case Type", summary["case_type"])
c2.metric("Priority", summary["priority"])
c3.metric("Status", summary["status"])
c4.metric("Account Risk", f"{summary['risk_score']:.3f}" if summary.get("risk_score") is not None else "n/a")

st.divider()

EVENT_COLORS = {
    "case_opened": "#4C6FFF",
    "evidence_collected": "#8C9EFF",
    "escalated": "#FFB020",
    "resolved": "#2ECC71",
}
EVENT_LABELS = {
    "case_opened": "Case Opened",
    "evidence_collected": "Evidence Collected",
    "escalated": "Escalated",
    "resolved": "Resolved",
}

if timeline:
    # ── Visual horizontal timeline ──────────────────────────────────
    fig = go.Figure()
    x_vals = [e["event_timestamp"] for e in timeline]
    y_vals = [0] * len(timeline)
    colors = [EVENT_COLORS.get(e["event_type"], "#999999") for e in timeline]
    labels = [EVENT_LABELS.get(e["event_type"], e["event_type"]) for e in timeline]

    fig.add_trace(go.Scatter(
        x=x_vals, y=y_vals, mode="markers+lines+text",
        marker=dict(size=18, color=colors, line=dict(width=2, color="white")),
        line=dict(color="#CCCCCC", width=2),
        text=labels, textposition="top center",
        hovertext=[e["event_description"] for e in timeline],
        hoverinfo="text+x",
    ))
    fig.update_layout(
        height=250, showlegend=False,
        yaxis=dict(visible=False, range=[-1, 1]),
        xaxis=dict(title="Time"),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Step-by-step detail ─────────────────────────────────────────
    st.subheader("Event Log")
    for e in timeline:
        color = EVENT_COLORS.get(e["event_type"], "#999999")
        st.markdown(
            f"<div style='border-left: 4px solid {color}; padding-left: 12px; margin-bottom: 14px;'>"
            f"<b>{EVENT_LABELS.get(e['event_type'], e['event_type'])}</b> "
            f"&nbsp;·&nbsp; <span style='color: gray;'>{e['event_timestamp']}</span><br>"
            f"{e['event_description']}"
            f"</div>",
            unsafe_allow_html=True,
        )
else:
    st.info("No timeline events recorded for this case.")