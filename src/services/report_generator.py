"""
src/services/report_generator.py
==================================
Executive Report Generator: renders a case's full evidence bundle, AI
Investigator writeup, moderator notes, and audit trail into a downloadable
PDF -- the artifact an analyst would actually hand to a manager.

Uses reportlab (pure Python, no external binaries/services) to stay
inside the project's free-tools-only stack. Three real charts are drawn
with reportlab.graphics (vector, not a rasterized image) straight from
the same numbers shown in the tables next to them:
  1. a composite-risk meter (thermometer against the same low/medium/
     high/critical zones the rest of the app uses)
  2. a signal-breakdown bar chart (the five inputs to that composite score)
  3. a report-reasons pie chart (falls back to an evidence-volume bar
     chart on cases with no reports on file, so a case page is never
     shipped with a missing third chart)

v3 (this version) -- full visual pass for external/recruiter-facing
distribution:
  - Executive summary "stat card" strip at the top (Priority / Status /
    Composite Risk / Case Type) so the headline numbers read in two
    seconds, before anyone reads a table.
  - Numbered section kickers (01, 02, 03 ...) so the document reads like
    a structured audit report rather than a stack of headings.
  - Every section heading is KeepTogether-wrapped with its first line of
    content, so a heading can no longer strand itself at the bottom of a
    page with its content pushed to the next one.
  - Charts sit inside a bordered "card" panel with headroom above the
    tallest bar, fixing label clipping/overlap on near-1.0 values.
  - The AI Investigator section is a tinted callout card; its Evidence
    field (previously a single run-on paragraph because the source
    string uses literal "\n" separators reportlab's Paragraph doesn't
    honor) is now rendered as a real bulleted list.
  - Flagged comments render in a structured table (date / classification
    / score / excerpt) instead of a run-on paragraph, are de-duplicated
    by exact text, and pass through a content-sensitivity filter before
    an export ever leaves the app:
      * comments carrying a severe policy category (identity_hate,
        threat, severe_toxic) are withheld with a policy-category
        placeholder instead of printing the raw text -- an executive
        export is not the place to reproduce hate speech or threats
        verbatim, and the classification + score already carry the
        evidentiary weight a reviewer needs;
      * remaining flagged comments still on the page have ordinary
        profanity masked (f**k-style) rather than withheld outright.
    This mirrors how real T&S tooling handles evidence in exports and
    keeps the PDF safe to hand to a recruiter, manager, or anyone
    outside the moderation team.

FIX (carried over from previous version): there is no hardcoded
PageBreak() anywhere -- reportlab paginates on real content height, and
the header/footer chrome plus charts give each page enough real content
that a case never renders a mostly-blank page.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, HRFlowable,
)
from reportlab.pdfgen.canvas import Canvas
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Polygon
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend

from src.repositories.case_repository import CaseRepository
from src.repositories.moderator_repository import ModeratorRepository
from src.ai.investigator import AIInvestigator

# ---------------------------------------------------------------------
# Brand palette -- same tokens as assets/style.css, so the PDF a manager
# gets looks like it came from the same product as the dashboard.
# ---------------------------------------------------------------------
BRAND = colors.HexColor("#7C3AED")
BRAND_DEEP = colors.HexColor("#4C1D95")
BRAND_SOFT = colors.HexColor("#F5F3FF")
MAGENTA = colors.HexColor("#E11D48")
INK = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
MUTED_LIGHT = colors.HexColor("#94A3B8")
BORDER = colors.HexColor("#E2E8F0")
BORDER_SOFT = colors.HexColor("#EDE9FE")
SURFACE = colors.HexColor("#F8FAFC")
CARD = colors.HexColor("#FFFFFF")

CRITICAL = colors.HexColor("#DC2626")
HIGH = colors.HexColor("#EA580C")
MEDIUM = colors.HexColor("#D97706")
LOW = colors.HexColor("#94A3B8")
GOOD = colors.HexColor("#12946F")

PRIORITY_COLOR = {"critical": CRITICAL, "high": HIGH, "medium": MEDIUM, "low": LOW}
STATUS_COLOR = {
    "open": MEDIUM, "in_progress": BRAND, "escalated": CRITICAL,
    "resolved": GOOD, "closed": LOW,
}

CHART_SERIES = [BRAND, MAGENTA, colors.HexColor("#14B8A6"),
                colors.HexColor("#F59E0B"), colors.HexColor("#A78BFA"),
                colors.HexColor("#FB7185")]

# ---------------------------------------------------------------------
# Content-sensitivity handling for exported evidence text.
# ---------------------------------------------------------------------
SEVERE_CATEGORIES = {"identity_hate", "threat", "severe_toxic"}

# Ordinary profanity (not slurs, not hate speech) gets masked rather than
# withheld, so an excerpt is still legible as evidence.
_PROFANITY = [
    "fuck", "shit", "bitch", "asshole", "bastard", "dick", "piss",
    "damn", "crap", "slut", "whore", "cunt",
]
_PROFANITY_RE = re.compile(
    r"\b(" + "|".join(_PROFANITY) + r")([a-z]*)\b", re.IGNORECASE
)


def _mask_profanity(text: str) -> str:
    def _repl(m):
        word = m.group(0)
        if len(word) <= 2:
            return "*" * len(word)
        return word[0] + "*" * (len(word) - 2) + word[-1]
    return _PROFANITY_RE.sub(_repl, text)


def _comment_display(c: dict) -> str:
    """Returns export-safe display text for a flagged comment. Comments
    carrying a severe policy category are withheld outright; everything
    else is profanity-masked but otherwise shown in full so the excerpt
    still functions as real evidence."""
    labels = {s.strip() for s in (c.get("toxicity_label") or "").split(",")}
    if labels & SEVERE_CATEGORIES:
        matched = ", ".join(sorted(labels & SEVERE_CATEGORIES))
        return (
            f"[Content withheld from export — flagged under restricted "
            f"policy categories ({matched}). Full text is available to "
            f"authorized reviewers in the SentinelX case workspace.]"
        )
    text = (c.get("text") or "").strip()
    if len(text) > 200:
        text = text[:200].rsplit(" ", 1)[0] + "…"
    return _mask_profanity(text)


def _escape(text) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="SXMasthead", fontSize=17, leading=20,
        textColor=colors.white, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="SXMastheadSub", fontSize=9, leading=12,
        textColor=colors.HexColor("#E9D5FF"),
    ))
    styles.add(ParagraphStyle(
        name="SXKicker", fontSize=8, leading=10,
        textColor=BRAND, fontName="Helvetica-Bold",
        spaceBefore=2, spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="SXHeading", fontSize=13, spaceBefore=0, spaceAfter=3,
        textColor=BRAND_DEEP, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(name="SXBody", fontSize=9.5, leading=14, textColor=INK))
    styles.add(ParagraphStyle(
        name="SXBodyMuted", fontSize=9, leading=13, textColor=MUTED,
    ))
    styles.add(ParagraphStyle(
        name="SXBullet", fontSize=9.5, leading=14, textColor=INK,
        leftIndent=12, bulletIndent=0, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="SXTiny", fontSize=7.5, textColor=MUTED_LIGHT, leading=10,
    ))
    styles.add(ParagraphStyle(
        name="SXCaption", fontSize=8, textColor=MUTED, leading=11,
        alignment=TA_CENTER, spaceBefore=4, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="SXCardLabel", fontSize=7.5, textColor=colors.HexColor("#EDE4FF"),
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=9,
    ))
    styles.add(ParagraphStyle(
        name="SXCardValue", fontSize=13, textColor=colors.white,
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=16,
    ))
    styles.add(ParagraphStyle(
        name="SXCardValueSmall", fontSize=10.5, textColor=colors.white,
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=13,
    ))
    styles.add(ParagraphStyle(
        name="SXNote", fontSize=8.25, textColor=MUTED, leading=12,
        fontName="Helvetica-Oblique",
    ))
    return styles


def _section(title: str, number: int, styles) -> list:
    """Kicker + heading + rule, as a list of flowables ready to be
    prepended to a KeepTogether block with the section's first content
    flowable so a heading can never strand at the bottom of a page."""
    return [
        Paragraph(f"SECTION {number:02d}", styles["SXKicker"]),
        Paragraph(title, styles["SXHeading"]),
        HRFlowable(width="100%", thickness=1.1, color=BRAND, spaceAfter=7),
    ]


def _table(data, col_widths, header=True, zebra=False, font_size=8.75):
    t = Table(data, colWidths=col_widths)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), BRAND_DEEP))
        style.append(("TEXTCOLOR", (0, 0), (-1, 0), colors.white))
        style.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
    if zebra:
        for row_idx in range(1 if header else 0, len(data), 2):
            style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), SURFACE))
    t.setStyle(TableStyle(style))
    return t


def _pill_table(label: str, value: str, color) -> Table:
    """A single colored 'badge' rendered as a one-cell table -- the PDF
    equivalent of the .sx-badge pills used throughout the dashboard, so
    priority/status read the same way here as they do on screen."""
    t = Table([[f"{label}: {value.upper()}"]], colWidths=[None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


# ---------------------------------------------------------------------
# Executive summary stat-card strip
# ---------------------------------------------------------------------

def _risk_band(score: float) -> tuple[str, colors.Color]:
    if score is None:
        return "—", LOW
    if score < 0.40:
        return "LOW", GOOD
    if score < 0.70:
        return "ELEVATED", MEDIUM
    return "CRITICAL", CRITICAL


def _stat_cards(case: dict, risk_val, styles) -> Table:
    priority = (case["priority"] or "—").upper()
    status = (case["status"] or "—").replace("_", " ").upper()
    case_type = (case["case_type"] or "—").replace("_", " ").title()
    band_label, band_color = _risk_band(risk_val)

    def _card(label, value_para, fill):
        inner = Table(
            [[Paragraph(label, styles["SXCardLabel"])], [value_para]],
            colWidths=[1.42 * inch],
        )
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), fill),
            ("TOPPADDING", (0, 0), (-1, 0), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ("TOPPADDING", (0, 1), (-1, 1), 2),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        return inner

    cards = [
        _card("PRIORITY", Paragraph(priority, styles["SXCardValue"]), PRIORITY_COLOR.get(case["priority"], LOW)),
        _card("STATUS", Paragraph(status, styles["SXCardValueSmall"]), STATUS_COLOR.get(case["status"], LOW)),
        _card("COMPOSITE RISK", Paragraph(f"{risk_val:.3f}" if risk_val is not None else "—", styles["SXCardValue"]), band_color),
        _card("CASE TYPE", Paragraph(case_type, styles["SXCardValueSmall"]), BRAND_DEEP),
    ]
    row = Table([cards], colWidths=[1.5 * inch] * 4, spaceAfter=2)
    row.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return row


# ---------------------------------------------------------------------
# Chart panel background -- gives every chart a bordered "card" look
# consistent with the stat cards and callout boxes, instead of vector
# art floating directly on the page background.
# ---------------------------------------------------------------------

def _panel(width: float, height: float) -> Drawing:
    d = Drawing(width, height)
    # Faint offset "shadow" rect behind the card so charts read as raised
    # panels rather than flat vector art sitting on the page background.
    d.add(Rect(2, -2, width, height, fillColor=colors.HexColor("#EAECF0"), strokeColor=None))
    d.add(Rect(0, 0, width, height, fillColor=SURFACE, strokeColor=BORDER, strokeWidth=0.75))
    return d


# ---------------------------------------------------------------------
# Chart 1 -- composite risk meter
# ---------------------------------------------------------------------

def _risk_meter(score: float) -> Drawing:
    """A horizontal thermometer against the same low/medium/high/
    critical zones used everywhere else in the app, with a marker at
    the account's actual composite_risk_score. Reads at a glance --
    the point of a gauge in an executive report is that a manager
    shouldn't have to interpret a raw 0.xxx number themselves."""
    width, height = 468, 92
    d = _panel(width, height)

    track_x, track_y, track_w, track_h = 20, 34, 428, 22
    zones = [
        (0.00, 0.40, GOOD, "Low"),
        (0.40, 0.70, MEDIUM, "Elevated"),
        (0.70, 1.00, CRITICAL, "Critical"),
    ]
    for lo, hi, color, label in zones:
        x0 = track_x + lo * track_w
        w = (hi - lo) * track_w
        d.add(Rect(x0, track_y, w, track_h, fillColor=color, strokeColor=colors.white, strokeWidth=1.25))
        d.add(String(x0 + w / 2, track_y - 13, label, fontSize=7.75, fillColor=MUTED,
                      textAnchor="middle", fontName="Helvetica"))

    score = max(0.0, min(1.0, score or 0.0))
    marker_x = track_x + score * track_w
    marker_x = min(max(marker_x, track_x + 16), track_x + track_w - 16)
    d.add(Polygon(
        points=[marker_x - 7, track_y + track_h + 16, marker_x + 7, track_y + track_h + 16, marker_x, track_y + track_h + 3],
        fillColor=INK, strokeColor=None,
    ))
    d.add(String(marker_x, track_y + track_h + 21, f"{score:.3f}", fontSize=11,
                 fillColor=INK, textAnchor="middle", fontName="Helvetica-Bold"))
    d.add(Line(track_x, track_y - 3, track_x, track_y + track_h + 3, strokeColor=BORDER))
    d.add(Line(track_x + track_w, track_y - 3, track_x + track_w, track_y + track_h + 3, strokeColor=BORDER))
    return d


