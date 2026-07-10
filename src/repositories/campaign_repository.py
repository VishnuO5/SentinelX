"""
src/repositories/campaign_repository.py
=========================================
Real queries backing the Abuse Genome page: campaign DNA (velocity,
similarity, network density, report volume) plus the member accounts
of each campaign.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class CampaignRepository:

    def list_campaigns(self) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT c.*,
                   COUNT(a.account_id) AS account_count
            FROM campaigns c
            LEFT JOIN accounts a ON a.campaign_id = c.campaign_id
            GROUP BY c.campaign_id
            ORDER BY c.velocity_score DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def get_campaign(self, campaign_id: str) -> dict | None:
        conn = db.connect()
        row = conn.execute(
            "SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_campaign_dna(self, campaign_id: str) -> dict | None:
        """The four DNA dimensions the brief calls out: velocity,
        similarity, network density, and report volume -- the last one
        computed live (not stored), since it's a real count over the
        campaign's actual accounts' reports."""
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            return None

        conn = db.connect()
        report_count = conn.execute(
            """
            SELECT COUNT(*) FROM reports r
            JOIN accounts a ON r.account_id = a.account_id
            WHERE a.campaign_id = ?
            """,
            (campaign_id,),
        ).fetchone()[0]

        account_count = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()[0]

        # Normalize report volume against the busiest campaign so it sits
        # on the same 0-1 scale as the other three DNA dimensions.
        max_reports = conn.execute(
            """
            SELECT MAX(cnt) FROM (
                SELECT COUNT(*) AS cnt FROM reports r
                JOIN accounts a ON r.account_id = a.account_id
                WHERE a.campaign_id IS NOT NULL
                GROUP BY a.campaign_id
            )
            """
        ).fetchone()[0] or 1

        return {
            "campaign_id": campaign_id,
            "campaign_type": campaign["campaign_type"],
            "velocity": campaign["velocity_score"],
            "similarity": campaign["similarity_score"],
            "network_density": campaign["network_density"],
            "report_volume_normalized": round(report_count / max_reports, 3),
            "report_count": report_count,
            "account_count": account_count,
            "status": campaign["status"],
        }

    def get_campaign_accounts(self, campaign_id: str) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT a.account_id, a.display_name, a.status, a.device_id,
                   a.ip_region, a.risk_score
            FROM accounts a
            WHERE a.campaign_id = ?
            ORDER BY a.risk_score DESC
            """,
            (campaign_id,),
        ).fetchall()
        return [dict(r) for r in rows]