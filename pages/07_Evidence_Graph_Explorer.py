"""
pages/07_Evidence_Graph_Explorer.py
======================================
Evidence Graph Explorer: a simplified NetworkX graph showing
Case -> Account -> Comments/Reports/Campaign connections for a single
case, so an investigator can see the evidence structure at a glance
instead of reading a flat evidence list.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.engines.evidence_engine import graph_to_plot_data
from src.repositories.evidence_repository import EvidenceRepository


from src.ui.theme import apply_theme, sidebar_user, sidebar_status, page_header, card_header, chip
import src.ui.theme as theme
apply_theme()
sidebar_user()
page_header("🕸️", "Evidence Graph Explorer", "Case -> Account -> Comments / Reports / Campaign, as an actual connection graph.")

repo = EvidenceRepository()
cases = repo.list_cases_with_evidence(limit=100)

if not cases:
    st.info("No evidence found. Run scripts/generate_case_evidence.py, then reload the database.")
    st.stop()

st.markdown(f'<div class="sx-card">{card_header("🎯", "Choose a case")}', unsafe_allow_html=True)
case_options = {f"{c['case_id']} — {c['case_type']} — {c['account_id']}": c["case_id"] for c in cases}
choice = st.selectbox("Select a case", options=list(case_options.keys()), label_visibility="collapsed")
selected_case_id = case_options[choice]
st.markdown("</div>", unsafe_allow_html=True)

graph_data = repo.get_evidence_graph_data(selected_case_id)

if graph_data is None:
    st.warning("No evidence graph data for this case.")
    st.stop()

plot_data = graph_to_plot_data(graph_data)

c1, c2, c3 = st.columns(3)
c1.metric("Nodes", plot_data["node_count"])
c2.metric("Connections", plot_data["edge_count"])
c3.metric("Case Type", graph_data["case"]["case_type"].replace("_", " ").title())

st.markdown(f'<div class="sx-card">{card_header("🌐", "Connection graph")}', unsafe_allow_html=True)

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=plot_data["edge_x"], y=plot_data["edge_y"],
    mode="lines", line=dict(width=1.5, color=theme.CHART_LINE),
    hoverinfo="none", showlegend=False,
))

fig.add_trace(go.Scatter(
    x=plot_data["node_x"], y=plot_data["node_y"],
    mode="markers+text",
    marker=dict(size=26, color=plot_data["node_colors"], line=dict(width=2, color="white")),
    text=plot_data["node_labels"], textposition="bottom center",
    textfont=dict(size=10),
    hovertext=[f"{t}: {l}" for t, l in zip(plot_data["node_types"], plot_data["node_labels"])],
    hoverinfo="text", showlegend=False,
))

fig.update_layout(
    height=520,
    xaxis=dict(visible=False), yaxis=dict(visible=False),
    margin=dict(l=20, r=20, t=20, b=20),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig, width="stretch")

st.markdown(
    """
    <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:0.4rem;">
        <span class="sx-chip" style="color:#1D4ED8; background:#1D4ED81A;">🔵 Case</span>
        <span class="sx-chip" style="color:#DC2626; background:#DC26261A;">🔴 Account</span>
        <span class="sx-chip" style="color:#9333EA; background:#9333EA1A;">🟣 Comment</span>
        <span class="sx-chip" style="color:#B45309; background:#B453091A;">🟠 Report</span>
        <span class="sx-chip" style="color:#12946F; background:#12946F1A;">🟢 Campaign</span>
    </div>
    """.strip(),
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown(f'<div class="sx-card">{card_header("🔍", "Evidence Detail")}', unsafe_allow_html=True)
st.markdown(
    f"<div style='margin-bottom:0.8rem;'><b>Account:</b> "
    f"<span class='sx-mono'>{graph_data['account'].get('account_id')}</span> "
    f"&nbsp;·&nbsp; risk score: <b>{graph_data['account'].get('risk_score', 'n/a')}</b></div>",
    unsafe_allow_html=True,
)

detail_html = ""
for node in graph_data["nodes"]:
    if node["type"] not in ("case", "account"):
        detail_html += f"<div style='margin-bottom:6px;'>{chip(node['type'])} {node['label']}</div>"
st.markdown(detail_html or "<span style='color:var(--sx-muted);'>No linked evidence nodes.</span>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

sidebar_status()