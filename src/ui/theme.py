"""
src/ui/theme.py
==================
Shared theme loader so every page gets the same design system.

    from src.ui.theme import apply_theme, sidebar_brand
    apply_theme()
    sidebar_brand()   # Overview.py ONLY, at true module top level,
                       # before st.navigation(...) -- see apply_theme()
    ... page content ...

`sidebar_user()` / `sidebar_status()` are kept as no-op shims so the
existing per-page calls in pages/*.py don't need to be touched; the
brand block + status pulse they used to render now live in
sidebar_brand(), called once from Overview.py.
"""

from __future__ import annotations

import base64
import functools
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@functools.lru_cache(maxsize=1)
def _icon_data_uri() -> str:
    """Base64-embeds assets/logo_icon.png so it can sit inline in the
    sidebar_brand() HTML block. A plain <img src="assets/logo_icon.png">
    won't resolve reliably inside Streamlit's markdown -- the app isn't
    served from that relative path -- so the bytes are inlined instead.
    Cached because it re-reads the same ~28KB file on every rerun otherwise."""
    icon_path = PROJECT_ROOT / "assets" / "logo_icon.png"
    if not icon_path.exists():
        return ""
    encoded = base64.b64encode(icon_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def apply_theme() -> None:
    css_path = PROJECT_ROOT / "assets" / "style.css"
    css = css_path.read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    # NOTE: brand block placement lives in sidebar_brand(), not here.
    # st.logo() was tried first for the "SentinelX / Trust & Safety
    # Analyst" wordmark because it's an official API that places content
    # above the nav -- but st.logo() only accepts a static image, so the
    # text couldn't glow or shift color. sidebar_brand() replaces it
    # with real animated HTML instead. Getting it to sit above the nav
    # is NOT about calling it before st.navigation() in the script --
    # Streamlit's sidebar has three fixed slots (stSidebarHeader,
    # stSidebarNav, stSidebarUserContent) and always renders them in
    # that relative order regardless of call order. The actual fix is
    # the `order: -1` on [data-testid="stSidebarUserContent"] in
    # style.css, which is where sidebar_brand()'s HTML ends up.


def sidebar_brand(role: str = "Trust & Safety Analyst", status_label: str = "Live Monitoring Active") -> None:
    """Renders the SentinelX brand block + live-status pulse as one
    animated unit. Visually placed above the nav list by the
    `order: -1` rule on [data-testid="stSidebarUserContent"] in
    style.css -- see the note in apply_theme() for why call order
    alone can't do this. Call once, from Overview.py."""
    icon_uri = _icon_data_uri()
    mark_inner = f'<img src="{icon_uri}" alt="" />' if icon_uri else "&#128737;"
    st.sidebar.markdown(
        f"""
        <div class="sx-sidebar-brand">
            <div class="sx-mark">{mark_inner}</div>
            <div>
                <div class="sx-wordmark">SentinelX</div>
                <div class="sx-tagline">{role}</div>
            </div>
        </div>
        <div class="sx-sidebar-status">
            <div class="sx-pulse-dot"></div>
            <span>{status_label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_user(role: str = "Trust & Safety Analyst") -> None:
    """No-op. Superseded by sidebar_brand(), which renders the brand
    block above the nav list instead of below it. Kept as a function
    (rather than deleted) purely so the existing per-page
    `sidebar_user()` calls don't need editing; calling it does nothing."""
    return


def sidebar_status(label: str = "Live Monitoring Active") -> None:
    """No-op. Superseded by sidebar_brand(), which now renders the
    status pulse too (bundled with the brand block, above the nav).
    Kept as a function so the existing per-page `sidebar_status()`
    calls don't need editing; calling it does nothing, avoiding a
    second duplicate pulse block at the bottom of the sidebar."""
    return


def badge(text: str, kind: str = "low") -> str:
    kind = kind if kind in ("critical", "high", "medium", "low", "good", "brand") else "low"
    return f'<span class="sx-badge sx-badge-{kind}">{text}</span>'


def pill(text: str, direction: str = "flat") -> str:
    direction = direction if direction in ("up", "down", "flat") else "flat"
    arrow = {"up": "▲", "down": "▼", "flat": "●"}[direction]
    return f'<span class="sx-pill sx-pill-{direction}">{arrow} {text}</span>'


def banner_stat(icon: str, label: str, value, pill_html: str = "") -> str:
    return f"""
    <div class="sx-banner-stat">
        <div class="sx-stat-label">{icon} {label}</div>
        <div class="sx-stat-value">{value}</div>
        {pill_html}
    </div>
    """


def kpi_banner(stats_html: list[str]) -> None:
    grid = "".join(stats_html)
    st.markdown(f'<div class="sx-banner"><div class="sx-banner-grid">{grid}</div></div>', unsafe_allow_html=True)


def proof_stat(value, label: str) -> str:
    """One tile in the Overview page's 'proof of work' stat strip."""
    return f"""
    <div class="sx-proof-stat">
        <div class="sx-proof-value">{value}</div>
        <div class="sx-proof-label">{label}</div>
    </div>
    """


def proof_grid(stats_html: list[str]) -> None:
    grid = "".join(stats_html)
    st.markdown(f'<div class="sx-proof-grid">{grid}</div>', unsafe_allow_html=True)


def card_header(icon: str, title: str) -> str:
    return f"""
    <div class="sx-card-header">
        <div class="sx-card-icon">{icon}</div>
        <div class="sx-card-title">{title}</div>
    </div>
    """


# ---------------------------------------------------------------------
# Chart palette
# ---------------------------------------------------------------------
# Single source of truth for every Plotly chart in the app. Referenced
# by 7 pages as theme.CHART_* -- if this block goes missing again (as
# happened once already during a rewrite of this file), every one of
# those pages crashes with AttributeError on load. There is no
# fallback: these names must exist.

CHART_PRIMARY = "#7C3AED"       # violet -- brand primary, main series
CHART_SECONDARY = "#E11D48"     # rose -- brand secondary, contrast series
CHART_TERTIARY = "#A78BFA"      # light violet -- supporting/muted series
CHART_QUATERNARY = "#FB7185"    # light rose -- supporting/muted series
CHART_ACCENT_AMBER = "#F59E0B"  # warning/medium-severity data points
CHART_ACCENT_TEAL = "#14B8A6"   # positive/resolved data points
CHART_NEUTRAL = "#94A3B8"       # gridlines, muted/inactive series
CHART_LINE = "#D6D3E8"          # connector lines, subtle structure

CHART_CATEGORICAL = [
    CHART_PRIMARY, CHART_SECONDARY, CHART_ACCENT_TEAL,
    CHART_ACCENT_AMBER, CHART_TERTIARY, CHART_QUATERNARY,
]

GRAPH_NODE_COLORS = {
    "case": CHART_PRIMARY,
    "account": CHART_SECONDARY,
    "comment": CHART_TERTIARY,
    "report": CHART_ACCENT_AMBER,
    "campaign": CHART_ACCENT_TEAL,
}