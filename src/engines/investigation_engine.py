"""
src/engines/investigation_engine.py
======================================
Case priority already comes from a deterministic function
(priority_from_reports() in generate_cases.py) -- it was never actually
random. The real gap: that function looks at report_count alone.

This engine replaces it with a multi-factor priority score that also
weighs composite risk score (Unified Signal Engine) and campaign network
density -- genuinely more evidence-driven than a single-signal threshold.

Also adds two small, real, actionable pieces:
    - an SLA/overdue flag
    - a rule-based "recommended next action" for the analyst
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
PRIORITY_WEIGHTS = {
    "composite_risk_score": 0.50,
    "report_volume":        0.30,
    "network_density":      0.20,
}

PRIORITY_BANDS = [
    (0.75, "critical"),
    (0.50, "high"),
    (0.25, "medium"),
    (0.00, "low"),
]

SLA_HOURS = {
    "critical": 24,
    "high": 72,
    "medium": 168,
    "low": 336,
}


class InvestigationEngine:

    def compute_priority(
        self,
        composite_risk_score: float | None,
        report_count: int,
        max_report_count: int = 75,
        network_density: float | None = None,
    ) -> dict:
        risk = composite_risk_score if composite_risk_score is not None else 0.0
        report_signal = min(1.0, report_count / max(max_report_count, 1))
        density = network_density if network_density is not None else 0.0

        urgency = (
            PRIORITY_WEIGHTS["composite_risk_score"] * risk
            + PRIORITY_WEIGHTS["report_volume"] * report_signal
            + PRIORITY_WEIGHTS["network_density"] * density
        )
        urgency = round(min(1.0, max(0.0, urgency)), 4)

        label = "low"
        for threshold, band_label in PRIORITY_BANDS:
            if urgency >= threshold:
                label = band_label
                break

        return {"priority": label, "urgency_score": urgency}

    def check_sla(self, opened_at, status: str, priority: str, reference_time=None) -> dict:
        # FIX: this used to default to datetime.now() (real wall-clock time).
        # The whole dataset's timestamps are anchored to config.CURRENT_TIME,
        # not to whenever this code happens to run -- using real "now" only
        # looked correct by coincidence (today's real date happens to be
        # close to the dataset's anchor). It would silently give wrong
        # "hours overdue" numbers once real time drifts further, or if the
        # dataset gets regenerated with a different anchor.
        reference_time = reference_time or config.CURRENT_TIME

        if isinstance(opened_at, str):
            opened_at = datetime.fromisoformat(opened_at.replace("Z", ""))

        if status in ("resolved", "closed"):
            return {"overdue": False, "hours_open": None, "sla_hours": SLA_HOURS.get(priority)}

        hours_open = (reference_time - opened_at).total_seconds() / 3600
        sla_hours = SLA_HOURS.get(priority, SLA_HOURS["low"])

        return {
            "overdue": hours_open > sla_hours,
            "hours_open": round(hours_open, 1),
            "sla_hours": sla_hours,
        }

    def recommend_next_action(
        self,
        priority: str,
        status: str,
        evidence_count: int,
        overdue: bool,
    ) -> str:
        if status in ("resolved", "closed"):
            return "No action needed — case already closed."

        if overdue and priority in ("critical", "high"):
            return f"Overdue for a {priority}-priority case — escalate to a senior analyst now."

        if evidence_count == 0:
            return "No evidence collected yet — pull comments and reports before proceeding."

        if priority == "critical" and status == "open":
            return "Critical and unassigned/open — assign to a moderator immediately."

        if priority in ("critical", "high") and status == "in_progress":
            return "Actively worked, high urgency — verify evidence is sufficient to resolve or escalate."

        if priority in ("low", "medium") and status == "open":
            return "Standard queue item — assign during next triage pass."

        return "Continue standard investigation workflow."


if __name__ == "__main__":
    engine = InvestigationEngine()
    print(engine.compute_priority(composite_risk_score=0.62, report_count=45, network_density=0.7))
    print(engine.compute_priority(composite_risk_score=0.08, report_count=1, network_density=0.0))
    print(engine.check_sla("2026-05-01T00:00:00", status="open", priority="critical",
                            reference_time=datetime(2026, 6, 1)))
    print(engine.recommend_next_action(priority="critical", status="open", evidence_count=3, overdue=True))