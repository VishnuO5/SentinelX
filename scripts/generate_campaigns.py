"""
SentinelX - Generate Campaigns

FIX vs. previous version: campaigns are no longer independently random
rows disconnected from any account. Each campaign now corresponds to a
real cluster of accounts formed in generate_behaviour.py (shared devices,
shared dominant IP region, same abuse profile). velocity_score and
network_density are derived from real properties of the cluster
(account-creation spread, device-sharing ratio) rather than pure noise.

similarity_score is intentionally left NULL here -- it requires real
comment text, which doesn't exist yet at this point in the pipeline.
scripts/compute_campaign_similarity.py fills it in after
generate_comments.py has run (real TF-IDF + cosine similarity, per the
earlier agreed decision -- not a placeholder number).

Also writes generated_data/cluster_campaign_map.csv, which
generate_accounts.py uses to link each account to its real campaign_id.
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

behaviour = pd.read_csv(config.GENERATED_DIR / "behaviour.csv")
clustered = behaviour[behaviour["cluster_id"].notna()].copy()

records = []
cluster_map_rows = []

for i, (cluster_id, group) in enumerate(clustered.groupby("cluster_id"), start=1):
    campaign_id = f"CAMP-{i:03d}"
    campaign_type = group["campaign_type"].iloc[0]

    n_accounts = len(group)
    n_devices = group["device_id"].nunique()
    device_sharing_ratio = 1 - (n_devices / n_accounts)  # 0 = no sharing, ~1 = heavy sharing
    network_density = round(min(0.95, max(0.15, device_sharing_ratio + random.uniform(-0.05, 0.05))), 3)

    age_spread_days = group["account_age_days"].max() - group["account_age_days"].min()
    # tight creation window (accounts made within days of each other) = high velocity
    velocity_score = round(min(0.98, max(0.20, 1 - (age_spread_days / 90))), 3)

    first_detected = config.CURRENT_TIME - pd.Timedelta(
        days=int(group["account_age_days"].min()) + random.randint(1, 10)
    )

    status = random.choices(["active", "contained", "resolved"], weights=[0.4, 0.3, 0.3])[0]

    records.append({
        "campaign_id": campaign_id,
        "campaign_type": campaign_type,
        "first_detected_at": first_detected.strftime(config.DATE_FORMAT),
        "velocity_score": velocity_score,
        "similarity_score": None,  # filled by compute_campaign_similarity.py
        "network_density": network_density,
        "status": status,
    })

    cluster_map_rows.append({"cluster_id": cluster_id, "campaign_id": campaign_id, "campaign_type": campaign_type})

campaigns = pd.DataFrame(records)
cluster_map = pd.DataFrame(cluster_map_rows)

config.GENERATED_DIR.mkdir(exist_ok=True)
campaigns.to_csv(config.GENERATED_DIR / "campaigns.csv", index=False)
cluster_map.to_csv(config.GENERATED_DIR / "cluster_campaign_map.csv", index=False)

if __name__ == "__main__":
    print(campaigns)
    print(f"\nTotal Campaigns: {len(campaigns)}")
    print(f"Saved to: {config.GENERATED_DIR / 'campaigns.csv'}")