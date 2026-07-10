"""
src/repositories/account_repository.py
=========================================
Consolidated account queries. Before this file existed, "get an account
by ID," "find accounts by campaign," and "find accounts sharing a
device" were each re-written slightly differently inside
investigation_repository.py, mission_control_repository.py,
signal_repository.py, campaign_repository.py, and evidence_repository.py.
This is the one place those queries now live -- a schema change to the
accounts table only needs updating here.

Existing call sites were NOT changed to use this file for this handoff
(they work, and touching five already-tested repositories is a separate,
deliberate task) -- but any NEW account query should be added here
first, not re-written inline again.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class AccountRepository:

    def get_by_id(self, account_id: str) -> dict | None:
        conn = db.connect()
        row = conn.execute(
            "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
        return dict(row) if row else None

    def search(self, query: str, limit: int = 25) -> list:
        """Matches on account_id or display_name -- the same lookup
        Investigation Workspace's account search needs."""
        conn = db.connect()
        like = f"%{query}%"
        rows = conn.execute(
            """
            SELECT account_id, display_name, status, risk_score, campaign_id
            FROM accounts
            WHERE account_id LIKE ? OR display_name LIKE ?
            ORDER BY risk_score DESC
            LIMIT ?
            """,
            (like, like, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_by_campaign(self, campaign_id: str) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT account_id, display_name, status, device_id, ip_region, risk_score
            FROM accounts WHERE campaign_id = ?
            ORDER BY risk_score DESC
            """,
            (campaign_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_device_peers(self, account_id: str) -> list:
        """Other accounts sharing this account's device_id -- the same
        lookup the Signal Engine and campaign detection both need."""
        conn = db.connect()
        row = conn.execute("SELECT device_id FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
        if row is None:
            return []
        rows = conn.execute(
            """
            SELECT account_id, display_name, status, campaign_id
            FROM accounts WHERE device_id = ? AND account_id != ?
            """,
            (row["device_id"], account_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_top_risk(self, limit: int = 20) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT account_id, display_name, status, risk_score, campaign_id
            FROM accounts ORDER BY risk_score DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_by_status(self) -> dict:
        conn = db.connect()
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM accounts GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}