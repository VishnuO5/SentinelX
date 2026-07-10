"""
generate_signal_scores.py
=========================
Computes the Unified Signal Engine scores for every account.

Every signal is derived from REAL data — no random.uniform() anywhere.
Each signal is normalised to [0.0, 1.0] where higher = more suspicious.

Five signals:
    account_age_signal   — how new is the account? Newer = higher risk.
    report_volume_signal — how many unique reports has this account attracted?
    device_reuse_signal  — how many OTHER accounts share this device? More = higher risk.
    ip_region_signal     — how many OTHER accounts in the same campaign share this IP? More = higher risk.
    toxicity_signal      — what fraction of this account's own comments are toxic or severe_toxic?

Composite:
    final_risk = weighted sum of the five, using weights defined at the bottom.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import config

np.random.seed(config.RANDOM_SEED)

GEN = PROJECT_ROOT / "generated_data"

accounts  = pd.read_csv(GEN / "accounts.csv",  parse_dates=["created_at"])
comments  = pd.read_csv(GEN / "comments.csv",  parse_dates=["posted_at"])
reports   = pd.read_csv(GEN / "reports.csv")
behaviour = pd.read_csv(GEN / "behaviour.csv")

REFERENCE_DATE = config.CURRENT_TIME

# Signal 1: Account Age — newer = more suspicious
accounts["_age_days"] = (
    REFERENCE_DATE - accounts["created_at"]
).dt.total_seconds() / 86400
max_age = accounts["_age_days"].max()
accounts["account_age_signal"] = (1.0 - (accounts["_age_days"] / max_age)).clip(0, 1).round(4)

# Signal 2: Report Volume — more reports = more suspicious
report_counts = (
    reports.groupby("account_id")["report_id"].count()
    .rename("_report_count").reset_index()
)
accounts = accounts.merge(report_counts, on="account_id", how="left")
accounts["_report_count"] = accounts["_report_count"].fillna(0)
max_reports = accounts["_report_count"].max()
accounts["report_volume_signal"] = (
    (accounts["_report_count"] / max_reports).clip(0, 1) if max_reports > 0
    else 0.0
)

# Signal 3: Device Reuse — shared device = coordination signal
device_counts = (
    accounts.groupby("device_id")["account_id"].count()
    .rename("_device_peers").reset_index()
)
accounts = accounts.merge(device_counts, on="device_id", how="left")
accounts["_device_peers"] = (accounts["_device_peers"] - 1).clip(0)
max_dp = accounts["_device_peers"].max()
accounts["device_reuse_signal"] = (
    (accounts["_device_peers"] / max_dp).clip(0, 1) if max_dp > 0 else 0.0
)

# Signal 4: IP Region Coordination — accounts in same campaign sharing same IP
campaign_accounts = accounts[accounts["campaign_id"].notna()].copy()
if len(campaign_accounts) > 0:
    ip_camp = (
        campaign_accounts.groupby(["campaign_id", "ip_region"])["account_id"]
        .count().rename("_ip_campaign_peers").reset_index()
    )
    accounts = accounts.merge(ip_camp, on=["campaign_id", "ip_region"], how="left")
    accounts["_ip_campaign_peers"] = accounts["_ip_campaign_peers"].fillna(0)
else:
    accounts["_ip_campaign_peers"] = 0

global_ip = (
    accounts.groupby("ip_region")["account_id"].count()
    .rename("_global_ip").reset_index()
)
accounts = accounts.merge(global_ip, on="ip_region", how="left")
accounts["_ip_raw"] = accounts.apply(
    lambda r: r["_ip_campaign_peers"] if r["_ip_campaign_peers"] > 0
    else r["_global_ip"] / 10.0, axis=1
)
max_ip = accounts["_ip_raw"].max()
accounts["ip_region_signal"] = (
    (accounts["_ip_raw"] / max_ip).clip(0, 1) if max_ip > 0 else 0.0
)

# Signal 5: Toxicity — fraction of own comments that are toxic/severe_toxic
toxic_labels = {"toxic", "severe_toxic"}
comments["_is_toxic"] = comments["toxicity_label"].isin(toxic_labels).astype(int)
tox = (
    comments.groupby("account_id")
    .agg(_total=("comment_id","count"), _toxic=("_is_toxic","sum"))
    .reset_index()
)
tox["toxicity_signal"] = (tox["_toxic"] / tox["_total"]).fillna(0).clip(0, 1)
accounts = accounts.merge(tox[["account_id","toxicity_signal"]], on="account_id", how="left")
accounts["toxicity_signal"] = accounts["toxicity_signal"].fillna(0.0)

# Composite: weighted sum
# FIX: this used to be a local W dict that had silently drifted from
# config.SIGNAL_WEIGHTS (report_volume 0.30 vs config's 0.25, device_reuse
# 0.25 vs 0.20, toxicity 0.20 vs 0.30) -- meaning the Signal Engine page
# would have displayed different weights than what was actually used to
# compute every score in the database. Now there's exactly one place
# these weights are defined.
W = {
    "account_age_signal"   : config.SIGNAL_WEIGHTS["account_age"],
    "report_volume_signal" : config.SIGNAL_WEIGHTS["report_volume"],
    "device_reuse_signal"  : config.SIGNAL_WEIGHTS["device_reuse"],
    "ip_region_signal"     : config.SIGNAL_WEIGHTS["ip_region"],
    "toxicity_signal"      : config.SIGNAL_WEIGHTS["toxicity"],
}
accounts["final_risk"] = (
    W["account_age_signal"]    * accounts["account_age_signal"]
  + W["report_volume_signal"]  * accounts["report_volume_signal"]
  + W["device_reuse_signal"]   * accounts["device_reuse_signal"]
  + W["ip_region_signal"]      * accounts["ip_region_signal"]
  + W["toxicity_signal"]       * accounts["toxicity_signal"]
).round(4)

# Write back risk_score to accounts.csv
accounts["risk_score"] = accounts["final_risk"]

signal_ids = [f"SIG-{str(i+1).zfill(6)}" for i in range(len(accounts))]
output = pd.DataFrame({
    "signal_id"           : signal_ids,
    "account_id"          : accounts["account_id"].values,
    "computed_at"         : REFERENCE_DATE.isoformat(),
    "account_age_signal"  : accounts["account_age_signal"].round(4).values,
    "report_volume_signal": accounts["report_volume_signal"].round(4).values,
    "device_reuse_signal" : accounts["device_reuse_signal"].round(4).values,
    "ip_region_signal"    : accounts["ip_region_signal"].round(4).values,
    "toxicity_signal"     : accounts["toxicity_signal"].round(4).values,
    "final_risk"          : accounts["final_risk"].values,
})

output.to_csv(GEN / "signal_scores.csv", index=False)

accounts_out = accounts[[
    "account_id","created_at","device_id","ip_region",
    "display_name","status","risk_score","campaign_id"
]]
accounts_out.to_csv(GEN / "accounts.csv", index=False)

# Verification
print(f"Signal scores computed for {len(output)} accounts.\n")
print("── Sample (first 5) ───────────────────────────────────────────────")
print(output.head().to_string(index=False))

merged_check = output.merge(behaviour[["account_id","profile"]], on="account_id")
profile_risk = (
    merged_check.groupby("profile")["final_risk"]
    .agg(["mean","min","max","count"]).round(3)
    .sort_values("mean", ascending=False)
)
print("\n── final_risk by profile ───────────────────────────────────────────")
print(profile_risk.to_string())

print("\n── Sanity checks ───────────────────────────────────────────────────")
print(f"  risk_score nulls in accounts.csv : {accounts_out['risk_score'].isna().sum()}")
print(f"  final_risk range                 : [{output['final_risk'].min():.4f}, {output['final_risk'].max():.4f}]")
top3 = output.nlargest(3,"final_risk")[["account_id","final_risk"]]
print(f"  top-3 riskiest:\n{top3.to_string(index=False)}")
print(f"\n  Saved : generated_data/signal_scores.csv")
print(f"  Updated: generated_data/accounts.csv (risk_score populated)")