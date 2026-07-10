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

st.set_page_config(layout="wide")
st.title("Evidence Graph Explorer")
st.caption("Case -> Account -> Comments / Reports / Campaign, as an actual connection graph.")

repo = EvidenceRepository()
cases = repo.list_cases_with_evidence(limit=100)

if not cases:
    st.info("No evidence found. Run scripts/generate_case_evidence.py, then reload the database.")
    st.stop()

case_options = {f"{c['case_id']} — {c['case_type']} — {c['account_id']}": c["case_id"] for c in cases}
choice = st.selectbox("Select a case", options=list(case_options.keys()))
selected_case_id = case_options[choice]

graph_data = repo.get_evidence_graph_data(selected_case_id)

if graph_data is None:
    st.warning("No evidence graph data for this case.")
    st.stop()

plot_data = graph_to_plot_data(graph_data)

c1, c2, c3 = st.columns(3)
c1.metric("Nodes", plot_data["node_count"])
c2.metric("Connections", plot_data["edge_count"])
c3.metric("Case Type", graph_data["case"]["case_type"])

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=plot_data["edge_x"], y=plot_data["edge_y"],
    mode="lines", line=dict(width=1.5, color="#CCCCCC"),
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
    height=550,
    xaxis=dict(visible=False), yaxis=dict(visible=False),
    margin=dict(l=20, r=20, t=20, b=20),
    plot_bgcolor="white",
)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "🔵 Case · 🔴 Account · 🟣 Comment · 🟠 Report · 🟢 Campaign"
)

st.divider()
st.subheader("Evidence Detail")
st.write(f"**Account:** {graph_data['account'].get('account_id')} "
         f"(risk score: {graph_data['account'].get('risk_score', 'n/a')})")

for node in graph_data["nodes"]:
    if node["type"] not in ("case", "account"):
        st.write(f"- **{node['type']}**: {node['label']}")