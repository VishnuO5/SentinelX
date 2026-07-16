"""
pages/08_Investigation_Playbooks.py
======================================
Investigation Playbooks: case-type-specific recommended investigation
steps. An analyst picks a case type (or jumps in from a specific open
case) and gets the actual checklist to work through.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.playbook_repository import PlaybookRepository


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header, chip
import src.ui.theme as theme
apply_theme()
sidebar_user()
page_header("📘", "Investigation Playbooks", "Case-type-specific recommended steps -- spam gets a different playbook than harassment.")

repo = PlaybookRepository()
case_types = repo.list_case_types()

if not case_types:
    st.info("No playbooks found. Run scripts/generate_playbooks.py, then reload the database.")
    st.stop()

st.markdown(f'<div class="sx-card">{card_header("🎯", "Choose a case type")}', unsafe_allow_html=True)
col1, col2 = st.columns([1, 2])
with col1:
    selected_type = st.selectbox("Case type", options=case_types, label_visibility="collapsed")

with col2:
    open_cases = repo.list_open_cases_by_type(selected_type)
    st.markdown(
        f"<div style='padding-top:0.4rem;'>{chip(selected_type)} "
        f"<span class='sx-mono' style='color:var(--sx-muted); font-size:0.85rem;'>"
        f"{len(open_cases)} open case(s) of this type right now</span></div>",
        unsafe_allow_html=True,
    )
st.markdown("</div>", unsafe_allow_html=True)

# ── Historical outcomes for this case type ──────────────────────────────
# Real numbers from every case of this type ever opened -- not
# illustrative. Gives the analyst context the checklist alone can't:
# how often this case type actually resolves, how long it takes, and
# what priority mix it tends to show up at.
stats = repo.get_case_type_stats(selected_type)

st.markdown(f'<div class="sx-card">{card_header("📈", "Historical outcomes for this case type")}', unsafe_allow_html=True)

if stats["total"] == 0:
    st.caption("No historical cases of this type yet.")
else:
    k1, k2, k3 = st.columns(3)
    k1.metric("Cases opened (all time)", stats["total"])
    k2.metric("Resolution rate", f"{stats['resolution_rate']*100:.0f}%")
    k3.metric(
        "Avg time to resolve",
        f"{stats['avg_resolution_hours']:.0f} hrs" if stats["avg_resolution_hours"] else "n/a",
    )

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.caption("Status breakdown")
        status_counts = stats["status_counts"]
        STATUS_COLORS = {
            "open": theme.CHART_ACCENT_AMBER, "in_progress": theme.CHART_PRIMARY,
            "escalated": theme.CHART_SECONDARY, "resolved": theme.CHART_ACCENT_TEAL,
            "closed": theme.CHART_NEUTRAL,
        }
        pie = go.Figure(go.Pie(
            labels=[s.replace("_", " ").title() for s in status_counts],
            values=list(status_counts.values()),
            hole=0.55,
            marker=dict(colors=[STATUS_COLORS.get(s, theme.CHART_NEUTRAL) for s in status_counts]),
        ))
        pie.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="rgba(0,0,0,0)",
                           font=dict(color=theme.CHART_NEUTRAL), showlegend=True)
        st.plotly_chart(pie, width='stretch')

    with chart_col2:
        st.caption("Priority mix")
        priority_counts = stats["priority_counts"]
        PRIORITY_ORDER = ["critical", "high", "medium", "low"]
        PRIORITY_COLORS = {
            "critical": theme.CHART_SECONDARY, "high": theme.CHART_ACCENT_AMBER,
            "medium": theme.CHART_PRIMARY, "low": theme.CHART_ACCENT_TEAL,
        }
        ordered = [p for p in PRIORITY_ORDER if p in priority_counts]
        bar = go.Figure(go.Bar(
            x=[p.title() for p in ordered], y=[priority_counts[p] for p in ordered],
            marker_color=[PRIORITY_COLORS[p] for p in ordered],
        ))
        bar.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font=dict(color=theme.CHART_NEUTRAL))
        st.plotly_chart(bar, width='stretch')

st.markdown("</div>", unsafe_allow_html=True)

steps = repo.get_playbook(selected_type)

st.markdown(
    f'<div class="sx-card">{card_header("✅", f"Playbook: {selected_type.replace(chr(95), " ").title()}")}',
    unsafe_allow_html=True,
)

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

st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    f'<div class="sx-card">{card_header("🗂️", f"Open cases of type \'{selected_type}\'")}',
    unsafe_allow_html=True,
)
if open_cases:
    st.dataframe(open_cases, width="stretch")
else:
    st.info("No open cases of this type right now.")
st.markdown("</div>", unsafe_allow_html=True)

sidebar_status()