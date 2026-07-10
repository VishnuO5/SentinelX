"""
src/repositories/investigation_repository.py
============================================
Loads a complete investigation bundle for the Investigation Workspace,
and provides the write operations the Workspace page needs (adding a
case note).

Table names and column names match the approved schema (init_db.py).
"""

from __future__ import annotations

import uuid

from src.database.connection import db


class InvestigationRepository:

    def load_case(self, account_id: str) -> dict:
        conn = db.connect()

        account = conn.execute(
            "SELECT * FROM accounts WHERE account_id = ?",
            (account_id,)
        ).fetchone()

        comments = conn.execute(
            "SELECT * FROM comments WHERE account_id = ? ORDER BY posted_at DESC",
            (account_id,)
        ).fetchall()

        reports = conn.execute(
            "SELECT * FROM reports WHERE account_id = ? ORDER BY reported_at DESC",
            (account_id,)
        ).fetchall()

        # Table is signal_scores; composite column is composite_risk_score
        # (see scripts/init_db.py -- the approved schema).
        signals = conn.execute(
            "SELECT * FROM signal_scores WHERE account_id = ?",
            (account_id,)
        ).fetchone()

        # cases table holds open investigations for this account
        cases = conn.execute(
            "SELECT * FROM cases WHERE account_id = ? ORDER BY opened_at DESC",
            (account_id,)
        ).fetchall()

        # case_evidence and case_notes are keyed by case_id, not account_id
        evidence = []
        notes = []
        if cases:
            case_ids = [c["case_id"] for c in cases]
            placeholders = ",".join("?" * len(case_ids))

            evidence = conn.execute(
                f"SELECT * FROM case_evidence WHERE case_id IN ({placeholders})",
                case_ids
            ).fetchall()

            notes = conn.execute(
                f"""
                SELECT case_notes.*, moderators.name AS moderator_name
                FROM case_notes
                LEFT JOIN moderators ON case_notes.moderator_id = moderators.moderator_id
                WHERE case_notes.case_id IN ({placeholders})
                ORDER BY case_notes.created_at DESC
                """,
                case_ids
            ).fetchall()

        return {
            "account" : account,
            "comments": list(comments),
            "reports" : list(reports),
            "signals" : signals,
            "cases"   : list(cases),
            "evidence": list(evidence),
            "notes"   : list(notes),
        }

    def search_accounts(self, query: str, limit: int = 25) -> list:
        """Search accounts by account_id or display_name (case-insensitive,
        partial match). Empty query returns the highest-risk accounts first,
        so the page has something useful to show before anyone types."""
        conn = db.connect()

        query = (query or "").strip()

        if not query:
            rows = conn.execute(
                """
                SELECT account_id, display_name, status, risk_score, campaign_id
                FROM accounts
                ORDER BY risk_score DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return list(rows)

        like = f"%{query}%"
        rows = conn.execute(
            """
            SELECT account_id, display_name, status, risk_score, campaign_id
            FROM accounts
            WHERE account_id LIKE ? OR display_name LIKE ?
            ORDER BY risk_score DESC
            LIMIT ?
            """,
            (like, like, limit)
        ).fetchall()
        return list(rows)

    def list_moderators(self) -> list:
        conn = db.connect()
        rows = conn.execute(
            "SELECT moderator_id, name, role FROM moderators ORDER BY name"
        ).fetchall()
        return list(rows)

    def add_case_note(self, case_id: str, moderator_id: str, note_text: str) -> str:
        """Inserts a new case_notes row. Returns the generated note_id."""
        conn = db.connect()

        note_id = f"NOTE-{uuid.uuid4().hex[:8].upper()}"

        conn.execute(
            """
            INSERT INTO case_notes (note_id, case_id, moderator_id, note_text, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (note_id, case_id, moderator_id, note_text)
        )
        conn.commit()

        return note_id