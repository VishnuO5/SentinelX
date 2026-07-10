"""
scripts/generate_case_timeline.py
====================================
Populates case_timeline.csv -- the reconstruction of how each case
unfolded, used by the Investigation Replay page.

Events are derived from real case data (opened_at, status, resolved_at)
rather than invented independently: every case gets a "case_opened"
event, cases that progressed get "evidence_collected", cases that were
escalated get "escalated", and resolved cases get "resolved" -- always
consistent with that case's actual current status in cases.csv, so the
replay never shows a timeline that contradicts the case's real outcome.

Run AFTER generate_cases.py.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import config

random.seed(config.RANDOM_SEED)
np.random.seed(config.RANDOM_SEED)

cases = pd.read_csv(config.GENERATED_DIR / "cases.csv", parse_dates=["opened_at", "resolved_at"])

STATUS_PROGRESSION = {
    "open": ["case_opened"],
    "in_progress": ["case_opened", "evidence_collected"],
    "escalated": ["case_opened", "evidence_collected", "escalated"],
    "resolved": ["case_opened", "evidence_collected", "resolved"],
}

EVENT_DESCRIPTIONS = {
    "case_opened": "Case opened following signal threshold breach.",
    "evidence_collected": "Evidence gathered from account comments, reports, and campaign linkage.",
    "escalated": "Case escalated to senior review.",
    "resolved": "Investigation concluded; action taken on account.",
}

records = []
event_seq = 1

for _, case in cases.iterrows():
    status = case["status"]
    steps = STATUS_PROGRESSION.get(status, ["case_opened"])
    opened_at = case["opened_at"]
    resolved_at = case["resolved_at"] if pd.notna(case["resolved_at"]) else None

    # spread intermediate events between opened_at and (resolved_at or now)
    end_anchor = resolved_at if resolved_at is not None else config.CURRENT_TIME
    span_hours = max((end_anchor - opened_at).total_seconds() / 3600, 1)

    for i, event_type in enumerate(steps):
        if event_type == "case_opened":
            event_time = opened_at
        elif event_type == "resolved" and resolved_at is not None:
            event_time = resolved_at
        else:
            # place intermediate events at a random point within the span,
            # keeping them in chronological order
            fraction = (i + random.uniform(0.1, 0.9)) / len(steps)
            event_time = opened_at + pd.Timedelta(hours=span_hours * min(fraction, 0.95))

        records.append({
            "event_id": f"EVT-{event_seq:06d}",
            "case_id": case["case_id"],
            "event_type": event_type,
            "event_timestamp": event_time.strftime(config.DATE_FORMAT),
            "event_description": EVENT_DESCRIPTIONS[event_type],
        })
        event_seq += 1

timeline = pd.DataFrame(records)
output_file = config.GENERATED_DIR / "case_timeline.csv"
timeline.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(timeline.head(10).to_string(index=False))
    print(f"\nTotal Timeline Events: {len(timeline)}")
    print(f"Cases covered: {timeline['case_id'].nunique()} / {len(cases)}")
    print(f"Saved to: {output_file}")