"""
src/engines/evidence_engine.py
=================================
Turns the nodes/edges dict from EvidenceRepository.get_evidence_graph_data()
into an actual NetworkX graph with a computed spring layout, ready for a
plotting library to draw. This is the "Simplified NetworkX graph (~10
nodes)" module called out in the project brief.
"""

from __future__ import annotations

import networkx as nx

NODE_COLORS = {
    # Mirrors src/ui/theme.py's CHART_* constants -- kept as literal hex
    # here rather than importing the theme module, so the engine layer
    # doesn't take a dependency on the UI layer. Update both together.
    "case": "#7C3AED",       # CHART_PRIMARY (violet)
    "account": "#E11D48",    # CHART_SECONDARY (rose)
    "comment": "#A78BFA",    # CHART_TERTIARY (light violet)
    "report": "#F59E0B",     # CHART_ACCENT_AMBER
    "campaign": "#14B8A6",   # CHART_ACCENT_TEAL
}


def build_graph(graph_data: dict) -> nx.Graph:
    g = nx.Graph()
    for node in graph_data["nodes"]:
        g.add_node(node["id"], label=node["label"], type=node["type"])
    for edge in graph_data["edges"]:
        g.add_edge(edge["source"], edge["target"], label=edge.get("label", ""))
    return g


def compute_layout(g: nx.Graph, seed: int = 42) -> dict:
    """Spring layout -- deterministic given a fixed seed, so the graph
    doesn't visually re-shuffle every time the same case is viewed."""
    return nx.spring_layout(g, seed=seed, k=0.9)


def graph_to_plot_data(graph_data: dict) -> dict:
    """One-stop call for the page: builds the graph, computes layout, and
    returns everything a Plotly figure needs (node positions, colors,
    labels, and edge coordinate pairs)."""
    g = build_graph(graph_data)
    pos = compute_layout(g)

    node_x, node_y, node_labels, node_colors, node_types = [], [], [], [], []
    for node_id in g.nodes:
        x, y = pos[node_id]
        node_x.append(x)
        node_y.append(y)
        node_labels.append(g.nodes[node_id]["label"])
        node_type = g.nodes[node_id]["type"]
        node_types.append(node_type)
        node_colors.append(NODE_COLORS.get(node_type, "#999999"))

    edge_x, edge_y = [], []
    for u, v in g.edges:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    return {
        "node_x": node_x, "node_y": node_y,
        "node_labels": node_labels, "node_colors": node_colors,
        "node_types": node_types,
        "edge_x": edge_x, "edge_y": edge_y,
        "node_count": g.number_of_nodes(), "edge_count": g.number_of_edges(),
    }