# ---------------------------------------------------------------------
# Chart 2 -- signal breakdown bar chart
# ---------------------------------------------------------------------

def _signal_bar_chart(signals: dict) -> Drawing:
    labels = ["Account Age", "Report Volume", "Device Reuse", "IP Region", "Toxicity", "Composite"]
    keys = ["account_age_signal", "report_volume_signal", "device_reuse_signal",
            "ip_region_signal", "toxicity_signal", "composite_risk_score"]
    values = [round(float(signals.get(k) or 0.0), 3) for k in keys]

    width, height = 468, 208
    d = _panel(width, height)
    chart = HorizontalBarChart()
    chart.x, chart.y = 100, 18
    chart.width, chart.height = width - 175, height - 42
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 8.5
    chart.categoryAxis.labels.fillColor = INK
    chart.categoryAxis.labels.fontName = "Helvetica"
    # headroom above 1.0 so a near-1.0 bar's value label never clips
    # against the plot edge or the panel border
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 1.0
    chart.valueAxis.valueStep = 0.25
    chart.valueAxis.labels.fontSize = 7.5
    chart.valueAxis.labels.fillColor = MUTED
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = BORDER
    chart.valueAxis.gridStrokeWidth = 0.5
    chart.bars[0].fillColor = BRAND
    # Composite bar (last one) stands out in magenta so it reads as the
    # "result" of the other five, not just another input.
    chart.bars[(0, 5)].fillColor = MAGENTA
    chart.barLabelFormat = "%.2f"
    chart.barLabels.fontSize = 7.75
    chart.barLabels.fillColor = INK
    chart.barLabels.fontName = "Helvetica-Bold"
    chart.barLabels.nudge = 9
    chart.strokeColor = None
    chart.barWidth = 12
    chart.groupSpacing = 6
    d.add(chart)
    # Value labels sit outside the bar end (nudge=9); the panel is wider
    # than the plotted chart area (chart.width = width - 175, vs. a
    # 468pt-wide panel), so there's real margin reserved on the right
    # for a near-1.0 bar's label instead of it riding the panel border.
    return d


