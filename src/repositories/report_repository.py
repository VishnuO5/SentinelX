"""
src/repositories/report_repository.py
========================================
Consolidated report queries -- same rationale as account_repository.py
and comment_repository.py. Report-reason breakdowns and per-account
report counts were duplicated across case_repository.py,
policy_experiment_repository.py, and generate_signal_scores.py's real
report_volume_signal computation.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class ReportRepository:

    def get_by_account(self, account_id: str) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT report_id, comment_id, report_reason, reported_at, reporter_type
            FROM reports WHERE account_id = ?
            ORDER BY reported_at DESC
            """,
            (account_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_by_account(self, account_id: str) -> int:
        conn = db.connect()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM reports WHERE account_id = ?", (account_id,)
        ).fetchone()
        return row["n"] if row else 0

    def reason_breakdown_by_account(self, account_id: str) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT report_reason, COUNT(*) AS count
            FROM reports WHERE account_id = ?
            GROUP BY report_reason ORDER BY count DESC
            """,
            (account_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_max_report_count_across_accounts(self) -> int:
        """Used to normalize report_volume_signal to [0,1] in the Signal
        Engine -- the busiest account's report count is the scale."""
        conn = db.connect()
        row = conn.execute(
            "SELECT MAX(cnt) AS max_cnt FROM "
            "(SELECT COUNT(*) AS cnt FROM reports GROUP BY account_id)"
        ).fetchone()
        return row["max_cnt"] if row and row["max_cnt"] is not None else 0

    def count_by_reporter_type(self) -> dict:
        conn = db.connect()
        rows = conn.execute(
            "SELECT reporter_type, COUNT(*) AS n FROM reports GROUP BY reporter_type"
        ).fetchall()
        return {r["reporter_type"]: r["n"] for r in rows}