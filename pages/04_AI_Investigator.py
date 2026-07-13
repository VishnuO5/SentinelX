"""
pages/04_AI_Investigator.py
=============================
The centerpiece module: pick a case, and the AI Investigator produces a
Summary + Evidence + Recommendation, grounded in the real evidence bundle
(case, account, signals, comments, reports, campaign) pulled straight
from the database.

Uses Groq if GROQ_API_KEY is set in the environment; otherwise falls
back to a deterministic, evidence-based writeup (see src/ai/investigator.py
for why the fallback is real logic, not a placeholder).
"""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai.investigator import AIInvestigator
from src.ai.reasoning_engine import ReasoningEngine
from src.repositories.case_repository import CaseRepository


from src.ui.theme import apply_theme, sidebar_user, sidebar_status
apply_theme()
sidebar_user()
st.title("AI Investigator")
st.caption("Summary, Evidence, and Recommendation for a case -- generated from real data, not a template guess.")

repo = CaseRepository()
investigator = AIInvestigator()
reasoner = ReasoningEngine()

if not investigator.api_key:
    st.info(
        "No GROQ_API_KEY found in the environment -- running in fallback mode. "
        "The writeup below is still built entirely from real evidence in the "
        "database, just assembled by rules instead of an LLM. Set GROQ_API_KEY "
        "to switch to live LLM generation.",
        icon="ℹ️",
    )

# ── Case picker ──────────────────────────────────────────────────────────
st.subheader("Select a case")

recent_cases = repo.list_recent_cases(limit=50)
case_options = {
    f"{c['case_id']} — {c['case_type']} ({c['priority']}, {c['status']}) — {c['account_id']}": c["case_id"]
    for c in recent_cases
}

col1, col2 = st.columns([2, 1])
with col1:
    choice = st.selectbox("Recent cases", options=["-- select --"] + list(case_options.keys()))
with col2:
    manual_case_id = st.text_input("...or type a case ID", placeholder="e.g. CASE-00001")

selected_case_id = manual_case_id.strip() if manual_case_id.strip() else case_options.get(choice)

if selected_case_id:
    bundle = repo.get_investigation_bundle(selected_case_id)

    if bundle is None:
        st.warning(f"No case found with ID '{selected_case_id}'.")
    else:
        st.divider()

        # ── Evidence panel ───────────────────────────────────────────
        c1, c2, c3 = st.columns(3)
        c1.metric("Case Type", bundle["case"]["case_type"])
        c2.metric("Priority", bundle["case"]["priority"])
        c3.metric("Composite Risk", f"{(bundle['signals'] or {}).get('composite_risk_score', 0):.3f}")

        with st.expander("Raw evidence bundle (what the investigator sees)", expanded=False):
            st.write("**Account**", bundle["account"])
            st.write("**Signals**", bundle["signals"])
            st.write("**Campaign**", bundle["campaign"] or "Not linked to a campaign")
            st.write("**Report reasons**", bundle["reports"])
            st.write("**Top comments by toxicity**", bundle["comments"])

        st.divider()

        # ── Run investigation ───────────────────────────────────────
        if st.button("Run AI Investigation", type="primary"):
            with st.spinner("Analyzing evidence..."):
                result = investigator.investigate(bundle)
            st.session_state["last_investigation"] = result
            st.session_state["last_investigation_case_id"] = selected_case_id

        # FIX: previously this read st.session_state["last_investigation"]
        # unconditionally, so switching to a different case in the dropdown
        # without clicking "Run AI Investigation" again left the PREVIOUS
        # case's writeup on screen -- looking like it belonged to the newly
        # selected case. Now the cached result is only shown if it actually
        # belongs to the currently selected case.
        result = st.session_state.get("last_investigation")
        result_case_id = st.session_state.get("last_investigation_case_id")
        if result_case_id != selected_case_id:
            result = None

        if result and "error" not in result:
            mode_label = "🤖 LLM-generated (Groq)" if result.get("mode") == "llm" else "📋 Rule-based (fallback)"
            st.caption(mode_label)

            st.subheader("Summary")
            st.write(result.get("summary", ""))

            st.subheader("Evidence")
            st.markdown(result.get("evidence", ""))

            st.subheader("Recommendation")
            rec_col, conf_col = st.columns([3, 1])
            rec_col.success(result.get("recommendation", ""))
            conf_col.metric("Confidence", result.get("confidence", "n/a"))

            if result.get("fallback_reason"):
                st.caption(f"Note: {result['fallback_reason']}")

            # ── Reasoning trace ───────────────────────────────────
            # WIRING NOTE: this calls src/ai/reasoning_engine.py's
            # ReasoningEngine LIVE against the same evidence bundle --
            # a visible, step-by-step Evidence -> Pattern -> Risk
            # Correlation -> Verdict trace, distinct from the one-shot
            # summary above. Explainability, not just a verdict.
            with st.expander("Show step-by-step reasoning trace", expanded=False):
                trace = reasoner.reason(bundle)
                trace_mode_label = (
                    "🤖 LLM-generated (Groq)" if trace.get("mode") == "llm"
                    else "📋 Rule-based (fallback)"
                )
                st.caption(trace_mode_label)
                for step in trace.get("steps", []):
                    st.markdown(f"**{step['step']}**")
                    st.write(step["content"])

sidebar_status()