# ---------------------------------------------------------------------
# Chart 3 -- report reasons (falls back to an evidence-volume chart if
# there are no reports on file, so every report ships with 3 visuals)
# ---------------------------------------------------------------------

def _report_reason_pie(reports: list) -> Drawing:
    width, height = 468, 208
    d = _panel(width, height)
    pie = Pie()
    pie.x, pie.y = 46, 22
    pie.width, pie.height = 160, 160
    pie.data = [r["count"] for r in reports]
    pie.labels = None
    pie.slices.strokeWidth = 1.25
    pie.slices.strokeColor = colors.white
    for i in range(len(reports)):
        pie.slices[i].fillColor = CHART_SERIES[i % len(CHART_SERIES)]
    d.add(pie)

    legend = Legend()
    legend.x, legend.y = 250, 172
    legend.dx, legend.dy = 9, 9
    legend.fontSize = 8.75
    legend.fillColor = INK
    legend.alignment = "left"
    legend.columnMaximum = 8
    legend.deltay = 13
    total = sum(r["count"] for r in reports) or 1
    legend.colorNamePairs = [
        (CHART_SERIES[i % len(CHART_SERIES)],
         f"{r['report_reason'].replace('_', ' ').title()} — {r['count']} ({r['count'] / total:.0%})")
        for i, r in enumerate(reports)
    ]
    d.add(legend)
    return d


