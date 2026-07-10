"""
scripts/generate_counterfactual_runs.py
===========================================
Populates counterfactual_runs.csv -- "what would have happened under a
different policy?" Each scenario below is computed against real report/
account/case_timeline data, not invented numbers.
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

accounts = pd.read_csv(GEN / "accounts.csv", parse_dates=["created_at"])
reports = pd.read_csv(GEN / "reports.csv")
cases = pd.read_csv(GEN / "cases.csv")
timeline = pd.read_csv(GEN / "case_timeline.csv")

report_counts = reports.groupby("account_id").size().rename("report_count")
accounts = accounts.merge(report_counts, on="account_id", how="left")
accounts["report_count"] = accounts["report_count"].fillna(0)

cased_accounts = set(cases["account_id"])
accounts["account_age_days"] = (config.CURRENT_TIME - accounts["created_at"]).dt.days

records = []
run_seq = 1


def add_run(description: str, affected: int, would_flag: int, would_miss: int):
    global run_seq
    records.append({
        "run_id": f"CF-{run_seq:03d}",
        "policy_description": description,
        "cases_affected_count": affected,
        "cases_would_have_flagged": would_flag,
        "cases_would_have_missed": would_miss,
        "run_at": config.CURRENT_TIME.strftime(config.DATE_FORMAT),
    })
    run_seq += 1


# Scenario 1: lower the report threshold for auto-opening a case
newly_flagged = accounts[(accounts["report_count"] >= 3) & (~accounts["account_id"].isin(cased_accounts))]
add_run(
    "Lower report threshold from 5 to 3 reports before auto-opening a case",
    affected=len(newly_flagged), would_flag=len(newly_flagged), would_miss=0,
)

# Scenario 2: raise the report threshold
would_miss_high = accounts[(accounts["account_id"].isin(cased_accounts)) & (accounts["report_count"] < 10)]
add_run(
    "Raise report threshold from 5 to 10 reports before auto-opening a case",
    affected=len(would_miss_high), would_flag=0, would_miss=len(would_miss_high),
)

# Scenario 3: auto-flag any account under 14 days old, regardless of reports
young_uncased = accounts[(accounts["account_age_days"] < 14) & (~accounts["account_id"].isin(cased_accounts))]
add_run(
    "Auto-flag any account under 14 days old regardless of other signals",
    affected=len(young_uncased), would_flag=len(young_uncased), would_miss=0,
)

# Scenario 4: auto-flag any account whose device_id is shared by 3+ other accounts
device_counts = accounts.groupby("device_id")["account_id"].transform("count")
shared_device_uncased = accounts[(device_counts >= 3) & (~accounts["account_id"].isin(cased_accounts))]
add_run(
    "Auto-flag any account sharing a device with 3+ other accounts",
    affected=len(shared_device_uncased), would_flag=len(shared_device_uncased), would_miss=0,
)

# Scenario 5: require escalation before any case can resolve
resolved_case_ids = cases[cases["status"].isin(["resolved", "closed"])]["case_id"]
resolved_timeline = timeline[timeline["case_id"].isin(resolved_case_ids)]
has_escalation = set(resolved_timeline[resolved_timeline["event_type"] == "escalated"]["case_id"])
skipped_escalation = [c for c in resolved_case_ids if c not in has_escalation]
add_run(
    "Require escalation before any case can resolve (no direct open -> resolved)",
    affected=len(skipped_escalation), would_flag=0, would_miss=len(skipped_escalation),
)

counterfactuals = pd.DataFrame(records)
output_file = GEN / "counterfactual_runs.csv"
counterfactuals.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(counterfactuals.to_string(index=False))
    print(f"\nTotal Counterfactual Runs: {len(counterfactuals)}")
    print(f"Saved to: {output_file}")