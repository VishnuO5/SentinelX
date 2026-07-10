# METHODOLOGY

How every non-trivial number in SentinelX is actually computed. If a reviewer or interviewer asks "how did you get this," this document has the answer — nothing here is a placeholder.

---

## 1. Dataset construction

**Real component:** comment text and toxicity labels come from the [Jigsaw Toxic Comment Classification Challenge](https://www.kaggle.com/c/jigsaw-toxic-comment-classification-challenge) — 159,571 real Wikipedia talk-page comments, each labeled across six categories (`toxic`, `severe_toxic`, `obscene`, `threat`, `insult`, `identity_hate`).

**Synthetic component:** account metadata, campaign structure, reports, cases, and moderator assignments. These are generated, but not independently at random — `scripts/generate_behaviour.py` is the single source of truth: it assigns each of the 600 accounts a behavioral profile (`normal`, `spam`, `bot_network`, `harassment`, `scam`, `fake_engagement`, `repeat_offender`) with a weighted distribution (72% normal), and abusive profiles are grouped into explicit clusters — a cluster shares a small pool of `device_id`s and a dominant `ip_region`, exactly like a real coordinated abuse ring would. Every downstream generator (accounts, comments, reports, campaigns, cases, signals) reads from this file rather than re-rolling independent randomness, so an account's comment history, report volume, campaign linkage, and signal scores are all internally consistent with its actual behavioral profile.

## 2. Campaign similarity score (Abuse Genome)

`scripts/compute_campaign_similarity.py` computes **real TF-IDF vectorization + cosine similarity** over each campaign's actual member comment text (`sklearn.feature_extraction.text.TfidfVectorizer`, `sklearn.metrics.pairwise.cosine_similarity`), then averages the upper-triangle of the pairwise similarity matrix per campaign. This is not a random number assigned at generation time — it only exists after real comment text is generated and assigned to real campaign members.

Current results by campaign type (averaged across campaigns of that type):

| Campaign type | Avg. similarity |
|---|---|
| bot_network | 0.91 |
| spam | 0.79 |
| fake_engagement | 0.60 |
| scam | 0.42 |
| repeat_offender | 0.34 |
| harassment | 0.29 |

This ordering is itself a real finding, not a tuning artifact: bot networks and spam campaigns post near-identical text by nature (that's what makes them detectable), while harassment campaigns are coordinated in target and timing but not in wording — so a lower similarity score for harassment is the *correct* behavior of a real similarity metric, not a bug.

## 3. Unified Signal Engine

`src/engines/signal_engine.py` is the actual reusable engine (previously this logic only existed inline in a one-off batch script — see the file's docstring for why that mattered). Five signals, each normalized to `[0, 1]`:

- **`account_age_signal`** — `1 - (age_days / max_age_days)`. Newer accounts score higher.
- **`report_volume_signal`** — this account's real report count ÷ the busiest account's report count.
- **`device_reuse_signal`** — how many *other* real accounts share this exact `device_id`, ÷ the max across the population.
- **`ip_region_signal`** — for campaign-linked accounts, how many other accounts in the *same campaign* share this IP region; for standalone accounts, a discounted global IP-region count (÷10) so it doesn't compete on the same scale as genuine campaign clustering.
- **`toxicity_signal`** — fraction of this account's own real comments labeled `toxic` or `severe_toxic`.

**Composite:** a weighted sum, with weights defined once in `config.SIGNAL_WEIGHTS` (account_age 0.15, report_volume 0.30, device_reuse 0.25, ip_region 0.10, toxicity 0.20) and imported by the generator — not duplicated, so the weights displayed on the Signal Engine page can never drift from the weights that actually computed the scores in the database.

The engine also exposes `score_live_account()` (re-scores any existing account on demand, queried live from the database) and `score_hypothetical()` (scores a new/hypothetical account that doesn't exist yet), so the same formulas back both the batch pipeline and any live "what if" feature.

## 4. Unsupervised campaign detection (Abuse Genome, validation)

`src/engines/campaign_engine.py` is a genuinely separate exercise from the Signal Engine: instead of scoring accounts against a known campaign label, it tries to **rediscover coordinated clusters from scratch**, using only behavioral features (age, device-sharing, comment toxicity) and DBSCAN (`sklearn.cluster.DBSCAN`) — `campaign_id` is never given to it.

One feature was deliberately excluded after testing: a raw IP-region peer count. With only 10 possible IP regions spread across 600 accounts, every account has roughly 50–80 "IP peers" regardless of coordination — that's scale noise, not signal, and it was swamping the real device-sharing signal when standardized.

The engine auto-tunes its own `eps`/`min_samples` via a grid search (`CampaignEngine.tune()`): it evaluates every combination, keeps only the ones with a false-positive rate at or below 15%, and picks the one with the highest recall among those. This means the parameters aren't hand-picked to make the numbers look good — they're the output of an explicit, inspectable selection rule.

The detector's clusters are then compared against the real `campaign_id` labels (which it never saw), reporting precision, recall, and false-positive rate against that ground truth. See `FINDINGS.md` for the current numbers — this comparison is what makes "my algorithm recovers coordinated campaigns from raw signals alone" a claim backed by a number, not a slogan.

## 5. Policy Experiment Center

`scripts/generate_policy_experiments.py` computes real precision/recall/F1 by treating `campaign_id IS NOT NULL` as the ground-truth positive class (an account confirmed to belong to a real behavioral cluster) and sweeping the `composite_risk_score` threshold used to flag an account as high-risk. The page also exposes a live version (`src/repositories/policy_experiment_repository.py`) so an analyst can test any threshold on demand, not just the pre-generated scenarios — both paths run the identical query logic.

## 6. Counterfactual Simulator

`scripts/generate_counterfactual_runs.py` computes, for each hypothetical policy change (e.g. "lower the report threshold from 5 to 3"), the real count of accounts that would be newly flagged or newly missed, using actual `reports`, `accounts`, and `case_timeline` data — not an invented number. Three of the five scenarios currently show zero net change; that's a real result (see `FINDINGS.md`), not an empty feature.

## 7. Moderator Workspace business rules

`src/services/moderation_service.py` enforces transition rules the raw repository does not: a `closed` case has no valid next state, and a `critical`-priority case must have a real `escalated` event in its `case_timeline` before it can be marked `resolved`. Both rules are checked against live database state at the moment of the action, not against a static table.