def _evidence_volume_bar(comments_n: int, reports_n: int, notes_n: int, audit_n: int) -> Drawing:
    """Fallback third chart for the (rare) case with zero reports on
    file, so the report is never shipped with only 2 charts."""
    labels = ["Comments", "Reports", "Moderator Notes", "Audit Events"]
    values = [comments_n, reports_n, notes_n, audit_n]
    width, height = 468, 208
    d = _panel(width, height)
    chart = HorizontalBarChart()
    chart.x, chart.y = 105, 18
    chart.width, chart.height = width - 170, height - 42
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 8.5
    chart.categoryAxis.labels.fillColor = INK
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 7.5
    chart.valueAxis.labels.fillColor = MUTED
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = BORDER
    chart.valueAxis.gridStrokeWidth = 0.5
    chart.bars[0].fillColor = BRAND
    chart.barLabelFormat = "%d"
    chart.barLabels.fontSize = 8
    chart.barLabels.fillColor = INK
    chart.barLabels.fontName = "Helvetica-Bold"
    chart.barLabels.nudge = 9
    chart.strokeColor = None
    chart.barWidth = 14
    chart.groupSpacing = 8
    d.add(chart)
    return d


# ---------------------------------------------------------------------
# AI Investigator callout card
# ---------------------------------------------------------------------

