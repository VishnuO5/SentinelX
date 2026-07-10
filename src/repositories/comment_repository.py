"""
src/repositories/comment_repository.py
=========================================
Consolidated comment queries -- same rationale as account_repository.py.
Comment lookups by account and toxicity-based ordering were duplicated
across case_repository.py, evidence_repository.py, and the signal/
campaign engines' feature-building code.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class CommentRepository:

    def get_by_id(self, comment_id: str) -> dict | None:
        conn = db.connect()
        row = conn.execute(
            "SELECT * FROM comments WHERE comment_id = ?", (comment_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_by_account(self, account_id: str, limit: int = 50) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT comment_id, text, toxicity_label, toxicity_score, posted_at, platform_surface
            FROM comments WHERE account_id = ?
            ORDER BY posted_at DESC LIMIT ?
            """,
            (account_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_top_toxic_by_account(self, account_id: str, limit: int = 8) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT comment_id, text, toxicity_label, toxicity_score, posted_at
            FROM comments WHERE account_id = ?
            ORDER BY toxicity_score DESC LIMIT ?
            """,
            (account_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_average_toxicity(self, account_id: str) -> float:
        conn = db.connect()
        row = conn.execute(
            "SELECT AVG(toxicity_score) AS avg_tox FROM comments WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        return round(row["avg_tox"], 4) if row and row["avg_tox"] is not None else 0.0

    def get_by_campaign_accounts(self, campaign_id: str) -> list:
        """All comments from accounts in a given campaign -- used by
        compute_campaign_similarity.py's real TF-IDF cosine similarity
        step and by Abuse Genome's campaign deep-dive."""
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT c.comment_id, c.account_id, c.text, c.toxicity_label, c.toxicity_score
            FROM comments c
            JOIN accounts a ON c.account_id = a.account_id
            WHERE a.campaign_id = ?
            """,
            (campaign_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_by_label(self) -> dict:
        conn = db.connect()
        rows = conn.execute(
            "SELECT toxicity_label, COUNT(*) AS n FROM comments GROUP BY toxicity_label"
        ).fetchall()
        return {r["toxicity_label"]: r["n"] for r in rows}