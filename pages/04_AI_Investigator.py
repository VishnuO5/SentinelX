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

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai.investigator import AIInvestigator
from src.ai.reasoning_engine import ReasoningEngine
from src.repositories.case_repository import CaseRepository


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header, badge
import src.ui.theme as theme
apply_theme()
sidebar_user()
page_header("🤖", "AI Investigator", "Summary, Evidence, and Recommendation for a case -- generated from real data, not a template guess.")

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
st.markdown(f'<div class="sx-card">{card_header("🎯", "Select a case")}', unsafe_allow_html=True)

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
st.markdown("</div>", unsafe_allow_html=True)

selected_case_id = manual_case_id.strip() if manual_case_id.strip() else case_options.get(choice)

PRIORITY_KIND = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}

if selected_case_id:
    bundle = repo.get_investigation_bundle(selected_case_id)

    if bundle is None:
        st.warning(f"No case found with ID '{selected_case_id}'.")
    else:
        # ── Evidence panel ───────────────────────────────────────────
        st.markdown(f'<div class="sx-card">{card_header("🧾", "Evidence panel")}', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Case Type", bundle["case"]["case_type"].replace("_", " ").title())
        c2.metric("Priority", bundle["case"]["priority"].title())
        c3.metric("Composite Risk", f"{(bundle['signals'] or {}).get('composite_risk_score', 0):.3f}")
        st.markdown(
            f"<div style='margin:0.4rem 0 0.8rem 0;'>"
            f"{badge(bundle['case']['priority'], PRIORITY_KIND.get(bundle['case']['priority'], 'low'))}</div>",
            unsafe_allow_html=True,
        )

        with st.expander("Raw evidence bundle (what the investigator sees)", expanded=False):
            st.write("**Account**", bundle["account"])
            st.write("**Signals**", bundle["signals"])
            st.write("**Campaign**", bundle["campaign"] or "Not linked to a campaign")
            st.write("**Report reasons**", bundle["reports"])
            st.write("**Top comments by toxicity**", bundle["comments"])
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Signal breakdown chart ───────────────────────────────────
        # Which of the 5 fused signals is actually driving this account's
        # composite risk score -- the same numbers the AI Investigator's
        # recommendation is grounded in, shown visually instead of only
        # buried in the raw evidence expander above.
        signals = bundle["signals"] or {}
        signal_rows = [
            ("Account age", signals.get("account_age_signal")),
            ("Report volume", signals.get("report_volume_signal")),
            ("Device reuse", signals.get("device_reuse_signal")),
            ("IP region", signals.get("ip_region_signal")),
            ("Toxicity", signals.get("toxicity_signal")),
        ]
        signal_rows = [(name, val) for name, val in signal_rows if val is not None]

        if signal_rows:
            st.markdown(f'<div class="sx-card">{card_header("📊", "Signal breakdown")}', unsafe_allow_html=True)
            signal_rows.sort(key=lambda r: r[1])
            names = [r[0] for r in signal_rows]
            values = [r[1] for r in signal_rows]
            bar_colors = [
                theme.CHART_SECONDARY if v >= 0.66 else theme.CHART_ACCENT_AMBER if v >= 0.33 else theme.CHART_ACCENT_TEAL
                for v in values
            ]
            fig = go.Figure(go.Bar(
                x=values, y=names, orientation="h",
                marker_color=bar_colors,
                text=[f"{v:.2f}" for v in values], textposition="outside",
            ))
            fig.update_layout(
                height=230, margin=dict(l=10, r=30, t=10, b=10),
                xaxis=dict(range=[0, 1], title="Signal strength (0-1)"),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=theme.CHART_NEUTRAL),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Each bar is a real computed signal for this account -- not illustrative. This is what the recommendation below is grounded in.")
            st.markdown("</div>", unsafe_allow_html=True)

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

            st.markdown(f'<div class="sx-card">{card_header("🧠", "AI Assessment")}', unsafe_allow_html=True)
            st.caption(mode_label)

            st.markdown('<div class="sx-section-header" style="margin-top:0.6rem;"><div class="sx-section-title">Summary</div></div>', unsafe_allow_html=True)
            st.write(result.get("summary", ""))

            st.markdown('<div class="sx-section-header" style="margin-top:0.6rem;"><div class="sx-section-title">Evidence</div></div>', unsafe_allow_html=True)
            st.markdown(result.get("evidence", ""))

            st.markdown('<div class="sx-section-header" style="margin-top:0.6rem;"><div class="sx-section-title">Recommendation</div></div>', unsafe_allow_html=True)
            rec_col, conf_col = st.columns([3, 1])
            rec_col.success(result.get("recommendation", ""))

            confidence_label = result.get("confidence", "n/a")
            CONFIDENCE_SCALE = {"High": 0.85, "Medium": 0.55, "Low": 0.25}
            conf_numeric = CONFIDENCE_SCALE.get(confidence_label)
            with conf_col:
                if conf_numeric is not None:
                    gauge_color = (
                        theme.CHART_ACCENT_TEAL if confidence_label == "High"
                        else theme.CHART_ACCENT_AMBER if confidence_label == "Medium"
                        else theme.CHART_SECONDARY
                    )
                    gfig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=conf_numeric * 100,
                        number={"suffix": "%", "font": {"size": 22}},
                        gauge={
                            "axis": {"range": [0, 100], "visible": False},
                            "bar": {"color": gauge_color, "thickness": 0.9},
                            "bgcolor": "rgba(148,163,184,0.15)",
                            "borderwidth": 0,
                        },
                    ))
                    gfig.update_layout(height=110, margin=dict(l=10, r=10, t=10, b=0),
                                        paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(gfig, use_container_width=True)
                    st.caption(f"Confidence: **{confidence_label}**")
                else:
                    st.metric("Confidence", confidence_label)

            if result.get("fallback_reason"):
                st.caption(f"Note: {result['fallback_reason']}")
            st.markdown("</div>", unsafe_allow_html=True)

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