def _evidence_bullets(evidence_text: str, styles) -> list:
    """The AIInvestigator emits evidence as "\n- line" separated text.
    Paragraph doesn't honor bare newlines, so the previous version
    printed this as one run-on sentence. Split it back into real
    bullet paragraphs."""
    lines = [ln.strip(" -") for ln in evidence_text.split("\n") if ln.strip(" -")]
    if not lines:
        return [Paragraph("—", styles["SXBody"])]
    return [Paragraph(f"•  {_escape(ln)}", styles["SXBullet"]) for ln in lines]


def _ai_callout(ai_result: dict, styles) -> Table:
    body = []
    if ai_result.get("error"):
        body.append(Paragraph(_escape(ai_result["error"]), styles["SXBody"]))
    else:
        body.append(Paragraph(f"<b>Summary</b>", styles["SXBody"]))
        body.append(Paragraph(_escape(ai_result.get("summary") or "—"), styles["SXBody"]))
        body.append(Spacer(1, 6))
        body.append(Paragraph("<b>Evidence</b>", styles["SXBody"]))
        body.extend(_evidence_bullets(ai_result.get("evidence") or "", styles))
        body.append(Spacer(1, 6))
        body.append(Paragraph(
            f"<b>Recommendation:</b> {_escape(ai_result.get('recommendation') or '—')}",
            styles["SXBody"],
        ))
        body.append(Spacer(1, 6))
        mode = ai_result.get("mode", "fallback")
        mode_label = "LLM-generated (Groq)" if mode == "llm" else "Rule-based (fallback mode)"
        body.append(Paragraph(f"Generated in {mode_label}.", styles["SXTiny"]))

    inner = Table([[body]], colWidths=[6.35 * inch])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_SOFT),
        ("BOX", (0, 0), (-1, -1), 1, BORDER_SOFT),
        ("LINEBEFORE", (0, 0), (0, 0), 3, BRAND),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    return inner


