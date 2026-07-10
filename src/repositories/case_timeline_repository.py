"""
src/repositories/case_timeline_repository.py
================================================
Real queries backing the Investigation Replay page.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class CaseTimelineRepository:

    def list_cases_with_timeline(self, limit: int = 100) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT DISTINCT c.case_id, c.case_type, c.priority, c.status, c.opened_at
            FROM case_timeline t
            JOIN cases c ON t.case_id = c.case_id
            ORDER BY c.opened_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_timeline(self, case_id: str) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT event_id, event_type, event_timestamp, event_description
            FROM case_timeline
            WHERE case_id = ?
            ORDER BY event_timestamp ASC
            """,
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_case_summary(self, case_id: str) -> dict | None:
        conn = db.connect()
        row = conn.execute(
            """
            SELECT c.*, a.display_name, a.risk_score
            FROM cases c
            LEFT JOIN accounts a ON c.account_id = a.account_id
            WHERE c.case_id = ?
            """,
            (case_id,),
        ).fetchone()
        return dict(row) if row else None