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
        """.strip(),
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


_CHIP_PALETTE = [
    "#6D28D9",  # violet
    "#BE185D",  # rose
    "#0F766E",  # teal
    "#B45309",  # amber
    "#1D4ED8",  # blue
    "#4D7C0F",  # lime
    "#9333EA",  # purple
    "#0369A1",  # sky
]


def chip(text: str) -> str:
    """A small colorful pill for plain categorical text that would
    otherwise render as flat, uncolored words in a table (a case type
    like "spam" or "scam", for example). Picks a color deterministically
    from a fixed palette based on the text itself, so the same category
    always gets the same color everywhere it appears, and glows in that
    same color on hover via .sx-chip's currentColor box-shadow -- no
    per-category CSS class needed."""
    color = _CHIP_PALETTE[sum(ord(ch) for ch in text) % len(_CHIP_PALETTE)]
    label = text.replace("_", " ")
    return f'<span class="sx-chip" style="color:{color};background:{color}1A;">{label}</span>'


def pill(text: str, direction: str = "flat") -> str:
    direction = direction if direction in ("up", "down", "flat") else "flat"
    arrow = {"up": "▲", "down": "▼", "flat": "●"}[direction]
    return f'<span class="sx-pill sx-pill-{direction}">{arrow} {text}</span>'


def banner_stat(icon: str, label: str, value, pill_html: str = "") -> str:
    # NOTE: must return a single block with no leading/trailing blank lines.
    # kpi_banner() joins several of these with "".join() -- if each one
    # kept the blank line that a triple-quoted f-string naturally has at
    # its start/end, the joined result has whitespace-only lines *between*
    # each card. Streamlit's Markdown renderer treats an indented block
    # that follows a blank line as a literal code block, so instead of
    # rendering as cards, the raw "<div class=...>" text shows up on the
    # page. .strip() removes exactly that blank line so nothing about the
    # HTML block ever gets interrupted, however many of these get joined.
    return (
        f'<div class="sx-banner-stat">'
        f'<div class="sx-stat-label">{icon} {label}</div>'
        f'<div class="sx-stat-value">{value}</div>'
        f'{pill_html}'
        f'</div>'
    )


def kpi_banner(stats_html: list[str]) -> None:
    grid = "".join(stats_html)
    st.markdown(f'<div class="sx-banner"><div class="sx-banner-grid">{grid}</div></div>', unsafe_allow_html=True)


def proof_stat(value, label: str) -> str:
    """One tile in the Overview page's 'proof of work' stat strip."""
    # Same blank-line fix as banner_stat() above -- proof_grid() joins
    # several of these too.
    return f"""<div class="sx-proof-stat">
        <div class="sx-proof-value">{value}</div>
        <div class="sx-proof-label">{label}</div>
    </div>""".strip()


def proof_grid(stats_html: list[str]) -> None:
    grid = "".join(stats_html)
    st.markdown(f'<div class="sx-proof-grid">{grid}</div>', unsafe_allow_html=True)


def card_header(icon: str, title: str) -> str:
    # Same fix -- this one hasn't shown the bug yet only because nothing
    # currently joins two card_header() calls back to back, but it has
    # the identical shape, so it gets the identical fix pre-emptively.
    return f"""<div class="sx-card-header">
        <div class="sx-card-icon">{icon}</div>
        <div class="sx-card-title">{title}</div>
    </div>""".strip()


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score confidence interval for a binomial proportion
    (default z=1.96). Same method used for PraxisIQ's confidence
    intervals -- appropriate here for precision/recall, which are both
    just proportions (TP / predicted-positive, TP / actual-positive)
    over a finite, real sample of accounts, not population parameters."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + (z ** 2) / n
    centre = p + (z ** 2) / (2 * n)
    adj = z * ((p * (1 - p) / n + (z ** 2) / (4 * n ** 2)) ** 0.5)
    low = (centre - adj) / denom
    high = (centre + adj) / denom
    return (max(0.0, low), min(1.0, high))


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Drop-in replacement for the `st.title("X"); st.caption("Y")` pair
    every page used to open with. Same information, presented as one
    premium unit: an icon chip, a glow-on-hover title (the same
    .sx-glow-text treatment Mission Control and the Overview hero use),
    and a muted subtitle line -- so every page in the app opens with a
    consistent, considered first impression instead of a plain black
    <h1>. A single call, called once at the top of a page, so the
    triple-quoted-string leading-blank-line issue documented on
    banner_stat() above never applies here."""
    # The subtitle <div> is now ALWAYS emitted, even when subtitle="" --
    # never conditionally included or excluded. Investigation Workspace is
    # the only page that calls page_header() without a subtitle, and is
    # the only page where a "</div>" leak has been seen; always emitting
    # a structurally identical string (just with empty text content when
    # there's no subtitle) removes that difference entirely instead of
    # trying to special-case around it. Empty subtitles are hidden via
    # the .sx-page-subtitle:empty rule in style.css, not by omitting the
    # tag in Python.
    st.markdown(
        f'<div class="sx-page-header">'
        f'<div class="sx-page-header-icon">{icon}</div>'
        f'<div>'
        f'<div class="sx-page-title sx-glow-text">{title}</div>'
        f'<div class="sx-page-subtitle">{subtitle}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


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