"""
scripts/generate_policy_experiments.py
=========================================
Populates policy_experiments.csv with REAL precision/recall numbers,
not placeholders. The experiment: "what if we changed the composite
risk-score threshold used to flag an account as high-risk?"

Ground truth proxy: campaign_id IS NOT NULL (an account confirmed to
belong to a real behavioral cluster -- see generate_behaviour.py /
generate_campaigns.py). This is the same honesty tradeoff a real T&S
team faces -- there's no perfect ground truth, only the best available
confirmed-abuse signal -- but every number below is a genuine computation
against that proxy, not a randomly chosen value.

baseline = config.HIGH_RISK_THRESHOLD (what Mission Control currently uses)
tested   = a sweep of alternative thresholds
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import config

accounts = pd.read_csv(config.GENERATED_DIR / "accounts.csv")
accounts["is_abusive"] = accounts["campaign_id"].notna()


def precision_recall(threshold: float) -> tuple[float, float]:
    predicted_positive = accounts["risk_score"] >= threshold
    actual_positive = accounts["is_abusive"]

    tp = (predicted_positive & actual_positive).sum()
    fp = (predicted_positive & ~actual_positive).sum()
    fn = (~predicted_positive & actual_positive).sum()

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return round(float(precision), 3), round(float(recall), 3)


def false_positive_rate(threshold: float) -> float:
    predicted_positive = accounts["risk_score"] >= threshold
    actual_negative = ~accounts["is_abusive"]
    fp = (predicted_positive & actual_negative).sum()
    total_negative = actual_negative.sum()
    return round(float(fp / total_negative), 3) if total_negative > 0 else 0.0


baseline_threshold = config.HIGH_RISK_THRESHOLD
tested_thresholds = [0.25, 0.30, 0.35, 0.45, 0.50, 0.55]
tested_thresholds = tested_thresholds[: config.NUM_POLICY_EXPERIMENTS]

baseline_precision, baseline_recall = precision_recall(baseline_threshold)
baseline_fpr = false_positive_rate(baseline_threshold)

records = []
for i, tested_threshold in enumerate(tested_thresholds, start=1):
    tested_precision, tested_recall = precision_recall(tested_threshold)
    tested_fpr = false_positive_rate(tested_threshold)

    records.append({
        "experiment_id": f"EXP-{i:03d}",
        "experiment_name": f"High-risk threshold: {baseline_threshold} -> {tested_threshold}",
        "parameter_changed": "high_risk_threshold",
        "baseline_value": baseline_threshold,
        "tested_value": tested_threshold,
        "baseline_precision": baseline_precision,
        "baseline_recall": baseline_recall,
        "tested_precision": tested_precision,
        "tested_recall": tested_recall,
        "false_positive_delta": round(tested_fpr - baseline_fpr, 3),
        "run_at": config.CURRENT_TIME.strftime(config.DATE_FORMAT),
    })

experiments = pd.DataFrame(records)
output_file = config.GENERATED_DIR / "policy_experiments.csv"
experiments.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(experiments.to_string(index=False))
    print(f"\nBaseline threshold {baseline_threshold}: precision={baseline_precision}, recall={baseline_recall}")
    print(f"Saved to: {output_file}")