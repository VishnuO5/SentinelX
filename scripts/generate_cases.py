"""
generate_cases.py
=================
Generates cases.csv with REAL case-campaign-account linkage.

Logic:
  - Abusive accounts (those with a campaign_id) are the primary source of cases —
    their case references their actual campaign and their own reports as evidence.
  - A smaller number of cases come from non-campaign accounts flagged by high
    report volume (genuine false-positive / collateral cases an analyst would see).

case_type is derived from the account's actual campaign_type (not random.choice),
so an investigator looking at a "spam" case will actually see spam comments.
"""

from __future__ import annotations

import random
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import config

random.seed(config.RANDOM_SEED)
np.random.seed(config.RANDOM_SEED)

GEN = PROJECT_ROOT / "generated_data"

accounts  = pd.read_csv(GEN / "accounts.csv")
campaigns = pd.read_csv(GEN / "campaigns.csv")
reports   = pd.read_csv(GEN / "reports.csv")
behaviour = pd.read_csv(GEN / "behaviour.csv")

# FIX (issue #13): campaign_type and case_type were unified into the same
# taxonomy in config.py (config.CAMPAIGN_TYPES == config.CASE_TYPES ==
# config.ABUSE_TYPES). This CAMPAIGN_TO_CASE dict was left over from BEFORE
# that unification and still used the old pre-unification keys
# ("mass_harassment", "scam_links", "coordinated_spam"). Since those keys
# never matched the real campaign_type values ("harassment", "scam", "spam",
# etc.), every harassment/scam case silently fell through .get(c_type,
# "spam") and got mislabeled as case_type="spam". Confirmed: 37 harassment
# cases and 20 scam cases were mislabeled before this fix.
# campaign_type now maps directly onto case_type -- no lookup table needed.

PRIORITIES   = ["low", "medium", "high", "critical"]
STATUSES     = ["open", "in_progress", "escalated", "resolved"]
MODERATOR_IDS = [f"MOD-{i:03d}" for i in range(1, config.NUM_MODERATORS + 1)]

# Report counts per account (used for priority and non-campaign case selection)
report_counts = reports.groupby("account_id")["report_id"].count().rename("report_count")
accounts = accounts.join(report_counts, on="account_id")
accounts["report_count"] = accounts["report_count"].fillna(0)

# Merge campaign info onto accounts
accounts = accounts.merge(
    campaigns[["campaign_id","campaign_type","status"]],
    on="campaign_id", how="left", suffixes=("","_camp")
)
accounts = accounts.merge(behaviour[["account_id","profile"]], on="account_id", how="left")

# ── Build cases ──────────────────────────────────────────────────────────────

def priority_from_reports(n: int) -> str:
    if n >= 20: return "critical"
    if n >= 10: return "high"
    if n >= 4:  return "medium"
    return "low"

def build_case(idx, account_row, forced_campaign_id=None, forced_case_type=None):
    opened = config.CURRENT_TIME - timedelta(days=random.randint(0, 180))
    status = random.choice(STATUSES)
    resolved = None
    if status == "resolved":
        resolved = (opened + timedelta(days=random.randint(1, 15))).strftime(config.DATE_FORMAT)

    camp_id = forced_campaign_id or account_row.get("campaign_id")
    c_type  = forced_case_type   or account_row.get("campaign_type")
    case_type = c_type if c_type and pd.notna(c_type) else random.choice(config.CASE_TYPES)

    return {
        "case_id"              : f"CASE-{idx:05d}",
        "campaign_id"          : camp_id if pd.notna(camp_id) else None,
        "account_id"           : account_row["account_id"],
        "case_type"            : case_type,
        "priority"             : priority_from_reports(int(account_row["report_count"])),
        "status"               : status,
        "opened_at"            : opened.strftime(config.DATE_FORMAT),
        "resolved_at"          : resolved,
        "assigned_moderator_id": random.choice(MODERATOR_IDS),
    }

cases = []
idx = 1

# Tier 1: one case per abusive account that has a real campaign_id
abusive = accounts[accounts["campaign_id"].notna()].copy()
for _, row in abusive.iterrows():
    cases.append(build_case(idx, row))
    idx += 1

# Tier 2: fill remaining slots with high-report non-campaign accounts
needed = 180 - len(cases)
if needed > 0:
    non_campaign = accounts[accounts["campaign_id"].isna()].copy()
    non_campaign = non_campaign.sort_values("report_count", ascending=False)
    for _, row in non_campaign.head(needed).iterrows():
        cases.append(build_case(idx, row))
        idx += 1

cases_df = pd.DataFrame(cases).head(180)
cases_df.to_csv(GEN / "cases.csv", index=False)

print(cases_df.head().to_string(index=False))
print(f"\nTotal Cases : {len(cases_df)}")
print(f"With real campaign link : {cases_df['campaign_id'].notna().sum()}")
print(f"case_type distribution :\n{cases_df['case_type'].value_counts().to_string()}")
print(f"\nSaved: {GEN / 'cases.csv'}")