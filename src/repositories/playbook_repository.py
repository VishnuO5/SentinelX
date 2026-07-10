"""
src/repositories/playbook_repository.py
==========================================
Real queries backing the Investigation Playbooks page.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class PlaybookRepository:

    def list_case_types(self) -> list:
        conn = db.connect()
        rows = conn.execute("SELECT DISTINCT case_type FROM playbooks ORDER BY case_type").fetchall()
        return [r["case_type"] for r in rows]

    def get_playbook(self, case_type: str) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT playbook_id, step_order, step_description, checklist_item
            FROM playbooks WHERE case_type = ? ORDER BY step_order
            """,
            (case_type,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_open_cases_by_type(self, case_type: str, limit: int = 30) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT case_id, priority, status, account_id, opened_at
            FROM cases WHERE case_type = ? AND status != 'closed'
            ORDER BY opened_at DESC LIMIT ?
            """,
            (case_type, limit),
        ).fetchall()
        return [dict(r) for r in rows]