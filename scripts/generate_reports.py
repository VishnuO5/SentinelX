"""
SentinelX - Generate Reports

FIX vs. previous version: report volume per comment is now driven by the
owning account's real report_probability (from behaviour.csv) combined
with the comment's actual toxicity_score, instead of a flat random sample
of NUM_REPORTS comments. report_reason is now drawn from a distribution
appropriate to the account's actual abuse type instead of a dead
"spam" in labels check that could never fire (toxicity_label never
contains the literal string "spam").
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

comments = pd.read_csv(config.GENERATED_DIR / "comments.csv")
behaviour = pd.read_csv(config.GENERATED_DIR / "behaviour.csv")
report_prob_by_account = behaviour.set_index("account_id")["report_probability"].to_dict()
profile_by_account = behaviour.set_index("account_id")["profile"].to_dict()

records = []
report_seq = 1

for _, c in comments.iterrows():
    account_id = c["account_id"]
    p_report = report_prob_by_account.get(account_id, 0.05)
    toxicity_score = float(c["toxicity_score"])
    profile = profile_by_account.get(account_id, "normal")

    # expected number of reports scales with both the account's report
    # likelihood and how toxic this specific comment is
    lam = p_report * (0.5 + 2.5 * toxicity_score)
    n_reports = np.random.poisson(lam=lam)
    n_reports = min(n_reports, 6)

    if n_reports == 0:
        continue

    posted_at = pd.to_datetime(c["posted_at"])
    reasons = config.REPORT_REASON_BY_ABUSE_TYPE.get(profile, config.REPORT_REASON_BY_ABUSE_TYPE["normal"])

    for _ in range(n_reports):
        reported_at = posted_at + pd.Timedelta(hours=random.uniform(0.5, 96))
        records.append({
            "report_id": f"REP-{report_seq:06d}",
            "comment_id": c["comment_id"],
            "account_id": account_id,
            "report_reason": random.choice(reasons),
            "reported_at": reported_at.strftime(config.DATE_FORMAT),
            "reporter_type": random.choices(config.REPORTER_TYPES, weights=[0.5, 0.35, 0.15])[0],
        })
        report_seq += 1

reports = pd.DataFrame(records)

output_file = config.GENERATED_DIR / "reports.csv"
reports.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(reports.head())
    print(f"\nTotal Reports: {len(reports)}")
    print(f"Saved to: {output_file}")