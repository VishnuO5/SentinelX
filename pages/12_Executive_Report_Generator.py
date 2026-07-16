"""
pages/12_Executive_Report_Generator.py
=========================================
One-click PDF export of a full case investigation.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.case_repository import CaseRepository
from src.repositories.moderator_repository import ModeratorRepository
from src.services.report_generator import generate_case_report_pdf


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header, badge
import src.ui.theme as theme
apply_theme()
sidebar_user()
page_header("📄", "Executive Report Generator", "Generate a one-click, downloadable PDF summary of any investigation.")

repo = CaseRepository()
recent_cases = repo.list_recent_cases(limit=200)

if not recent_cases:
    st.info("No cases found in the database.")
    st.stop()

PRIORITY_KIND = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
STATUS_KIND = {"open": "medium", "in_progress": "brand", "escalated": "critical",
               "resolved": "good", "closed": "low"}

st.markdown(f'<div class="sx-card">{card_header("🎯", "Choose a case")}', unsafe_allow_html=True)
case_options = {
    f"{c['case_id']} — {c['case_type']} ({c['priority']}, {c['status']})": c["case_id"]
    for c in recent_cases
}

selected_label = st.selectbox("Select a case", list(case_options.keys()), label_visibility="collapsed")
selected_case_id = case_options[selected_label]

case = repo.get_case(selected_case_id)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Case Type", case["case_type"].replace("_", " ").title())
col2.metric("Priority", case["priority"].title())
col3.metric("Status", case["status"].replace("_", " ").title())
col4.metric("Account", case["account_id"])
st.markdown(
    f"<div style='margin-top:0.6rem;'>"
    f"{badge(case['priority'], PRIORITY_KIND.get(case['priority'], 'low'))} "
    f"{badge(case['status'].replace('_', ' '), STATUS_KIND.get(case['status'], 'low'))}"
    f"</div>",
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# ── On-screen preview ────────────────────────────────────────────────────
# The PDF is a black box until you download it -- this shows the same
# underlying numbers (signal breakdown + recent notes/audit trail) that
# generate_case_report_pdf() pulls, so there's something to look at
# before committing to a download.
bundle = repo.get_investigation_bundle(selected_case_id)
mod_repo = ModeratorRepository()
notes = mod_repo.get_notes(selected_case_id)
audit = mod_repo.get_audit_log(selected_case_id)

st.markdown(f'<div class="sx-card">{card_header("👁️", "Report preview")}', unsafe_allow_html=True)

signals = (bundle or {}).get("signals") or {}
signal_rows = [
    ("Account age", signals.get("account_age_signal")),
    ("Report volume", signals.get("report_volume_signal")),
    ("Device reuse", signals.get("device_reuse_signal")),
    ("IP region", signals.get("ip_region_signal")),
    ("Toxicity", signals.get("toxicity_signal")),
]
signal_rows = [(n, v) for n, v in signal_rows if v is not None]

prev_col1, prev_col2 = st.columns([3, 2])
with prev_col1:
    st.caption("Signal breakdown — one of three charts included in the PDF")
    if signal_rows:
        signal_rows.sort(key=lambda r: r[1])
        fig = go.Figure(go.Bar(
            x=[r[1] for r in signal_rows], y=[r[0] for r in signal_rows], orientation="h",
            marker_color=theme.CHART_PRIMARY,
            text=[f"{r[1]:.2f}" for r in signal_rows], textposition="outside",
        ))
        fig.update_layout(
            height=200, margin=dict(l=10, r=30, t=10, b=10),
            xaxis=dict(range=[0, 1]),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=theme.CHART_NEUTRAL),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No signal score computed for this account yet.")

with prev_col2:
    st.caption(f"Investigation notes ({len(notes)}) & audit trail ({len(audit)}) included in report")
    if notes:
        latest = notes[0]
        st.markdown(f"**Latest note** — {latest.get('moderator_name') or latest.get('moderator_id')}")
        st.caption(latest.get("note_text", "")[:180])
    else:
        st.caption("No investigation notes on record yet.")
    if audit:
        st.markdown(f"**Last action** — {audit[0].get('action', '')}")
        st.caption(audit[0].get("timestamp", ""))

st.markdown("</div>", unsafe_allow_html=True)

st.markdown(f'<div class="sx-card">{card_header("🖨️", "Generate report")}', unsafe_allow_html=True)
st.caption("Pulls evidence, signal scores, and the AI investigator's assessment into a single downloadable PDF.")
st.markdown(
    """
    <div style="display:flex; gap:16px; flex-wrap:wrap; margin:0.5rem 0 0.8rem 0; font-size:0.85rem; color:var(--sx-muted);">
        <span>📊 Composite risk meter</span>
        <span>📈 Signal breakdown chart</span>
        <span>🥧 Report reasons chart</span>
        <span>🧠 AI assessment</span>
        <span>📝 Notes &amp; audit trail</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.button("Generate PDF Report", type="primary"):
    with st.spinner("Building report — pulling evidence, signals, and AI assessment..."):
        try:
            pdf_bytes = generate_case_report_pdf(selected_case_id)
            st.session_state["report_pdf"] = pdf_bytes
            st.session_state["report_case_id"] = selected_case_id
            st.success("Report generated.")
        except Exception as exc:
            st.error(f"Could not generate report: {exc}")

if (
    st.session_state.get("report_pdf")
    and st.session_state.get("report_case_id") == selected_case_id
):
    st.download_button(
        label="Download PDF",
        data=st.session_state["report_pdf"],
        file_name=f"SentinelX_Report_{selected_case_id}.pdf",
        mime="application/pdf",
    )

st.markdown("</div>", unsafe_allow_html=True)

sidebar_status()