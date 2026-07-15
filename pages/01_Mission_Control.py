"""
pages/01_Mission_Control.py
==============================
Premium dashboard: full-width gradient KPI banner, case volume trend,
priority donut, a real activity feed (from case_timeline), and a styled
recent-cases table. Every number is real, nothing hardcoded.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.mission_control_repository import MissionControlRepository
import src.ui.theme as theme
from src.ui.theme import (
    apply_theme, sidebar_user, sidebar_status, kpi_banner, banner_stat,
    pill, badge, card_header, chip, page_header,
)


apply_theme()
sidebar_user()

repo = MissionControlRepository()
kpis = repo.get_kpis()

page_header(
    "🎯", "Mission Control",
    "Active investigations, risk posture, and team activity — live from the database.",
)

# ---------------------------------------------------------------------
# Gradient KPI banner
# ---------------------------------------------------------------------

kpi_banner([
    banner_stat("📂", "Open Investigations", kpis["open_cases"],
                pill("across all priorities", "flat")),
    banner_stat("⚠️", "High-Risk Accounts", kpis["high_risk_accounts"],
                pill("risk ≥ 0.4", "flat")),
    banner_stat("🧬", "Active Campaigns", kpis["active_campaigns"],
                pill("currently tracked", "flat")),
    banner_stat("📊", "Average Risk", f"{kpis['avg_risk'] * 100:.0f}%",
                pill("population-wide", "flat")),
])

# ---------------------------------------------------------------------
# Trend + priority donut
# ---------------------------------------------------------------------

left, right = st.columns([2, 1])

with left:
    st.markdown(
        f'<div class="sx-card">{card_header("📈", "Case Volume")}',
        unsafe_allow_html=True,
    )

    RANGE_OPTIONS = {"30d": 30, "60d": 60, "90d": 90, "All time": None}
    selected_range = st.radio(
        "Range", list(RANGE_OPTIONS.keys()), index=3,
        horizontal=True, label_visibility="collapsed", key="case_volume_range",
    )
    # Defensive call: if an older copy of mission_control_repository.py
    # (one without the `days` parameter) is still on disk, this falls
    # back to the full-history query instead of crashing the page. The
    # range buttons will simply have no effect until the repository file
    # is updated too -- but the page always loads.
    try:
        trend = repo.get_case_volume_trend(days=RANGE_OPTIONS[selected_range])
    except TypeError:
        st.caption(
            "⚠️ Range filter inactive — mission_control_repository.py on disk "
            "is an older version that doesn't accept a `days` argument yet. "
            "Replace that file to enable filtering."
        )
        trend = repo.get_case_volume_trend()
    if trend:
        weeks = [t["week"] for t in trend]
        counts = [t["count"] for t in trend]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=weeks, y=counts, mode="lines",
            line=dict(color=theme.CHART_PRIMARY, width=2.5, shape="spline"),
            fill="tozeroy", fillcolor="rgba(124, 58, 237, 0.10)",
            hovertemplate="Week %{x}<br>%{y} cases<extra></extra>",
        ))
        fig.update_layout(
            height=250, margin=dict(l=10, r=10, t=6, b=10),
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(family="Inter, sans-serif", size=11, color="#5B6478"),
            xaxis=dict(showgrid=False, showline=True, linecolor="#ECEDF4"),
            yaxis=dict(showgrid=True, gridcolor="#F1F2F6", zeroline=False),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    else:
        st.info("No case data yet.")

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown(
        f'<div class="sx-card">{card_header("🥧", "By Priority")}',
        unsafe_allow_html=True,
    )

    breakdown = repo.get_priority_breakdown()
    if breakdown:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        breakdown = sorted(breakdown, key=lambda b: order.get(b["priority"], 9))
        colors = {"critical": "#DC2626", "high": "#EA580C", "medium": "#D97706", "low": "#9096A8"}

        fig = go.Figure(data=[go.Pie(
            labels=[b["priority"].capitalize() for b in breakdown],
            values=[b["count"] for b in breakdown],
            hole=0.62,
            marker=dict(colors=[colors.get(b["priority"], "#9096A8") for b in breakdown]),
            textinfo="value",
            textfont=dict(family="JetBrains Mono, monospace", size=12),
            hovertemplate="%{label}: %{value} cases<extra></extra>",
        )])
        fig.update_layout(
            height=250, margin=dict(l=10, r=10, t=6, b=10),
            paper_bgcolor="white", showlegend=True,
            legend=dict(orientation="h", y=-0.12, font=dict(size=10, family="Inter, sans-serif")),
            font=dict(family="Inter, sans-serif", color="#5B6478"),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    else:
        st.info("No case data yet.")

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# Recent Investigations (styled table) + Activity Feed
# ---------------------------------------------------------------------

left, right = st.columns([2, 1])

PRIORITY_KIND = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
STATUS_KIND = {"open": "medium", "in_progress": "brand", "escalated": "critical",
               "resolved": "good", "closed": "low"}
EVENT_META = {
    "case_opened":        ("#C9A227", "Case opened"),
    "escalated":          ("#DC2626", "Escalated"),
    "evidence_collected": ("#6C63FF", "Evidence collected"),
    "resolved":           ("#12946F", "Resolved"),
}

with left:
    st.markdown(
        f'<div class="sx-card">{card_header("🗂️", "Recent Investigations")}',
        unsafe_allow_html=True,
    )

    recent_cases = repo.get_recent_cases(limit=8)

    if recent_cases:
        rows_html = ""
        for c in recent_cases:
            pri_badge = badge(c["priority"], PRIORITY_KIND.get(c["priority"], "low"))
            status_badge = badge(c["status"].replace("_", " "), STATUS_KIND.get(c["status"], "low"))
            mod = c["assigned_moderator_id"] or "—"
            # .strip() on EACH row before concatenating -- accumulating
            # un-stripped f-strings in a loop leaves a whitespace-only
            # line between every pair of rows (row1 ends with trailing
            # indentation, row2 starts with a leading newline -- together
            # that's a blank line), which is exactly what makes Streamlit's
            # Markdown renderer treat everything after row 1 as a literal
            # code block. Stripping each fragment means concatenation adds
            # zero extra whitespace, so no blank line can ever form.
            rows_html += f"""
            <tr>
                <td class="sx-mono">{c['case_id']}</td>
                <td>{chip(c['case_type'])}</td>
                <td>{pri_badge}</td>
                <td>{status_badge}</td>
                <td class="sx-mono">{str(c['opened_at'])[:10]}</td>
                <td class="sx-mono">{mod}</td>
            </tr>
            """.strip()
        st.markdown(
            f"""
            <table class="sx-table">
                <thead><tr>
                    <th>Case ID</th><th>Type</th><th>Priority</th>
                    <th>Status</th><th>Opened</th><th>Moderator</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
            """.strip(),
            unsafe_allow_html=True,
        )
    else:
        st.info("No cases found in the database.")

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown(
        f'<div class="sx-card">{card_header("⚡", "Activity")}',
        unsafe_allow_html=True,
    )

    activity = repo.get_recent_activity(limit=6)

    if activity:
        items_html = ""
        for a in activity:
            color, label = EVENT_META.get(a["event_type"], ("#9096A8", a["event_type"]))
            time_str = str(a["event_timestamp"])[5:16].replace("-", "/")
            items_html += f"""
            <div class="sx-activity-item">
                <div class="sx-activity-dot" style="background:{color};"></div>
                <div style="flex:1;">
                    <div class="sx-activity-row">
                        <div>
                            <div class="sx-activity-title">{label} — {a['case_id']}</div>
                            <div class="sx-activity-desc">{a['event_description']}</div>
                        </div>
                        <div class="sx-activity-time">{time_str}</div>
                    </div>
                </div>
            </div>
            """.strip()
        st.markdown(items_html, unsafe_allow_html=True)
    else:
        st.info("No activity yet.")

    st.markdown("</div>", unsafe_allow_html=True)

sidebar_status()