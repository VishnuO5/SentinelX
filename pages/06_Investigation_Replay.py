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


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header, badge
import src.ui.theme as theme
apply_theme()
sidebar_user()
page_header("⏮️", "Investigation Replay", "Step through how a case actually unfolded, from first flag to resolution.")

repo = CaseTimelineRepository()
cases = repo.list_cases_with_timeline(limit=100)

if not cases:
    st.info("No case timelines found. Run scripts/generate_case_timeline.py, then reload the database.")
    st.stop()

PRIORITY_KIND = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
STATUS_KIND = {"open": "medium", "in_progress": "brand", "escalated": "critical",
               "resolved": "good", "closed": "low"}

st.markdown(f'<div class="sx-card">{card_header("🎬", "Choose a case")}', unsafe_allow_html=True)
case_options = {
    f"{c['case_id']} — {c['case_type']} ({c['priority']}, {c['status']})": c["case_id"]
    for c in cases
}
choice = st.selectbox("Select a case to replay", options=list(case_options.keys()), label_visibility="collapsed")
selected_case_id = case_options[choice]

summary = repo.get_case_summary(selected_case_id)
timeline = repo.get_timeline(selected_case_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Case Type", summary["case_type"].replace("_", " ").title())
c2.metric("Priority", summary["priority"].title())
c3.metric("Status", summary["status"].replace("_", " ").title())
c4.metric("Account Risk", f"{summary['risk_score']:.3f}" if summary.get("risk_score") is not None else "n/a")
st.markdown("</div>", unsafe_allow_html=True)

EVENT_COLORS = {
    "case_opened": "#C9A227",
    "evidence_collected": "#6C63FF",
    "escalated": "#DC2626",
    "resolved": "#12946F",
}
EVENT_LABELS = {
    "case_opened": "Case Opened",
    "evidence_collected": "Evidence Collected",
    "escalated": "Escalated",
    "resolved": "Resolved",
}

if timeline:
    left, right = st.columns([3, 2])

    with left:
        st.markdown(f'<div class="sx-card">{card_header("📈", "Timeline")}', unsafe_allow_html=True)
        fig = go.Figure()
        x_vals = [e["event_timestamp"] for e in timeline]
        y_vals = [0] * len(timeline)
        colors = [EVENT_COLORS.get(e["event_type"], theme.CHART_NEUTRAL) for e in timeline]
        labels = [EVENT_LABELS.get(e["event_type"], e["event_type"]) for e in timeline]

        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals, mode="markers+lines+text",
            marker=dict(size=18, color=colors, line=dict(width=2, color="white")),
            line=dict(color=theme.CHART_LINE, width=2),
            text=labels, textposition="top center",
            hovertext=[e["event_description"] for e in timeline],
            hoverinfo="text+x",
        ))
        fig.update_layout(
            height=250, showlegend=False,
            yaxis=dict(visible=False, range=[-1, 1]),
            xaxis=dict(title="Time"),
            margin=dict(l=20, r=20, t=40, b=20),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown(f'<div class="sx-card">{card_header("📋", "Case snapshot")}', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="display:flex; flex-direction:column; gap:0.7rem;">
                <div>{badge(summary['priority'], PRIORITY_KIND.get(summary['priority'], 'low'))}
                     {badge(summary['status'].replace('_',' '), STATUS_KIND.get(summary['status'], 'low'))}</div>
                <div class="sx-mono" style="color:var(--sx-muted); font-size:0.85rem;">
                    {len(timeline)} events recorded for {selected_case_id}
                </div>
            </div>
            """.strip(),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Step-by-step detail, reusing the same activity-feed component
    #    Mission Control's Activity card uses, so a timeline reads the
    #    same way anywhere it shows up in the app ──────────────────────
    st.markdown(f'<div class="sx-card">{card_header("🪄", "Event Log")}', unsafe_allow_html=True)
    items_html = ""
    for e in timeline:
        color = EVENT_COLORS.get(e["event_type"], theme.CHART_NEUTRAL)
        label = EVENT_LABELS.get(e["event_type"], e["event_type"])
        items_html += f"""
        <div class="sx-activity-item">
            <div class="sx-activity-dot" style="background:{color};"></div>
            <div style="flex:1;">
                <div class="sx-activity-row">
                    <div>
                        <div class="sx-activity-title">{label}</div>
                        <div class="sx-activity-desc">{e['event_description']}</div>
                    </div>
                    <div class="sx-activity-time">{str(e['event_timestamp'])[:16].replace('T', ' ')}</div>
                </div>
            </div>
        </div>
        """.strip()
    st.markdown(items_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("No timeline events recorded for this case.")

sidebar_status()