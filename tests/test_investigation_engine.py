"""
tests/test_investigation_engine.py
=====================================
Covers multi-factor priority scoring, SLA overdue detection (including
the fixed config.CURRENT_TIME anchoring), and rule-based recommendations.
"""

from __future__ import annotations

from datetime import datetime

import config
from src.engines.investigation_engine import InvestigationEngine


def test_high_risk_high_reports_dense_campaign_is_critical_or_high():
    engine = InvestigationEngine()
    result = engine.compute_priority(composite_risk_score=0.9, report_count=75, network_density=0.9)
    assert result["priority"] in ("critical", "high")
    assert result["urgency_score"] > 0.75


def test_low_signal_account_is_low_priority():
    engine = InvestigationEngine()
    result = engine.compute_priority(composite_risk_score=0.05, report_count=0, network_density=0.0)
    assert result["priority"] == "low"
    assert result["urgency_score"] < 0.25


def test_priority_urgency_score_is_bounded():
    engine = InvestigationEngine()
    result = engine.compute_priority(composite_risk_score=1.0, report_count=999999, network_density=1.0)
    assert 0.0 <= result["urgency_score"] <= 1.0


def test_priority_handles_missing_signals_gracefully():
    engine = InvestigationEngine()
    result = engine.compute_priority(composite_risk_score=None, report_count=0, network_density=None)
    assert result["priority"] == "low"


def test_sla_uses_dataset_anchor_time_not_wall_clock():
    """Regression test for the fixed bug: check_sla() must anchor to
    config.CURRENT_TIME by default, not real wall-clock time."""
    engine = InvestigationEngine()
    result_default = engine.check_sla(
        opened_at=config.CURRENT_TIME.isoformat(), status="open", priority="critical"
    )
    result_explicit = engine.check_sla(
        opened_at=config.CURRENT_TIME.isoformat(), status="open", priority="critical",
        reference_time=config.CURRENT_TIME,
    )
    assert result_default["hours_open"] == result_explicit["hours_open"]


def test_sla_resolved_case_is_never_overdue():
    engine = InvestigationEngine()
    result = engine.check_sla(
        opened_at="2020-01-01T00:00:00", status="resolved", priority="critical",
        reference_time=datetime(2026, 6, 1),
    )
    assert result["overdue"] is False


def test_sla_flags_overdue_critical_case():
    engine = InvestigationEngine()
    result = engine.check_sla(
        opened_at="2026-01-01T00:00:00", status="open", priority="critical",
        reference_time=datetime(2026, 6, 1),
    )
    assert result["overdue"] is True
    assert result["hours_open"] > 24


def test_recommend_next_action_closed_case_needs_no_action():
    engine = InvestigationEngine()
    rec = engine.recommend_next_action(priority="high", status="closed", evidence_count=5, overdue=False)
    assert "no action" in rec.lower()


def test_recommend_next_action_overdue_critical_escalates():
    engine = InvestigationEngine()
    rec = engine.recommend_next_action(priority="critical", status="open", evidence_count=3, overdue=True)
    assert "escalate" in rec.lower()


def test_recommend_next_action_no_evidence_flags_it():
    engine = InvestigationEngine()
    rec = engine.recommend_next_action(priority="medium", status="open", evidence_count=0, overdue=False)
    assert "evidence" in rec.lower()