"""
pages/10_Counterfactual_Simulator.py
=======================================
Counterfactual Simulator: "what would have happened under a different
policy?" Each scenario is computed against real report/account/timeline
data by scripts/generate_counterfactual_runs.py -- including scenarios
where the honest answer is "nothing would have changed," which is
itself a real finding about how much overlap exists between signals.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.counterfactual_repository import CounterfactualRepository


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header, badge
import src.ui.theme as theme
apply_theme()
sidebar_user()
page_header("🔀", "Counterfactual Simulator", "What would have happened to real cases under a different policy -- computed, not guessed.")

repo = CounterfactualRepository()
runs = repo.list_runs()

if not runs:
    st.info("No counterfactual runs found. Run scripts/generate_counterfactual_runs.py, then reload the database.")
    st.stop()

st.markdown(f'<div class="sx-card">{card_header("📊", "Scenario comparison")}', unsafe_allow_html=True)
fig = go.Figure()
fig.add_trace(go.Bar(
    x=[r["run_id"] for r in runs], y=[r["cases_would_have_flagged"] for r in runs],
    name="Would have flagged (new)", marker_color=theme.CHART_SECONDARY,
))
fig.add_trace(go.Bar(
    x=[r["run_id"] for r in runs], y=[r["cases_would_have_missed"] for r in runs],
    name="Would have missed (dropped)", marker_color=theme.CHART_PRIMARY,
))
fig.update_layout(
    barmode="group", height=380,
    xaxis_title="Scenario", yaxis_title="Accounts",
    margin=dict(l=20, r=20, t=20, b=20),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", y=1.12),
)
st.plotly_chart(fig, width="stretch")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown(f'<div class="sx-card">{card_header("🧭", "Scenario Detail")}', unsafe_allow_html=True)

for r in runs:
    no_change = r["cases_affected_count"] == 0
    st.markdown(
        f"""
        <div style="border:1px solid var(--sx-border); border-radius:var(--sx-radius-sm);
                    padding:1rem 1.2rem; margin-bottom:0.9rem; transition:box-shadow 0.2s ease, border-color 0.2s ease;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:0.3rem;">
                <span class="sx-mono" style="font-weight:700; color:var(--sx-brand-strong);">{r['run_id']}</span>
                {badge("no change", "low") if no_change else badge("policy shift", "brand")}
            </div>
            <div style="color:var(--sx-ink); font-size:0.92rem; margin-bottom:0.2rem;">{r['policy_description']}</div>
        </div>
        """.strip(),
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Accounts Affected", r["cases_affected_count"])
    c2.metric("Newly Flagged", r["cases_would_have_flagged"])
    c3.metric("Would Have Missed", r["cases_would_have_missed"])

    if r["cases_affected_count"] > 0:
        # 95% Wilson CI on "of the accounts this policy change affects,
        # what share would actually be newly flagged" -- affected_count
        # is a real but finite sample, so a bare percentage overstates
        # how precisely known that split is, especially on smaller runs.
        flag_lo, flag_hi = theme.wilson_ci(r["cases_would_have_flagged"], r["cases_affected_count"])
        st.caption(
            f"Share newly flagged: {r['cases_would_have_flagged'] / r['cases_affected_count'] * 100:.0f}% "
            f"(95% CI: [{flag_lo*100:.0f}%, {flag_hi*100:.0f}%] of {r['cases_affected_count']} affected accounts)"
        )

    if no_change:
        st.caption(
            "No change -- every account this policy would target is already "
            "captured by the current detection signals (device reuse, report "
            "volume, and account age already correlate strongly with real "
            "campaign membership in this dataset)."
        )
    st.markdown("<div style='margin-bottom:0.6rem;'></div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

sidebar_status()