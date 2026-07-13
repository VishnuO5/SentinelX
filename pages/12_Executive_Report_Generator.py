"""
pages/12_Executive_Report_Generator.py
=========================================
One-click PDF export of a full case investigation.
"""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.case_repository import CaseRepository
from src.services.report_generator import generate_case_report_pdf


from src.ui.theme import apply_theme, sidebar_user, sidebar_status
apply_theme()
sidebar_user()
st.title("Executive Report Generator")
st.caption("Generate a one-click, downloadable PDF summary of any investigation.")

repo = CaseRepository()
recent_cases = repo.list_recent_cases(limit=200)

if not recent_cases:
    st.info("No cases found in the database.")
    st.stop()

case_options = {
    f"{c['case_id']} — {c['case_type']} ({c['priority']}, {c['status']})": c["case_id"]
    for c in recent_cases
}

selected_label = st.selectbox("Select a case", list(case_options.keys()))
selected_case_id = case_options[selected_label]

case = repo.get_case(selected_case_id)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Case Type", case["case_type"])
col2.metric("Priority", case["priority"])
col3.metric("Status", case["status"])
col4.metric("Account", case["account_id"])

st.divider()

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

sidebar_status()