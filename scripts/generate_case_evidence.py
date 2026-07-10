"""
scripts/generate_case_evidence.py
====================================
Populates case_evidence.csv -- the actual evidence items attached to
each case, used by the Evidence Graph Explorer.

For every case, evidence is pulled from real, already-generated data:
  - up to 3 of the account's own comments, highest toxicity first
  - up to 2 report reasons filed against the account (aggregated)
  - the linked campaign, if any

added_at reuses the case's real "evidence_collected" timestamp from
case_timeline.csv where available, so the evidence log is consistent
with the case's actual recorded timeline instead of inventing a second,
unrelated set of times.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import config

GEN = config.GENERATED_DIR

cases = pd.read_csv(GEN / "cases.csv")
comments = pd.read_csv(GEN / "comments.csv")
reports = pd.read_csv(GEN / "reports.csv")
timeline = pd.read_csv(GEN / "case_timeline.csv")

# real "evidence_collected" timestamp per case, if it exists
evidence_time = (
    timeline[timeline["event_type"] == "evidence_collected"]
    .groupby("case_id")["event_timestamp"].first()
    .to_dict()
)

records = []
idx = 1

for _, case in cases.iterrows():
    case_id = case["case_id"]
    account_id = case["account_id"]
    added_by = case["assigned_moderator_id"]
    added_at = evidence_time.get(case_id, case["opened_at"])

    # top comments by toxicity for this account
    acc_comments = (
        comments[comments["account_id"] == account_id]
        .sort_values("toxicity_score", ascending=False)
        .head(3)
    )
    for _, c in acc_comments.iterrows():
        records.append({
            "evidence_id": f"EVD-{idx:06d}",
            "case_id": case_id,
            "evidence_type": "comment",
            "reference_id": c["comment_id"],
            "added_at": added_at,
            "added_by": added_by,
        })
        idx += 1

    # top report reasons for this account (one evidence row per distinct reason)
    acc_reports = reports[reports["account_id"] == account_id]
    top_reasons = acc_reports["report_reason"].value_counts().head(2)
    for reason in top_reasons.index:
        # reference the first report_id with that reason as a concrete pointer
        ref_report = acc_reports[acc_reports["report_reason"] == reason].iloc[0]
        records.append({
            "evidence_id": f"EVD-{idx:06d}",
            "case_id": case_id,
            "evidence_type": "report",
            "reference_id": ref_report["report_id"],
            "added_at": added_at,
            "added_by": added_by,
        })
        idx += 1

    # linked campaign, if any
    if pd.notna(case.get("campaign_id")):
        records.append({
            "evidence_id": f"EVD-{idx:06d}",
            "case_id": case_id,
            "evidence_type": "campaign",
            "reference_id": case["campaign_id"],
            "added_at": added_at,
            "added_by": added_by,
        })
        idx += 1

evidence = pd.DataFrame(records)
output_file = GEN / "case_evidence.csv"
evidence.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(evidence.head(10).to_string(index=False))
    print(f"\nTotal Evidence Items: {len(evidence)}")
    print(f"Cases with evidence: {evidence['case_id'].nunique()} / {len(cases)}")
    print(evidence["evidence_type"].value_counts().to_string())
    print(f"\nSaved to: {output_file}")