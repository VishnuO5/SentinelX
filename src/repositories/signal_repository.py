"""
src/repositories/signal_repository.py
======================================
Real queries backing the Unified Signal Engine page.

The signal computation itself already happens in
scripts/generate_signal_scores.py (real data, no random numbers -- see
that file's docstring). This repository just reads what was computed.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.database.connection import db


class SignalRepository:

    def get_engine_stats(self) -> dict:
        """Platform-wide signal distribution -- used for the engine
        overview cards and the weight bar chart."""
        conn = db.connect()

        row = conn.execute(
            """
            SELECT
                AVG(account_age_signal)   AS avg_age,
                AVG(report_volume_signal) AS avg_reports,
                AVG(device_reuse_signal)  AS avg_device,
                AVG(ip_region_signal)     AS avg_ip,
                AVG(toxicity_signal)      AS avg_toxicity,
                AVG(composite_risk_score) AS avg_composite,
                MIN(composite_risk_score) AS min_composite,
                MAX(composite_risk_score) AS max_composite,
                COUNT(*)                  AS total_accounts
            FROM signal_scores
            """
        ).fetchone()

        return dict(row) if row else {}

    def get_score_distribution(self, bucket_size: float = 0.1) -> list:
        """Histogram-ready bucket counts for composite_risk_score."""
        conn = db.connect()
        rows = conn.execute("SELECT composite_risk_score FROM signal_scores").fetchall()
        buckets: dict[float, int] = {}
        for r in rows:
            score = r["composite_risk_score"] or 0.0
            bucket = round((score // bucket_size) * bucket_size, 2)
            buckets[bucket] = buckets.get(bucket, 0) + 1
        return sorted(({"bucket": k, "count": v} for k, v in buckets.items()), key=lambda x: x["bucket"])

    def get_top_risk_accounts(self, limit: int = 20) -> list:
        conn = db.connect()
        rows = conn.execute(
            """
            SELECT s.account_id, a.display_name, a.status, a.campaign_id,
                   s.account_age_signal, s.report_volume_signal,
                   s.device_reuse_signal, s.ip_region_signal,
                   s.toxicity_signal, s.composite_risk_score
            FROM signal_scores s
            JOIN accounts a ON s.account_id = a.account_id
            ORDER BY s.composite_risk_score DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_signal_for_account(self, account_id: str) -> dict | None:
        conn = db.connect()
        row = conn.execute(
            "SELECT * FROM signal_scores WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_weights(self) -> dict:
        """The weights the composite score is built from -- pulled from
        config.py so the page never hardcodes a number that could drift
        from what generate_signal_scores.py actually used."""
        return {
            "Account Age": config.SIGNAL_WEIGHTS["account_age"],
            "Report Volume": config.SIGNAL_WEIGHTS["report_volume"],
            "Device Reuse": config.SIGNAL_WEIGHTS["device_reuse"],
            "IP Region": config.SIGNAL_WEIGHTS["ip_region"],
            "Toxicity": config.SIGNAL_WEIGHTS["toxicity"],
        }