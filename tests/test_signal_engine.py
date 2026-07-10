"""
tests/test_signal_engine.py
==============================
Covers the Unified Signal Engine: weight validation, the composite
formula, batch scoring against real data, and live hypothetical scoring.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.engines.signal_engine import SignalEngine


def test_weights_must_sum_to_one():
    with pytest.raises(AssertionError):
        SignalEngine(weights={
            "account_age_signal": 0.5, "report_volume_signal": 0.5,
            "device_reuse_signal": 0.5, "ip_region_signal": 0.5,
            "toxicity_signal": 0.5,
        })


def test_composite_is_weighted_sum():
    engine = SignalEngine()
    all_zero = engine.composite({
        "account_age_signal": 0, "report_volume_signal": 0,
        "device_reuse_signal": 0, "ip_region_signal": 0, "toxicity_signal": 0,
    })
    all_one = engine.composite({
        "account_age_signal": 1, "report_volume_signal": 1,
        "device_reuse_signal": 1, "ip_region_signal": 1, "toxicity_signal": 1,
    })
    assert all_zero == 0.0
    assert all_one == pytest.approx(1.0, abs=1e-6)


def test_composite_missing_keys_default_to_zero():
    engine = SignalEngine()
    result = engine.composite({"toxicity_signal": 1.0})
    assert 0 < result < 1.0


def test_score_population_returns_expected_columns(sample_accounts_df, sample_comments_df, sample_reports_df):
    engine = SignalEngine()
    scored = engine.score_population(sample_accounts_df, sample_comments_df, sample_reports_df)

    for col in ["account_age_signal", "report_volume_signal", "device_reuse_signal",
                "ip_region_signal", "toxicity_signal", "final_risk"]:
        assert col in scored.columns

    assert len(scored) == len(sample_accounts_df)
    assert scored["final_risk"].between(0, 1).all()


def test_score_population_matches_stored_signal_scores(sample_accounts_df, sample_comments_df, sample_reports_df):
    """The engine's batch output should match generated_data/signal_scores.csv
    to within floating-point rounding -- proof the extraction didn't change
    the formula that already produced the stored data."""
    engine = SignalEngine()
    scored = engine.score_population(sample_accounts_df, sample_comments_df, sample_reports_df)

    existing = pd.read_csv("generated_data/signal_scores.csv")
    merged = scored[["account_id", "final_risk"]].merge(
        existing[["account_id", "final_risk"]], on="account_id", suffixes=("_new", "_existing")
    )
    diff = (merged["final_risk_new"] - merged["final_risk_existing"]).abs()
    assert diff.max() < 0.001


def test_hypothetical_bot_scores_higher_than_hypothetical_normal(sample_accounts_df):
    engine = SignalEngine()

    bot_like = engine.score_hypothetical(
        created_at="2026-05-30", device_id="DEV-0001", ip_region="South-East-Asia",
        toxic_comment_ratio=0.9, report_count=10, population_accounts=sample_accounts_df,
    )
    normal_like = engine.score_hypothetical(
        created_at="2015-01-01", device_id="DEV-UNIQUE-TEST", ip_region="US-East",
        toxic_comment_ratio=0.0, report_count=0, population_accounts=sample_accounts_df,
    )

    assert bot_like["final_risk"] > normal_like["final_risk"]
    assert 0 <= bot_like["final_risk"] <= 1
    assert 0 <= normal_like["final_risk"] <= 1


def test_hypothetical_signals_are_bounded(sample_accounts_df):
    engine = SignalEngine()
    result = engine.score_hypothetical(
        created_at="2026-06-01", device_id="DEV-0001", ip_region="US-East",
        toxic_comment_ratio=5.0,  # deliberately out-of-range input
        report_count=99999,
        population_accounts=sample_accounts_df,
    )
    for key in ["account_age_signal", "report_volume_signal", "device_reuse_signal",
                "ip_region_signal", "toxicity_signal", "final_risk"]:
        assert 0.0 <= result[key] <= 1.0, f"{key} out of bounds: {result[key]}"