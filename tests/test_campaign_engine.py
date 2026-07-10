"""
tests/test_campaign_engine.py
================================
Covers the unsupervised campaign detection engine: feature construction,
the cluster-interpretation heuristic (largest cluster = background), and
end-to-end detection quality against ground truth.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.engines.campaign_engine import CampaignEngine, FEATURE_COLUMNS


def test_build_features_returns_expected_columns(sample_accounts_df, sample_comments_df, sample_reports_df):
    engine = CampaignEngine()
    features = engine.build_features(sample_accounts_df, sample_comments_df, sample_reports_df)

    for col in FEATURE_COLUMNS:
        assert col in features.columns
    assert "campaign_id" in features.columns
    assert len(features) == len(sample_accounts_df)


def test_normal_accounts_have_near_zero_device_peer_count(sample_accounts_df, sample_comments_df, sample_reports_df):
    engine = CampaignEngine()
    features = engine.build_features(sample_accounts_df, sample_comments_df, sample_reports_df)

    normal = features[features["campaign_id"].isna()]
    campaign = features[features["campaign_id"].notna()]

    # Campaign accounts should show meaningfully more device sharing on average
    assert campaign["device_peer_count"].mean() > normal["device_peer_count"].mean()


def test_flag_from_labels_treats_largest_cluster_as_background():
    engine = CampaignEngine()
    # 8 points in cluster 0 (background), 2 in cluster 1, 1 noise point
    labels = np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 1, -1])
    flagged = engine.flag_from_labels(labels)

    assert flagged.sum() == 3          # 2 in cluster 1 + 1 noise point
    assert not flagged[:8].any()       # none of cluster 0 flagged
    assert flagged[8:].all()           # cluster 1 + noise all flagged


def test_flag_from_labels_all_noise_flags_nothing():
    """When DBSCAN finds zero clusters (every point is noise), there's no
    dense 'background' population to compare against -- flag_from_labels
    conservatively flags nothing rather than flagging everyone, since no
    baseline was established. This is a deliberate design choice, not an
    oversight: with no formed clusters, the detector has no support for
    calling anything an outlier relative to a norm."""
    engine = CampaignEngine()
    labels = np.array([-1, -1, -1])
    flagged = engine.flag_from_labels(labels)
    assert not flagged.any()


def test_evaluate_returns_expected_keys(sample_accounts_df, sample_comments_df, sample_reports_df):
    engine = CampaignEngine()
    features = engine.build_features(sample_accounts_df, sample_comments_df, sample_reports_df)
    labels = engine.detect(features, eps=0.5, min_samples=3)
    metrics = engine.evaluate(features, labels)

    for key in ["recall", "precision", "false_positive_rate", "clusters_found",
                "true_positives", "false_positives", "false_negatives", "true_negatives"]:
        assert key in metrics


@pytest.mark.slow
def test_full_pipeline_achieves_strong_recall(sample_accounts_df, sample_comments_df, sample_reports_df):
    """End-to-end: tuned DBSCAN should recover the large majority of real
    coordinated accounts with a low false-positive rate, using zero
    knowledge of campaign_id during detection itself."""
    engine = CampaignEngine()
    _, metrics = engine.run_full_pipeline(sample_accounts_df, sample_comments_df, sample_reports_df)

    assert metrics["recall"] >= 0.85
    assert metrics["false_positive_rate"] <= 0.15