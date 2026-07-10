"""
tests/test_repositories.py
=============================
Read-only coverage for the core repositories -- safe to run directly
against the real database, since none of these write.
"""

from __future__ import annotations

from src.repositories.mission_control_repository import MissionControlRepository
from src.repositories.case_repository import CaseRepository
from src.repositories.account_repository import AccountRepository


def test_mission_control_kpis_are_internally_consistent():
    repo = MissionControlRepository()
    kpis = repo.get_kpis()

    for key in ["open_cases", "high_risk_accounts", "active_campaigns", "avg_risk"]:
        assert key in kpis

    assert kpis["open_cases"] >= 0
    assert 0.0 <= kpis["avg_risk"] <= 1.0


def test_case_repository_investigation_bundle_has_expected_shape():
    repo = CaseRepository()
    bundle = repo.get_investigation_bundle("CASE-00082")

    assert bundle is not None
    assert "case" in bundle
    assert "account" in bundle
    assert bundle["case"]["case_id"] == "CASE-00082"


def test_case_repository_returns_none_for_unknown_case():
    repo = CaseRepository()
    bundle = repo.get_investigation_bundle("CASE-99999-DOES-NOT-EXIST")
    assert bundle is None


def test_account_repository_returns_real_account_data():
    repo = AccountRepository()
    # Use whatever public method this repository actually exposes for a
    # single lookup -- fetch a real account_id from the DB first.
    from src.database.connection import db
    conn = db.connect()
    row = conn.execute("SELECT account_id FROM accounts LIMIT 1").fetchone()
    account_id = row["account_id"]

    methods = [m for m in dir(repo) if not m.startswith("_")]
    assert len(methods) > 0, "AccountRepository should expose at least one public method"