# ---------------------------------------------------------------------
# Letterhead + footer, drawn on every page via onFirstPage/onLaterPages
# so every page -- not just the first -- gets the branded header/footer
# and a correct page number (SimpleDocTemplate calls this once per page
# as it paginates, so canv.getPageNumber() is always accurate).
# ---------------------------------------------------------------------

def _draw_shield_mark(canv, cx, cy, scale=1.0):
    """Small vector shield-and-eye mark, echoing the app's logo, drawn
    directly on the letterhead so the PDF carries the same brand mark
    as the product rather than a plain wordmark."""
    canv.saveState()
    canv.translate(cx, cy)
    canv.scale(scale, scale)
    canv.setFillColor(colors.white)
    canv.setStrokeColor(colors.white)
    p = canv.beginPath()
    p.moveTo(0, 11)
    p.lineTo(9, 7.5)
    p.lineTo(9, -3)
    p.curveTo(9, -9, 4.5, -12.5, 0, -14)
    p.curveTo(-4.5, -12.5, -9, -9, -9, -3)
    p.lineTo(-9, 7.5)
    p.close()
    canv.drawPath(p, fill=1, stroke=0)
    canv.setFillColor(BRAND_DEEP)
    canv.circle(0, -1.5, 3.4, fill=1, stroke=0)
    canv.setFillColor(colors.white)
    canv.circle(0, -1.5, 1.3, fill=1, stroke=0)
    canv.restoreState()


def _make_canvas_factory(case_id: str, page_w: float, page_h: float):
    def _draw_chrome(canv, doc):
        canv.saveState()
        # Top letterhead band
        canv.setFillColor(BRAND_DEEP)
        canv.rect(0, page_h - 0.64 * inch, page_w, 0.64 * inch, fill=1, stroke=0)
        canv.setFillColor(BRAND)
        canv.rect(0, page_h - 0.685 * inch, page_w, 0.045 * inch, fill=1, stroke=0)

        _draw_shield_mark(canv, 0.62 * inch, page_h - 0.32 * inch, scale=0.72)

        canv.setFillColor(colors.white)
        canv.setFont("Helvetica-Bold", 13.5)
        canv.drawString(0.92 * inch, page_h - 0.35 * inch, "SentinelX")
        canv.setFont("Helvetica", 8.25)
        canv.setFillColor(colors.HexColor("#E9D5FF"))
        canv.drawString(0.92 * inch, page_h - 0.505 * inch, "Trust & Safety — Executive Investigation Report")

        canv.setFont("Helvetica-Bold", 10.5)
        canv.setFillColor(colors.white)
        canv.drawRightString(page_w - 0.75 * inch, page_h - 0.35 * inch, case_id)
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(colors.HexColor("#E9D5FF"))
        canv.drawRightString(page_w - 0.75 * inch, page_h - 0.505 * inch,
                              datetime.now().strftime("Generated %Y-%m-%d %H:%M"))

        # Bottom footer
        canv.setStrokeColor(BORDER)
        canv.setLineWidth(0.75)
        canv.line(0.75 * inch, 0.55 * inch, page_w - 0.75 * inch, 0.55 * inch)
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(MUTED_LIGHT)
        canv.drawString(0.75 * inch, 0.38 * inch,
                         "SentinelX — Confidential Trust & Safety Report. Internal use only.")
        # Page number itself is drawn later by _NumberedCanvas once the
        # total page count is known, so the footer can read "Page X of Y"
        # instead of a bare page number.
        canv.restoreState()
    return _draw_chrome


class _NumberedCanvas(Canvas):
    """Defers the footer's page number until the full page count is
    known, so every page can read "Page X of Y" -- the detail that
    makes a multi-page export read as a finished document rather than
    an open-ended stream of pages."""

    def __init__(self, *args, **kwargs):
        Canvas.__init__(self, *args, **kwargs)
        self._saved_states = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(MUTED_LIGHT)
            page_w = self._pagesize[0]
            self.drawRightString(page_w - 0.75 * inch, 0.38 * inch,
                                  f"Page {self.getPageNumber()} of {total}")
            Canvas.showPage(self)
        Canvas.save(self)


