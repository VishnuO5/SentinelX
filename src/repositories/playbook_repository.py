"""
src/repositories/playbook_repository.py
=========================================
Real queries backing the Investigation Playbooks page: the checklist
itself for a given case type, plus historical outcome stats (resolution
rate, avg time to resolve, status/priority mix) computed live from the
`cases` table so the numbers next to each playbook are real, not
illustrative.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db

# Cases in any of these statuses are still "open" for the purposes of
# this page -- resolved/closed cases are historical, not active work.
OPEN_STATUSES = ("open", "in_progress", "escalated")


class PlaybookRepository:

    def list_case_types(self) -> list:
        """Distinct case types that have a playbook defined, in a stable
        order (alphabetical) so the selectbox doesn't reshuffle on
        every rerun."""
        conn = db.connect()
        rows = conn.execute(
            "SELECT DISTINCT case_type FROM playbooks ORDER BY case_type"
        ).fetchall()
        return [r["case_type"] for r in rows]

    def get_playbook(self, case_type: str) -> list:
        """Ordered checklist steps for a case type."""
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT playbook_id, case_type, step_order, step_description, checklist_item
            FROM playbooks
            WHERE case_type = ?
            ORDER BY step_order
            """,
            (case_type,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_open_cases_by_type(self, case_type: str) -> list:
        """Currently open/in-progress/escalated cases of this type."""
        conn = db.connect()
        placeholders = ",".join("?" for _ in OPEN_STATUSES)
        rows = conn.execute(
            f"""
            SELECT case_id, priority, status, opened_at, account_id, assigned_moderator_id
            FROM cases
            WHERE case_type = ? AND status IN ({placeholders})
            ORDER BY opened_at DESC
            """,
            (case_type, *OPEN_STATUSES),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_case_type_stats(self, case_type: str) -> dict:
        """Real historical numbers for every case of this type ever
        opened: total volume, resolution rate, avg time to resolve
        (resolved cases only), and the status/priority mix."""
        conn = db.connect()

        rows = conn.execute(
            "SELECT status, priority, opened_at, resolved_at FROM cases WHERE case_type = ?",
            (case_type,),
        ).fetchall()
        rows = [dict(r) for r in rows]

        total = len(rows)
        status_counts: dict = {}
        priority_counts: dict = {}
        resolved_hours = []

        for row in rows:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
            priority_counts[row["priority"]] = priority_counts.get(row["priority"], 0) + 1

            if row["status"] in ("resolved", "closed") and row["opened_at"] and row["resolved_at"]:
                opened = _parse_ts(row["opened_at"])
                resolved = _parse_ts(row["resolved_at"])
                if opened and resolved:
                    resolved_hours.append((resolved - opened).total_seconds() / 3600)

        resolved_count = status_counts.get("resolved", 0) + status_counts.get("closed", 0)
        resolution_rate = resolved_count / total if total else 0.0
        avg_resolution_hours = sum(resolved_hours) / len(resolved_hours) if resolved_hours else None

        return {
            "total": total,
            "resolution_rate": resolution_rate,
            "avg_resolution_hours": avg_resolution_hours,
            "status_counts": status_counts,
            "priority_counts": priority_counts,
        }


def _parse_ts(value: str):
    """Parses the 'YYYY-MM-DD HH:MM:SS' timestamps used throughout the
    generated data. Returns None if the value is missing or malformed
    rather than raising, since resolved_at is blank for open cases."""
    from datetime import datetime

    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None