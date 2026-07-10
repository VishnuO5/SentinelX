"""
SentinelX - Generate Accounts

FIX vs. previous version: risk_score and campaign_id are no longer
hardcoded to None. campaign_id is set here directly from behaviour.csv's
cluster_id (matched to the campaign_id generate_campaigns.py assigns to
that same cluster). risk_score is intentionally left NULL at this stage
and back-filled by generate_signal_scores.py once real signals exist --
that's a cache of a computed value, not a value this script should invent.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import config

fake = Faker()
Faker.seed(config.RANDOM_SEED)
random.seed(config.RANDOM_SEED)
np.random.seed(config.RANDOM_SEED)

behaviour = pd.read_csv(config.GENERATED_DIR / "behaviour.csv")
cluster_to_campaign = pd.read_csv(config.GENERATED_DIR / "cluster_campaign_map.csv") \
    .set_index("cluster_id")["campaign_id"].to_dict()


def account_status(profile: str) -> str:
    if profile == "normal":
        return random.choices(
            list(config.ACCOUNT_STATUS_DISTRIBUTION.keys()),
            weights=list(config.ACCOUNT_STATUS_DISTRIBUTION.values()),
        )[0]
    # abusive profiles skew toward review/suspension
    return random.choices(
        ["active", "under_review", "suspended", "banned"],
        weights=[0.30, 0.30, 0.25, 0.15],
    )[0]


records = []
for _, row in behaviour.iterrows():
    created_at = config.CURRENT_TIME - pd.Timedelta(days=int(row["account_age_days"]))
    campaign_id = cluster_to_campaign.get(row["cluster_id"]) if pd.notna(row["cluster_id"]) else None

    records.append({
        "account_id": row["account_id"],
        "created_at": created_at.strftime(config.DATE_FORMAT),
        "device_id": row["device_id"],
        "ip_region": row["ip_region"],
        "display_name": fake.name(),
        "status": account_status(row["profile"]),
        "risk_score": None,  # back-filled by generate_signal_scores.py
        "campaign_id": campaign_id,
    })

accounts = pd.DataFrame(records)

output_file = config.GENERATED_DIR / "accounts.csv"
accounts.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(accounts.head())
    print(f"\nAccounts Generated: {len(accounts)}")
    print(f"Accounts linked to a campaign: {accounts['campaign_id'].notna().sum()}")
    print(f"Saved to:\n{output_file}")