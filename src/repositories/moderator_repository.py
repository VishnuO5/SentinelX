"""
src/repositories/moderator_repository.py
==========================================
Backs the Moderator Workspace: case queue, assignment, and the
resolve/escalate/close actions. This is the module that finally writes
real rows into audit_log and case_notes -- both correctly empty until
now, since they only make sense once real moderator actions happen.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db

VALID_STATUSES = ["open", "in_progress", "escalated", "resolved", "closed"]


class ModeratorRepository:

    def list_moderators(self) -> list:
        conn = db.connect()
        rows = conn.execute(
            "SELECT moderator_id, name, role, active_case_count "
            "FROM moderators ORDER BY active_case_count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_queue(self, moderator_id: str | None = None, status: str | None = None,
                   limit: int = 100) -> list:
        conn = db.connect()
        query = """
            SELECT cases.case_id, cases.case_type, cases.priority, cases.status,
                   cases.opened_at, cases.resolved_at, cases.account_id,
                   cases.assigned_moderator_id, moderators.name AS moderator_name
            FROM cases
            LEFT JOIN moderators ON cases.assigned_moderator_id = moderators.moderator_id
            WHERE 1=1
        """
        params: list = []
        if moderator_id:
            query += " AND cases.assigned_moderator_id = ?"
            params.append(moderator_id)
        if status:
            query += " AND cases.status = ?"
            params.append(status)
        query += """
            ORDER BY CASE cases.priority
                WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                WHEN 'medium' THEN 2 ELSE 3 END,
                cases.opened_at DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_case_summary(self, case_id: str) -> dict | None:
        conn = db.connect()
        row = conn.execute(
            """
            SELECT cases.*, accounts.display_name, accounts.risk_score,
                   accounts.status AS account_status, moderators.name AS moderator_name
            FROM cases
            LEFT JOIN accounts ON cases.account_id = accounts.account_id
            LEFT JOIN moderators ON cases.assigned_moderator_id = moderators.moderator_id
            WHERE cases.case_id = ?
            """,
            (case_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_notes(self, case_id: str) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT case_notes.*, moderators.name AS moderator_name
            FROM case_notes
            LEFT JOIN moderators ON case_notes.moderator_id = moderators.moderator_id
            WHERE case_notes.case_id = ?
            ORDER BY case_notes.created_at DESC
            """,
            (case_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_audit_log(self, case_id: str) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT audit_log.*, moderators.name AS moderator_name
            FROM audit_log
            LEFT JOIN moderators ON audit_log.moderator_id = moderators.moderator_id
            WHERE audit_log.case_id = ?
            ORDER BY audit_log.timestamp DESC
            """,
            (case_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # -- internal write helpers -------------------------------------------

    def _write_audit(self, conn, case_id: str, moderator_id: str, action: str) -> None:
        log_id = f"LOG-{uuid.uuid4().hex[:8].upper()}"
        conn.execute(
            "INSERT INTO audit_log (log_id, case_id, moderator_id, action, timestamp) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (log_id, case_id, moderator_id, action)
        )

    def _write_timeline(self, conn, case_id: str, event_type: str, description: str) -> None:
        event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"
        conn.execute(
            "INSERT INTO case_timeline (event_id, case_id, event_type, event_timestamp, "
            "event_description) VALUES (?, ?, ?, datetime('now'), ?)",
            (event_id, case_id, event_type, description)
        )

    def _sync_moderator_counts(self, conn, moderator_id: str | None) -> None:
        if not moderator_id:
            return
        count = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE assigned_moderator_id = ? "
            "AND status IN ('open','in_progress','escalated')",
            (moderator_id,)
        ).fetchone()[0]
        conn.execute(
            "UPDATE moderators SET active_case_count = ? WHERE moderator_id = ?",
            (count, moderator_id)
        )

    # -- actions ------------------------------------------------------------

    def assign_case(self, case_id: str, moderator_id: str) -> None:
        conn = db.connect()

        old = conn.execute(
            "SELECT assigned_moderator_id FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        old_moderator = old["assigned_moderator_id"] if old else None

        conn.execute(
            "UPDATE cases SET assigned_moderator_id = ? WHERE case_id = ?",
            (moderator_id, case_id)
        )

        mod_row = conn.execute(
            "SELECT name FROM moderators WHERE moderator_id = ?", (moderator_id,)
        ).fetchone()
        moderator_name = mod_row["name"] if mod_row else moderator_id

        self._write_audit(conn, case_id, moderator_id, f"assigned to {moderator_name}")
        self._write_timeline(conn, case_id, "assigned", f"Case assigned to {moderator_name}")

        if old_moderator and old_moderator != moderator_id:
            self._sync_moderator_counts(conn, old_moderator)
        self._sync_moderator_counts(conn, moderator_id)

        conn.commit()

    def update_status(self, case_id: str, new_status: str, moderator_id: str) -> None:
        if new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")

        conn = db.connect()

        if new_status in ("resolved", "closed"):
            conn.execute(
                "UPDATE cases SET status = ?, resolved_at = datetime('now') WHERE case_id = ?",
                (new_status, case_id)
            )
        else:
            conn.execute(
                "UPDATE cases SET status = ?, resolved_at = NULL WHERE case_id = ?",
                (new_status, case_id)
            )

        self._write_audit(conn, case_id, moderator_id, f"status changed to {new_status}")
        self._write_timeline(conn, case_id, new_status, f"Case marked {new_status}")
        self._sync_moderator_counts(conn, moderator_id)

        conn.commit()

    def add_note(self, case_id: str, moderator_id: str, note_text: str) -> str:
        conn = db.connect()
        note_id = f"NOTE-{uuid.uuid4().hex[:8].upper()}"
        conn.execute(
            "INSERT INTO case_notes (note_id, case_id, moderator_id, note_text, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (note_id, case_id, moderator_id, note_text)
        )
        self._write_audit(conn, case_id, moderator_id, "added a note")
        conn.commit()
        return note_id