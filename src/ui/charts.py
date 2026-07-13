"""
src/ui/charts.py
===================
Shared Plotly chart theming, matching assets/style.css's actual current
palette (light canvas, violet/rose brand family) -- so every chart looks
like it belongs to the same design system instead of each page picking
its own ad hoc colors.
"""

from __future__ import annotations

import plotly.graph_objects as go

# Ordered palette for multi-series charts. Violet -> magenta -> rose,
# matching assets/style.css's --sx-brand / --sx-intelligence family.
GLOW_PALETTE = ["#7C3AED", "#A855F7", "#D946EF", "#E11D48", "#F97316", "#BE123C"]

COLOR = {
    "brand": "#7C3AED",
    "brand_strong": "#6D28D9",
    "brand_glow": "#C4B5FD",
    "magenta": "#A855F7",
    "rose": "#E11D48",
    "rose_strong": "#BE123C",
    "critical": "#DC2626",
    "high": "#EA580C",
    "medium": "#D97706",
    "good": "#12946F",
    "muted": "#667085",
    "ink": "#101828",
    "grid": "rgba(124, 58, 237, 0.10)",
}

PAPER_BG = "rgba(0,0,0,0)"
PLOT_BG = "rgba(0,0,0,0)"


def apply_chart_theme(fig: go.Figure, height: int | None = None) -> go.Figure:
    layout_kwargs = dict(
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family="Inter, sans-serif", size=11, color=COLOR["muted"]),
        legend=dict(font=dict(color=COLOR["muted"])),
        xaxis=dict(showgrid=False, showline=True, linecolor=COLOR["grid"], color=COLOR["muted"]),
        yaxis=dict(showgrid=True, gridcolor=COLOR["grid"], zeroline=False, color=COLOR["muted"]),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    if height:
        layout_kwargs["height"] = height
    fig.update_layout(**layout_kwargs)
    return fig