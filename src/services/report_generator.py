"""
src/services/report_generator.py
==================================
Executive Report Generator: renders a case's full evidence bundle, AI
Investigator writeup, moderator notes, and audit trail into a downloadable
PDF -- the artifact an analyst would actually hand to a manager.

Uses reportlab (pure Python, no external binaries/services) to stay
inside the project's free-tools-only stack.
"""

from __future__ import annotations

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
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

from src.repositories.case_repository import CaseRepository
from src.repositories.moderator_repository import ModeratorRepository
from src.ai.investigator import AIInvestigator


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
        name="SXTitle", fontSize=20, leading=24, spaceAfter=4,
        textColor=colors.HexColor("#1E293B")
    ))
    styles.add(ParagraphStyle(
        name="SXSubtitle", fontSize=10, textColor=colors.HexColor("#64748B"),
        spaceAfter=16
    ))
    styles.add(ParagraphStyle(
        name="SXHeading", fontSize=13, spaceBefore=14, spaceAfter=6,
        textColor=colors.HexColor("#4F46E5")
    ))
    styles.add(ParagraphStyle(name="SXBody", fontSize=10, leading=14))
    styles.add(ParagraphStyle(
        name="SXTiny", fontSize=8, textColor=colors.HexColor("#94A3B8")
    ))
    return styles


def _table(data, col_widths, header=True):
    t = Table(data, colWidths=col_widths)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")))
        style.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    return t


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
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )

    story = []

    story.append(Paragraph("SentinelX — Executive Investigation Report", styles["SXTitle"]))
    story.append(Paragraph(
        f"Case {case['case_id']} &nbsp;|&nbsp; Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        styles["SXSubtitle"]
    ))

    # --- Case summary ---
    story.append(Paragraph("Case Summary", styles["SXHeading"]))
    risk_val = account.get("risk_score")
    case_table = [
        ["Case ID", case["case_id"], "Status", case["status"]],
        ["Case Type", case["case_type"], "Priority", case["priority"]],
        ["Opened", str(case["opened_at"]), "Resolved", str(case.get("resolved_at") or "—")],
        ["Account", account.get("display_name", case["account_id"]),
         "Risk Score", f"{risk_val:.3f}" if risk_val is not None else "—"],
    ]
    story.append(_table(case_table, [1.1 * inch, 2.3 * inch, 1.1 * inch, 2.3 * inch], header=False))
    story.append(Spacer(1, 10))

    # --- Campaign link ---
    story.append(Paragraph("Campaign Link", styles["SXHeading"]))
    if campaign:
        story.append(Paragraph(
            f"Linked to campaign <b>{campaign['campaign_id']}</b> ({campaign['campaign_type']}), "
            f"similarity score {campaign['similarity_score']:.2f}, "
            f"velocity {campaign['velocity_score']:.2f}, "
            f"network density {campaign['network_density']:.2f}.",
            styles["SXBody"]
        ))
    else:
        story.append(Paragraph("Not linked to any known coordinated campaign.", styles["SXBody"]))
    story.append(Spacer(1, 8))

    # --- Signal breakdown ---
    story.append(Paragraph("Unified Signal Engine", styles["SXHeading"]))
    if signals:
        sig_rows = [["Signal", "Score"]]
        for label, key in [
            ("Account Age", "account_age_signal"),
            ("Report Volume", "report_volume_signal"),
            ("Device Reuse", "device_reuse_signal"),
            ("IP Region", "ip_region_signal"),
            ("Toxicity", "toxicity_signal"),
            ("Composite Risk", "composite_risk_score"),
        ]:
            val = signals.get(key)
            sig_rows.append([label, f"{val:.3f}" if val is not None else "—"])
        story.append(_table(sig_rows, [3.5 * inch, 1.5 * inch]))
    else:
        story.append(Paragraph("No signal data available for this account.", styles["SXBody"]))
    story.append(Spacer(1, 8))

    # --- AI Investigator ---
    story.append(Paragraph("AI Investigator Assessment", styles["SXHeading"]))
    if ai_result.get("error"):
        story.append(Paragraph(_escape(ai_result["error"]), styles["SXBody"]))
    else:
        for label, key in [("Summary", "summary"), ("Evidence", "evidence"),
                            ("Recommendation", "recommendation")]:
            text = ai_result.get(key) or "—"
            story.append(Paragraph(f"<b>{label}:</b> {_escape(text)}", styles["SXBody"]))
            story.append(Spacer(1, 4))
        mode = ai_result.get("mode", "fallback")
        story.append(Paragraph(f"Generated in {mode} mode.", styles["SXTiny"]))
    story.append(Spacer(1, 8))

    # --- Reports ---
    story.append(Paragraph("Report Summary", styles["SXHeading"]))
    if reports:
        rep_rows = [["Reason", "Count"]] + [[r["report_reason"], str(r["count"])] for r in reports]
        story.append(_table(rep_rows, [3.5 * inch, 1.5 * inch]))
    else:
        story.append(Paragraph("No reports on file for this account.", styles["SXBody"]))
    story.append(Spacer(1, 8))

    # --- Top comments ---
    story.append(Paragraph("Top Flagged Comments", styles["SXHeading"]))
    if comments:
        for c in comments[:5]:
            story.append(Paragraph(
                f"<b>{c['toxicity_label']}</b> ({c['toxicity_score']:.2f}, {c['posted_at']}): "
                f"{_escape(c['text'][:220])}",
                styles["SXBody"]
            ))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No flagged comments.", styles["SXBody"]))

    # --- Moderator notes + audit trail (page 2) ---
    story.append(PageBreak())
    story.append(Paragraph("Moderator Notes", styles["SXHeading"]))
    if notes:
        for n in notes:
            story.append(Paragraph(
                f"<b>{n.get('moderator_name') or n['moderator_id']}</b> — {n['created_at']}: "
                f"{_escape(n['note_text'])}",
                styles["SXBody"]
            ))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("No notes recorded for this case.", styles["SXBody"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Audit Trail", styles["SXHeading"]))
    if audit:
        audit_rows = [["Timestamp", "Moderator", "Action"]] + [
            [a["timestamp"], a.get("moderator_name") or a["moderator_id"], a["action"]]
            for a in audit
        ]
        story.append(_table(audit_rows, [1.8 * inch, 1.8 * inch, 2.4 * inch]))
    else:
        story.append(Paragraph("No audit events recorded for this case yet.", styles["SXBody"]))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()