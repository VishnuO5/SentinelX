"""
src/repositories/counterfactual_repository.py
=================================================
Real queries backing the Counterfactual Simulator.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import db


class CounterfactualRepository:

    def list_runs(self) -> list:
        conn = db.connect()
        rows = conn.execute("SELECT * FROM counterfactual_runs ORDER BY run_id").fetchall()
        return [dict(r) for r in rows]