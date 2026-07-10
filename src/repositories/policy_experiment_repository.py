"""
src/repositories/policy_experiment_repository.py
====================================================
Real queries backing the Policy Experiment Center, plus a live
precision/recall/F1 calculator so an analyst can test any threshold on
demand, not just the pre-generated scenarios.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class PolicyExperimentRepository:

    def list_experiments(self) -> list:
        conn = db.connect()
        rows = conn.execute(
            "SELECT * FROM policy_experiments ORDER BY tested_value"
        ).fetchall()
        return [dict(r) for r in rows]

    def compute_live_metrics(self, threshold: float) -> dict:
        """Real precision/recall/F1 at any threshold the user picks,
        computed on demand against the same ground-truth proxy
        (campaign_id IS NOT NULL) used in generate_policy_experiments.py."""
        conn = db.connect()

        tp = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE risk_score >= ? AND campaign_id IS NOT NULL",
            (threshold,),
        ).fetchone()[0]
        fp = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE risk_score >= ? AND campaign_id IS NULL",
            (threshold,),
        ).fetchone()[0]
        fn = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE risk_score < ? AND campaign_id IS NOT NULL",
            (threshold,),
        ).fetchone()[0]
        tn = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE risk_score < ? AND campaign_id IS NULL",
            (threshold,),
        ).fetchone()[0]

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        }

    def sweep_thresholds(self, step: float = 0.05) -> list:
        """Full precision/recall curve across the threshold range, for
        the chart."""
        results = []
        t = 0.0
        while t <= 1.0:
            results.append(self.compute_live_metrics(round(t, 2)))
            t += step
        return results