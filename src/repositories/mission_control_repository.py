"""
src/repositories/mission_control_repository.py
================================================
Real queries backing the Mission Control page.
No hardcoded numbers — everything comes from the database.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.database.connection import db


class MissionControlRepository:

    def get_kpis(self) -> dict:
        conn = db.connect()

        open_cases = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE status IN ('open','in_progress','escalated')"
        ).fetchone()[0]

        # FIX: was hardcoded ">= 0.7", which never matched anything once
        # the Unified Signal Engine started computing real scores (real
        # range is ~0.04-0.66). Now reads a documented, named threshold
        # from config.py instead of a magic number.
        high_risk_accounts = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE risk_score >= ?",
            (config.HIGH_RISK_THRESHOLD,)
        ).fetchone()[0]

        active_campaigns = conn.execute(
            "SELECT COUNT(*) FROM campaigns WHERE status = 'active'"
        ).fetchone()[0]

        # FIX: column is composite_risk_score per the approved schema
        # (init_db.py). It was "final_risk" only because data_loader.py
        # used to silently rebuild the table around whatever the CSV
        # contained -- that's fixed now, so this must match the real
        # schema, not the old CSV's column name.
        avg_risk = conn.execute(
            "SELECT AVG(composite_risk_score) FROM signal_scores"
        ).fetchone()[0]

        return {
            "open_cases": open_cases,
            "high_risk_accounts": high_risk_accounts,
            "active_campaigns": active_campaigns,
            "avg_risk": round(avg_risk, 2) if avg_risk is not None else 0.0,
        }

    def get_recent_cases(self, limit: int = 10) -> list:
        conn = db.connect()

        rows = conn.execute(
            """
            SELECT case_id, case_type, priority, status, opened_at,
                   assigned_moderator_id
            FROM cases
            ORDER BY opened_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(r) for r in rows]

    def get_moderator_workload(self) -> list:
        conn = db.connect()

        rows = conn.execute(
            """
            SELECT moderator_id, name, role, active_case_count
            FROM moderators
            ORDER BY active_case_count DESC
            """
        ).fetchall()

        return [dict(r) for r in rows]

    def get_case_volume_trend(self) -> list:
        """Cases opened per week, real dates from the cases table --
        powers the Mission Control trend chart."""
        conn = db.connect()

        rows = conn.execute(
            """
            SELECT strftime('%Y-%W', opened_at) AS week, COUNT(*) AS count
            FROM cases
            GROUP BY week
            ORDER BY week ASC
            """
        ).fetchall()

        return [dict(r) for r in rows]

    def get_priority_breakdown(self) -> list:
        """Real case count per priority band."""
        conn = db.connect()

        rows = conn.execute(
            """
            SELECT priority, COUNT(*) AS count
            FROM cases
            GROUP BY priority
            """
        ).fetchall()

        return [dict(r) for r in rows]

    def get_recent_activity(self, limit: int = 6) -> list:
        """Recent real events from case_timeline, joined with case context
        -- powers the Mission Control activity feed."""
        conn = db.connect()

        rows = conn.execute(
            """
            SELECT case_timeline.event_type, case_timeline.event_timestamp,
                   case_timeline.event_description, cases.case_id, cases.case_type
            FROM case_timeline
            JOIN cases ON case_timeline.case_id = cases.case_id
            ORDER BY case_timeline.event_timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(r) for r in rows]