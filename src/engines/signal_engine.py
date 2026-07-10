"""
src/engines/signal_engine.py
==============================
The real Unified Signal Engine logic, extracted from what used to live
only inside generate_signal_scores.py as a one-off batch script. Making
it an actual importable engine means:

  1. The module literally named "Unified Signal Engine" is now an engine,
     not a script -- the batch generator imports and calls this instead
     of duplicating the formula.
  2. A brand-new / hypothetical account can be scored live (e.g. a
     "simulate new account" demo) using the exact same formula and the
     exact same population-relative normalisation as every stored score,
     instead of a second, drifted copy of the math.

Every signal is derived from real data -- no random.uniform() anywhere.
Five signals, each normalised to [0, 1] where higher = more suspicious:
    account_age_signal   -- newer accounts score higher
    report_volume_signal -- more reports received scores higher
    device_reuse_signal  -- more OTHER accounts sharing this device scores higher
    ip_region_signal      -- IP coordination within a campaign, or global IP density
    toxicity_signal       -- fraction of the account's own comments that are toxic
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

TOXIC_LABELS = {"toxic", "severe_toxic"}


class SignalEngine:

    def __init__(self, weights: dict | None = None):
        self.weights = weights or {
            "account_age_signal":   config.SIGNAL_WEIGHTS["account_age"],
            "report_volume_signal": config.SIGNAL_WEIGHTS["report_volume"],
            "device_reuse_signal":  config.SIGNAL_WEIGHTS["device_reuse"],
            "ip_region_signal":     config.SIGNAL_WEIGHTS["ip_region"],
            "toxicity_signal":      config.SIGNAL_WEIGHTS["toxicity"],
        }
        assert abs(sum(self.weights.values()) - 1.0) < 1e-9, \
            "SignalEngine weights must sum to 1.0"

    def composite(self, signals: dict) -> float:
        """Weighted sum of the five signals -> single risk score."""
        return round(sum(self.weights[k] * signals.get(k, 0.0) for k in self.weights), 4)

    def score_population(
        self,
        accounts: pd.DataFrame,
        comments: pd.DataFrame,
        reports: pd.DataFrame,
        reference_date=None,
    ) -> pd.DataFrame:
        """Scores every account in `accounts` against the population it's part of.
        Returns a DataFrame with the five signal columns + final_risk, indexed
        the same as the input (one row per account_id)."""

        accounts = accounts.copy()
        reference_date = reference_date or config.CURRENT_TIME

        if not pd.api.types.is_datetime64_any_dtype(accounts["created_at"]):
            accounts["created_at"] = pd.to_datetime(accounts["created_at"])

        accounts["_age_days"] = (reference_date - accounts["created_at"]).dt.total_seconds() / 86400
        max_age = accounts["_age_days"].max()
        accounts["account_age_signal"] = (
            (1.0 - (accounts["_age_days"] / max_age)).clip(0, 1).round(4)
            if max_age > 0 else 0.0
        )

        report_counts = (
            reports.groupby("account_id")["report_id"].count()
            .rename("_report_count").reset_index()
        )
        accounts = accounts.merge(report_counts, on="account_id", how="left")
        accounts["_report_count"] = accounts["_report_count"].fillna(0)
        max_reports = accounts["_report_count"].max()
        accounts["report_volume_signal"] = (
            (accounts["_report_count"] / max_reports).clip(0, 1) if max_reports > 0 else 0.0
        )

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

        comments = comments.copy()
        comments["_is_toxic"] = comments["toxicity_label"].isin(TOXIC_LABELS).astype(int)
        tox = (
            comments.groupby("account_id")
            .agg(_total=("comment_id", "count"), _toxic=("_is_toxic", "sum"))
            .reset_index()
        )
        tox["toxicity_signal"] = (tox["_toxic"] / tox["_total"]).fillna(0).clip(0, 1)
        accounts = accounts.merge(tox[["account_id", "toxicity_signal"]], on="account_id", how="left")
        accounts["toxicity_signal"] = accounts["toxicity_signal"].fillna(0.0)

        accounts["final_risk"] = accounts.apply(
            lambda r: self.composite({
                "account_age_signal":   r["account_age_signal"],
                "report_volume_signal": r["report_volume_signal"],
                "device_reuse_signal":  r["device_reuse_signal"],
                "ip_region_signal":     r["ip_region_signal"],
                "toxicity_signal":      r["toxicity_signal"],
            }), axis=1
        )

        return accounts

    def score_hypothetical(
        self,
        *,
        created_at,
        device_id: str,
        ip_region: str,
        toxic_comment_ratio: float,
        report_count: int,
        population_accounts: pd.DataFrame,
        reference_date=None,
    ) -> dict:
        """Scores one hypothetical account against the CURRENT population's
        normalisation ranges, so a demo account gets a realistic,
        population-relative score instead of an isolated, meaningless one."""

        reference_date = reference_date or config.CURRENT_TIME
        created_at = pd.Timestamp(created_at)

        pop = population_accounts.copy()
        if not pd.api.types.is_datetime64_any_dtype(pop["created_at"]):
            pop["created_at"] = pd.to_datetime(pop["created_at"])

        pop_age_days = (reference_date - pop["created_at"]).dt.total_seconds() / 86400
        max_age = max(pop_age_days.max(), 1.0)
        own_age_days = (reference_date - created_at).total_seconds() / 86400
        account_age_signal = round(max(0.0, min(1.0, 1.0 - (own_age_days / max_age))), 4)

        max_reports = pop.get("_report_count", pd.Series([0])).max() or 1
        report_volume_signal = round(max(0.0, min(1.0, report_count / max_reports)), 4)

        device_peers = int((pop["device_id"] == device_id).sum())
        max_dp = max(pop.groupby("device_id")["account_id"].count().max() - 1, 1)
        device_reuse_signal = round(max(0.0, min(1.0, device_peers / max_dp)), 4)

        ip_density = int((pop["ip_region"] == ip_region).sum())
        max_ip = max(pop.groupby("ip_region")["account_id"].count().max(), 1)
        ip_region_signal = round(max(0.0, min(1.0, (ip_density / 10.0) / (max_ip / 10.0))), 4)

        toxicity_signal = round(max(0.0, min(1.0, toxic_comment_ratio)), 4)

        signals = {
            "account_age_signal": account_age_signal,
            "report_volume_signal": report_volume_signal,
            "device_reuse_signal": device_reuse_signal,
            "ip_region_signal": ip_region_signal,
            "toxicity_signal": toxicity_signal,
        }
        signals["final_risk"] = self.composite(signals)
        return signals


if __name__ == "__main__":
    GEN = PROJECT_ROOT / "generated_data"
    accounts = pd.read_csv(GEN / "accounts.csv", parse_dates=["created_at"])
    comments = pd.read_csv(GEN / "comments.csv", parse_dates=["posted_at"])
    reports = pd.read_csv(GEN / "reports.csv")

    engine = SignalEngine()
    scored = engine.score_population(accounts, comments, reports)
    print(scored[["account_id", "final_risk"]].describe())
    print("\nExample hypothetical scoring:")
    print(engine.score_hypothetical(
        created_at="2026-05-30", device_id="DEV-0001", ip_region="South-East-Asia",
        toxic_comment_ratio=0.8, report_count=5, population_accounts=accounts,
    ))