"""
tests/test_reasoning_engine.py
=================================
Covers the multi-step reasoning trace (fallback mode -- no Groq key
required to run these) and the fixed "dominant signal by weighted
contribution, not raw magnitude" bug.
"""

from __future__ import annotations

from src.ai.reasoning_engine import ReasoningEngine, _top_signal_name, _rule_based_trace
from src.repositories.case_repository import CaseRepository


def test_top_signal_uses_weighted_contribution_not_raw_magnitude():
    """Regression test for the fixed bug. With config.SIGNAL_WEIGHTS =
    account_age: 0.15, device_reuse: 0.25 -- a higher raw account_age
    value should NOT beat a moderately-high device_reuse value once
    weights are applied. 0.95 * 0.15 = 0.1425 (account_age contribution)
    vs 0.70 * 0.25 = 0.175 (device_reuse contribution) -- device_reuse
    should win despite the lower raw number."""
    signals = {
        "account_age_signal": 0.95,
        "device_reuse_signal": 0.70,
        "report_volume_signal": 0.10,
        "ip_region_signal": 0.10,
        "toxicity_signal": 0.10,
    }
    assert _top_signal_name(signals) == "device reuse"


def test_top_signal_handles_empty_signals():
    assert _top_signal_name({}) == "insufficient signal data"


def test_rule_based_trace_has_four_steps():
    bundle = CaseRepository().get_investigation_bundle("CASE-00082")
    result = _rule_based_trace(bundle)

    assert result["mode"] == "fallback"
    assert len(result["steps"]) == 4
    step_names = [s["step"] for s in result["steps"]]
    assert step_names == ["Evidence Gathering", "Pattern Analysis", "Risk Correlation", "Verdict"]


def test_rule_based_trace_content_is_non_empty():
    bundle = CaseRepository().get_investigation_bundle("CASE-00082")
    result = _rule_based_trace(bundle)
    for step in result["steps"]:
        assert len(step["content"]) > 10


def test_reasoning_engine_falls_back_without_api_key():
    """With no GROQ_API_KEY, ReasoningEngine must use the deterministic
    fallback rather than raising."""
    engine = ReasoningEngine(api_key=None)
    bundle = CaseRepository().get_investigation_bundle("CASE-00082")
    result = engine.reason(bundle)

    assert result["mode"] == "fallback"
    assert len(result["steps"]) == 4


def test_reasoning_engine_runs_across_multiple_real_cases():
    """No crashes across a sample of real cases -- different evidence
    shapes (with/without campaign link, with/without reports)."""
    repo = CaseRepository()
    engine = ReasoningEngine(api_key=None)

    sample_case_ids = [c["case_id"] for c in repo.list_recent_cases(limit=10)]
    for case_id in sample_case_ids:
        bundle = repo.get_investigation_bundle(case_id)
        if bundle is None:
            continue
        result = engine.reason(bundle)
        assert len(result["steps"]) == 4