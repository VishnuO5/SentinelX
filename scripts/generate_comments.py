"""
scripts/generate_comments.py

SentinelX - Generate Comments

FIX v2: accounts in a campaign cluster reuse text from a shared per-cluster
template pool, simulating coordinated copy-paste behavior.

FIX v3: reuse rate is no longer flat across all campaign types. Different
abuse types have different real-world text-coordination signatures --
bot networks and spam post near-identical text, while harassment repeatedly
targets one victim without needing identical wording, and scams vary
surface text around a shared link. Reuse rate per type reflects that,
so similarity_score differentiates campaign types instead of converging
to one flat number.
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

TOXICITY_COLS = ["toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"]

# Fraction of a clustered account's comments that reuse the cluster's
# shared template pool, by campaign_type. Reflects real coordination
# signatures: bot/spam networks copy-paste heavily, harassment repeats a
# target rather than a message, scams vary wording around a shared link.
CLUSTER_REUSE_RATE_BY_TYPE = {
    "bot_network": 0.90,
    "spam": 0.75,
    "fake_engagement": 0.55,
    "scam": 0.35,
    "repeat_offender": 0.15,
    "harassment": 0.12,
}
DEFAULT_REUSE_RATE = 0.50
TEMPLATE_POOL_SIZE = 5

# ------------------------------------------------------------------
# Load real data
# ------------------------------------------------------------------

jigsaw = pd.read_csv(config.JIGSAW_DATASET)
jigsaw["is_toxic"] = jigsaw[TOXICITY_COLS].max(axis=1)

behaviour = pd.read_csv(config.GENERATED_DIR / "behaviour.csv")
accounts = pd.read_csv(config.GENERATED_DIR / "accounts.csv")
accounts_by_id = accounts.set_index("account_id")

toxic_pool = jigsaw[jigsaw["is_toxic"] == 1].sample(frac=1, random_state=config.RANDOM_SEED).reset_index(drop=True)
clean_pool = jigsaw[jigsaw["is_toxic"] == 0].sample(frac=1, random_state=config.RANDOM_SEED).reset_index(drop=True)

toxic_cursor = 0
clean_cursor = 0


def take_row(is_toxic: bool):
    global toxic_cursor, clean_cursor
    if is_toxic and toxic_cursor < len(toxic_pool):
        row = toxic_pool.iloc[toxic_cursor]
        toxic_cursor += 1
        return row
    if clean_cursor < len(clean_pool):
        row = clean_pool.iloc[clean_cursor]
        clean_cursor += 1
        return row
    row = toxic_pool.iloc[toxic_cursor % len(toxic_pool)]
    toxic_cursor += 1
    return row


def label_and_score(row) -> tuple:
    labels = [c for c in TOXICITY_COLS if row[c] == 1]
    if not labels:
        return "clean", 0.0
    score = round(float(row[TOXICITY_COLS].mean()), 3)
    return ",".join(labels), score


# ------------------------------------------------------------------
# Build one shared template pool per campaign cluster.
# ------------------------------------------------------------------

clustered = behaviour[behaviour["cluster_id"].notna()]
cluster_template_pools = {}
cluster_campaign_type = {}

for cluster_id, group in clustered.groupby("cluster_id"):
    avg_p_toxic = float(group["toxicity_probability"].mean())
    pool_rows = []
    for _ in range(TEMPLATE_POOL_SIZE):
        is_toxic_draw = random.random() < avg_p_toxic
        pool_rows.append(take_row(is_toxic_draw))
    cluster_template_pools[cluster_id] = pool_rows
    cluster_campaign_type[cluster_id] = group["campaign_type"].iloc[0]

PLATFORM_SURFACES = ["comments", "livechat", "community_post", "shorts_comments"]

records = []
comment_seq = 1

for _, brow in behaviour.iterrows():
    account_id = brow["account_id"]
    n = int(brow["expected_comments"])
    p_toxic = float(brow["toxicity_probability"])
    cluster_id = brow["cluster_id"] if pd.notna(brow["cluster_id"]) else None

    acc_created = pd.to_datetime(accounts_by_id.loc[account_id, "created_at"])
    window_days = max(1, (config.CURRENT_TIME - acc_created).days)

    template_pool = cluster_template_pools.get(cluster_id) if cluster_id else None
    campaign_type = cluster_campaign_type.get(cluster_id) if cluster_id else None
    reuse_rate = CLUSTER_REUSE_RATE_BY_TYPE.get(campaign_type, DEFAULT_REUSE_RATE)

    for _ in range(n):
        if template_pool and random.random() < reuse_rate:
            row = random.choice(template_pool)
        else:
            is_toxic_draw = random.random() < p_toxic
            row = take_row(is_toxic_draw)

        label, score = label_and_score(row)
        posted_at = acc_created + pd.Timedelta(days=random.randint(0, window_days))

        records.append({
            "comment_id": f"COM-{comment_seq:06d}",
            "account_id": account_id,
            "text": str(row["comment_text"])[:2000],
            "toxicity_label": label,
            "toxicity_score": score,
            "posted_at": posted_at.strftime(config.DATE_FORMAT),
            "platform_surface": random.choice(PLATFORM_SURFACES),
        })
        comment_seq += 1

comments = pd.DataFrame(records)

output_file = config.GENERATED_DIR / "comments.csv"
comments.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(comments.head())
    print(f"\nTotal Comments: {len(comments)}")
    print(f"Toxic pool used: {toxic_cursor} / {len(toxic_pool)}")
    print(f"Clean pool used: {clean_cursor} / {len(clean_pool)}")
    print(f"Clusters with shared templates: {len(cluster_template_pools)}")
    print(f"Saved to: {output_file}")