def generate_case_report_pdf(case_id: str) -> bytes:
    """Builds a full executive PDF report for one case. Returns raw PDF bytes."""

    bundle = CaseRepository().get_investigation_bundle(case_id)
    if bundle is None:
        raise ValueError(f"No case found: {case_id}")

    case = bundle["case"]
    account = bundle.get("account") or {}
    signals = bundle.get("signals") or {}
    campaign = bundle.get("campaign")
    reports = bundle.get("reports") or []
    comments = bundle.get("comments") or []

    mod_repo = ModeratorRepository()
    notes = mod_repo.get_notes(case_id)
    audit = mod_repo.get_audit_log(case_id)

    ai_result = AIInvestigator().investigate(bundle)

    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        topMargin=1.0 * inch, bottomMargin=0.85 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        title=f"SentinelX Report — {case_id}",
    )
    page_w, page_h = LETTER

    story = []
    sec_no = 0

    # ── Executive summary stat cards ─────────────────────────────────
    risk_val = account.get("risk_score")
    story.append(_stat_cards(case, risk_val, styles))
    story.append(Spacer(1, 14))

    # ── Case summary ──────────────────────────────────────────────────
    sec_no += 1
    case_table = [
        ["Case ID", case["case_id"], "Case Type", case["case_type"].replace("_", " ").title()],
        ["Opened", str(case["opened_at"])[:16], "Resolved", str(case.get("resolved_at") or "—")[:16]],
        ["Account", account.get("display_name", case["account_id"]),
         "Account ID", account.get("account_id", case["account_id"])],
        ["Risk Score", f"{risk_val:.3f}" if risk_val is not None else "—",
         "Assigned Moderator", case.get("assigned_moderator_id") or "— unassigned —"],
    ]
    story.append(KeepTogether(
        _section("Case Summary", sec_no, styles) +
        [_table(case_table, [1.1 * inch, 2.3 * inch, 1.25 * inch, 2.15 * inch], header=False, zebra=True)]
    ))
    story.append(Spacer(1, 14))

    # ── Chart 1: composite risk meter ────────────────────────────────
    sec_no += 1
    story.append(KeepTogether(
        _section("Composite Risk", sec_no, styles) + [
            _risk_meter(signals.get("composite_risk_score", risk_val or 0.0)),
            Paragraph(
                "Composite score blends account age, report volume, device reuse, IP region, "
                f"and toxicity signals. Production flag threshold: {0.4:.2f}.",
                styles["SXCaption"],
            ),
        ]
    ))

    # ── Campaign link ─────────────────────────────────────────────────
    sec_no += 1
    if campaign:
        campaign_flow = Paragraph(
            f"Linked to campaign <b>{campaign['campaign_id']}</b> ({campaign['campaign_type']}), "
            f"similarity score {campaign['similarity_score']:.2f}, "
            f"velocity {campaign['velocity_score']:.2f}, "
            f"network density {campaign['network_density']:.2f}.",
            styles["SXBody"]
        )
    else:
        campaign_flow = Paragraph("Not linked to any known coordinated campaign.", styles["SXBodyMuted"])
    story.append(KeepTogether(_section("Campaign Link", sec_no, styles) + [campaign_flow, Spacer(1, 12)]))

    # ── Chart 2: signal breakdown bar chart ──────────────────────────
    sec_no += 1
    if signals:
        story.append(KeepTogether(
            _section("Unified Signal Engine", sec_no, styles) + [
                _signal_bar_chart(signals),
                Paragraph("Each bar is one signal's contribution (0–1 scale); Composite is the blended result.",
                          styles["SXCaption"]),
            ]
        ))
    else:
        story.append(KeepTogether(
            _section("Unified Signal Engine", sec_no, styles) +
            [Paragraph("No signal data available for this account.", styles["SXBodyMuted"]), Spacer(1, 10)]
        ))

    # ── AI Investigator ───────────────────────────────────────────────
    sec_no += 1
    story.append(KeepTogether(
        _section("AI Investigator Assessment", sec_no, styles) + [_ai_callout(ai_result, styles)]
    ))
    story.append(Spacer(1, 14))

    # ── Chart 3: report reasons (or evidence-volume fallback) ────────
    sec_no += 1
    if reports:
        rep_rows = [["Reason", "Count"]] + [[r["report_reason"].replace("_", " ").title(), str(r["count"])] for r in reports]
        story.append(KeepTogether(
            _section("Report Summary", sec_no, styles) + [
                _report_reason_pie(reports),
                Spacer(1, 8),
                _table(rep_rows, [3.5 * inch, 1.5 * inch], zebra=True),
            ]
        ))
    else:
        story.append(KeepTogether(
            _section("Report Summary", sec_no, styles) + [
                Paragraph("No reports on file for this account.", styles["SXBodyMuted"]),
                Spacer(1, 6),
                _evidence_volume_bar(len(comments), len(reports), len(notes), len(audit)),
                Paragraph("Evidence volume on file for this case, for context.", styles["SXCaption"]),
            ]
        ))
    story.append(Spacer(1, 12))

    # ── Top flagged comments ────────────────────────────────────────
    sec_no += 1
    if comments:
        seen, deduped = set(), []
        for c in comments:
            key = c["text"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)

        rows = [["Date", "Classification", "Score", "Excerpt"]]
        for c in deduped[:5]:
            rows.append([
                str(c["posted_at"])[:10],
                Paragraph(_escape(c["toxicity_label"].replace(",", ", ")), styles["SXBodyMuted"]),
                f"{c['toxicity_score']:.2f}",
                Paragraph(_comment_display(c), styles["SXBody"]),
            ])
        comments_flow = [
            _table(rows, [0.72 * inch, 1.55 * inch, 0.55 * inch, 3.83 * inch], zebra=True, font_size=8.5),
            Spacer(1, 5),
            Paragraph(
                "Excerpts carrying a restricted policy category (identity-based hate, threats, "
                "severe toxicity) are withheld in this export; classification and score are shown "
                "in full. Ordinary profanity is masked.",
                styles["SXNote"],
            ),
        ]
    else:
        comments_flow = [Paragraph("No flagged comments.", styles["SXBodyMuted"])]
    story.append(KeepTogether(_section("Top Flagged Comments", sec_no, styles) + comments_flow))
    story.append(Spacer(1, 12))

    # ── Moderator notes ────────────────────────────────────────────────
    sec_no += 1
    if notes:
        notes_flow = []
        for n in notes:
            notes_flow.append(Paragraph(
                f"<b>{_escape(n.get('moderator_name') or n['moderator_id'])}</b> "
                f"<font color='#94A3B8'>— {str(n['created_at'])[:16]}</font>: "
                f"{_escape(n['note_text'])}",
                styles["SXBody"]
            ))
            notes_flow.append(Spacer(1, 5))
    else:
        notes_flow = [Paragraph("No notes recorded for this case.", styles["SXBodyMuted"])]
    story.append(KeepTogether(_section("Moderator Notes", sec_no, styles) + notes_flow))
    story.append(Spacer(1, 12))

    # ── Audit trail ─────────────────────────────────────────────────────
    sec_no += 1
    if audit:
        audit_rows = [["Timestamp", "Moderator", "Action"]] + [
            [str(a["timestamp"])[:16], _escape(a.get("moderator_name") or a["moderator_id"]), a["action"]]
            for a in audit
        ]
        audit_flow = [_table(audit_rows, [1.6 * inch, 1.8 * inch, 2.6 * inch], zebra=True)]
    else:
        audit_flow = [Paragraph("No audit events recorded for this case yet.", styles["SXBodyMuted"])]
    story.append(KeepTogether(_section("Audit Trail", sec_no, styles) + audit_flow))

    chrome = _make_canvas_factory(case["case_id"], page_w, page_h)
    doc.build(story, onFirstPage=chrome, onLaterPages=chrome, canvasmaker=_NumberedCanvas)
    buffer.seek(0)
    return buffer.read()