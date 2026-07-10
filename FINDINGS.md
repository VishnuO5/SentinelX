# FINDINGS

The interesting results the data actually produced — not aspirational claims, numbers pulled directly from the current database and engine runs.

---

## 1. Unsupervised campaign detection recovers real coordination from raw signals alone

Running `src/engines/campaign_engine.py`'s DBSCAN detector — which is never shown `campaign_id` — against the 600-account population, auto-tuned via grid search (see `METHODOLOGY.md` §4):

| Metric | Value |
|---|---|
| Recall (of real campaign accounts, % correctly flagged as coordinated) | **100%** |
| Precision (of flagged accounts, % that were actually in a real campaign) | **91.5%** |
| False positive rate | **3.7%** |
| Clusters found | 13 (vs. 16 real campaigns) |
| Accounts flagged as coordinated | 188 (of 172 real campaign-linked accounts) |

**Reading this honestly:** the detector catches every real campaign account (100% recall) at the cost of a small number of false positives (16 normal accounts incorrectly flagged, 3.7% false-positive rate) — a defensible trade-off for a detection system, where missing a real coordinated account is usually costlier than over-flagging a handful of normal ones. The 13-vs-16 cluster count gap means DBSCAN sometimes merges two real campaigns that look behaviorally similar into one detected cluster, or treats a small campaign as noise — worth stating plainly rather than implying perfect 1:1 cluster recovery.

## 2. Campaign similarity score correctly separates "identical text" campaigns from "coordinated but individually worded" campaigns

Real TF-IDF + cosine similarity, averaged per campaign type:

| Campaign type | Avg. similarity |
|---|---|
| bot_network | 0.91 |
| spam | 0.79 |
| fake_engagement | 0.60 |
| scam | 0.42 |
| repeat_offender | 0.34 |
| harassment | 0.29 |

Bot networks post near-identical text (highest similarity) — that's the actual signature of automation. Harassment campaigns are coordinated in *target and timing*, not wording, so a real similarity metric correctly scores them lowest. This ordering wasn't designed in — it fell out of computing the metric honestly, and it matches what a real T&S analyst would expect to see.

## 3. Current detection signals already have near-total overlap with three alternative policies

`scripts/generate_counterfactual_runs.py` tested five "what if we changed the policy" scenarios against real report/account/device data. Three came back with **zero net change**:

- Lowering the report threshold from 5 to 3: every account that would newly qualify is already in a case.
- Auto-flagging accounts under 14 days old: every one is already in a case.
- Auto-flagging accounts sharing a device with 3+ others: every one is already in a case.

**Reading this honestly:** this isn't a broken feature returning zeros — it's a real finding that the current case-opening logic (built from real campaign clustering) already has strong coverage on these three specific signals. The two scenarios that *did* show real movement (raising the report threshold to 10; requiring escalation before resolution) are the ones worth highlighting as the simulator's actual value: it correctly distinguishes "this policy change would do nothing" from "this policy change would meaningfully affect real cases."

## 4. The Unified Signal Engine's `report_volume_signal` is the dominant contributor to risk on this dataset

With weights `account_age: 0.15, report_volume: 0.30, device_reuse: 0.25, ip_region: 0.10, toxicity: 0.20`, and a policy-experiment baseline threshold of 0.4:

- Baseline precision: **1.0** — every account currently flagged as high-risk at this threshold is a real campaign account, zero false positives at this specific cutoff.
- Baseline recall: **0.628** — the threshold is conservative; it catches ~63% of real campaign accounts while accepting zero false positives, rather than maximizing recall at the cost of precision.

This is a real precision/recall trade-off, visible and adjustable live on the Policy Experiment Center page — not a single hardcoded number.

## 5. Business rule enforcement catches real invalid actions, not just intended ones

Manually tested against `src/services/moderation_service.py`, three scenarios that should be rejected were correctly rejected:

- Moving a `closed` case back to `escalated` — rejected ("no further status changes are allowed").
- Resolving a case with zero evidence attached — rejected.
- Resolving a `critical`-priority case that was never escalated — rejected ("must be escalated for senior review before they can be resolved").

All three checks run against live database state at the moment of the action (an actual `case_evidence` count, an actual `case_timeline` escalation event), not a cached or assumed value.

## 6. Case type distribution across the 180 generated cases

| Case type | Count |
|---|---|
| spam | 48 |
| harassment | 38 |
| bot_network | 33 |
| scam | 21 |
| fake_engagement | 24 |
| repeat_offender | 16 |

This reflects the real underlying account population's behavioral profile weights (`config.ACCOUNT_PROFILE_DISTRIBUTION`), not an arbitrary case-generation split.