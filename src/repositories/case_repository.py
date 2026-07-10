"""
src/repositories/case_repository.py
=====================================
Gathers everything about a case that the AI Investigator needs to reason
over: the case itself, the account, its comments/reports/signals, and
the campaign it's linked to (if any).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class CaseRepository:

    def get_case(self, case_id: str) -> dict | None:
        conn = db.connect()
        row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        return dict(row) if row else None

    def list_recent_cases(self, limit: int = 50) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT case_id, case_type, priority, status, opened_at, account_id
            FROM cases ORDER BY opened_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_investigation_bundle(self, case_id: str) -> dict | None:
        """Everything the AI Investigator needs, gathered in one place."""
        conn = db.connect()

        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if case is None:
            return None
        case = dict(case)

        account = conn.execute(
            "SELECT * FROM accounts WHERE account_id = ?", (case["account_id"],)
        ).fetchone()
        account = dict(account) if account else {}

        signals = conn.execute(
            "SELECT * FROM signal_scores WHERE account_id = ?", (case["account_id"],)
        ).fetchone()
        signals = dict(signals) if signals else {}

        comments = conn.execute(
            """
            SELECT comment_id, text, toxicity_label, toxicity_score, posted_at
            FROM comments WHERE account_id = ?
            ORDER BY toxicity_score DESC LIMIT 8
            """,
            (case["account_id"],),
        ).fetchall()
        comments = [dict(r) for r in comments]

        reports = conn.execute(
            """
            SELECT report_reason, COUNT(*) AS count
            FROM reports WHERE account_id = ?
            GROUP BY report_reason ORDER BY count DESC
            """,
            (case["account_id"],),
        ).fetchall()
        reports = [dict(r) for r in reports]

        campaign = None
        if case.get("campaign_id"):
            row = conn.execute(
                "SELECT * FROM campaigns WHERE campaign_id = ?", (case["campaign_id"],)
            ).fetchone()
            campaign = dict(row) if row else None

        return {
            "case": case,
            "account": account,
            "signals": signals,
            "comments": comments,
            "reports": reports,
            "campaign": campaign,
        }