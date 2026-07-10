"""
SentinelX - Behaviour Engine

Generates the behavioural profile for every synthetic account. This is the
actual source of truth for the rest of the pipeline: generate_accounts.py,
generate_comments.py, generate_reports.py, generate_campaigns.py, and
generate_signal_scores.py all read this file rather than re-rolling their
own independent randomness.

FIX vs. previous version: device_id/ip_region are no longer generated here
per-account from a tiny integer range (that caused 81.5% of all accounts to
collide on a single device_id). Instead, abusive profiles are grouped into
explicit clusters (a cluster = one future campaign), each with its own
small pool of shared device_ids and a dominant IP region. Normal accounts
each get a unique device_id, exactly as a real distinct user would.

FIX v2: cluster (campaign) size range tightened from 12-40 to 6-18. The
wider range produced too few, oversized clusters (~10 campaigns from ~172
abusive accounts). The tighter range produces more, smaller campaigns
(~14-16), closer to the NUM_CAMPAIGNS target in config.py. Exact count is
not forced -- it falls out naturally from how many abusive accounts of
each type exist, same as before, just with a smaller average chunk size.
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

# ------------------------------------------------------------------
# Step 1: assign every account a profile
# ------------------------------------------------------------------

profiles = list(config.ACCOUNT_PROFILE_DISTRIBUTION.keys())
weights = list(config.ACCOUNT_PROFILE_DISTRIBUTION.values())

account_ids = [f"ACC-{i:06d}" for i in range(1, config.NUM_ACCOUNTS + 1)]
assigned_profiles = random.choices(profiles, weights=weights, k=config.NUM_ACCOUNTS)

# ------------------------------------------------------------------
# Step 2: group abusive accounts into clusters (one cluster == one
# future campaign). Cluster size 6-18 accounts, tuned to land close to
# NUM_CAMPAIGNS given the real size of each abuse-type population.
# ------------------------------------------------------------------

abusive_by_type = {t: [] for t in config.ABUSE_TYPES}
normal_accounts = []

for acc_id, profile in zip(account_ids, assigned_profiles):
    if profile == "normal":
        normal_accounts.append(acc_id)
    else:
        abusive_by_type[profile].append(acc_id)

clusters = []  # list of dicts: {cluster_id, campaign_type, account_ids, device_pool, ip_region}
cluster_seq = 1
device_seq = 1

for abuse_type, accs in abusive_by_type.items():
    if not accs:
        continue
    random.shuffle(accs)
    cursor = 0
    while cursor < len(accs):
        size = random.randint(6, 18)
        chunk = accs[cursor: cursor + size]
        cursor += size
        if not chunk:
            continue

        n_devices = max(2, min(6, len(chunk) // 4 + 2))
        device_pool = [f"DEV-{device_seq + j:04d}" for j in range(n_devices)]
        device_seq += n_devices
        dominant_ip = random.choice(config.IP_REGIONS)

        clusters.append({
            "cluster_id": f"CLU-{cluster_seq:03d}",
            "campaign_type": abuse_type,
            "account_ids": chunk,
            "device_pool": device_pool,
            "dominant_ip": dominant_ip,
        })
        cluster_seq += 1

account_to_cluster = {}
for c in clusters:
    for acc_id in c["account_ids"]:
        account_to_cluster[acc_id] = c

# ------------------------------------------------------------------
# Step 3: build the per-account behaviour record
# ------------------------------------------------------------------

records = []

for acc_id, profile in zip(account_ids, assigned_profiles):
    rules = config.PROFILE_RULES[profile]

    expected_comments = random.randint(*rules["comments"])
    toxicity_probability = round(random.uniform(*rules["toxicity_prob"]), 3)
    report_probability = round(random.uniform(*rules["report_prob"]), 3)
    account_age_days = random.randint(*rules["account_age_days"])

    cluster = account_to_cluster.get(acc_id)
    if cluster is not None:
        cluster_id = cluster["cluster_id"]
        campaign_type = cluster["campaign_type"]
        device_id = random.choice(cluster["device_pool"])
        ip_region = cluster["dominant_ip"] if random.random() < 0.7 else random.choice(config.IP_REGIONS)
    else:
        cluster_id = None
        campaign_type = None
        device_id = f"DEV-{device_seq:04d}"
        device_seq += 1
        ip_region = random.choice(config.IP_REGIONS)

    records.append({
        "account_id": acc_id,
        "profile": profile,
        "cluster_id": cluster_id,
        "campaign_type": campaign_type,
        "device_id": device_id,
        "ip_region": ip_region,
        "account_age_days": account_age_days,
        "expected_comments": expected_comments,
        "toxicity_probability": toxicity_probability,
        "report_probability": report_probability,
    })

behaviour = pd.DataFrame(records)

output_dir = config.GENERATED_DIR
output_dir.mkdir(exist_ok=True)
output_file = output_dir / "behaviour.csv"
behaviour.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(behaviour.head())
    print(f"\nBehaviour Records: {len(behaviour)}")
    print(f"Clusters formed: {len(clusters)}")
    print(behaviour["profile"].value_counts())
    print(f"\nSaved to:\n{output_file}")