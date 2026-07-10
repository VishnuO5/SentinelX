"""
scripts/generate_playbooks.py
================================
Populates playbooks.csv -- static reference data (not per-case). One
checklist per abuse type in config.PLAYBOOK_TYPES, so every campaign_type
/ case_type in the unified taxonomy has a matching investigation
playbook. Keeps the schema's playbooks table in the loop rather than
being a hardcoded dict living only in a page.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import config

PLAYBOOK_STEPS = {
    "spam": [
        ("Check for duplicate or near-duplicate accounts sharing this device_id.", True),
        ("Review posting velocity -- how many comments in the last 24-72 hours?", True),
        ("Check report volume and reason distribution for this account.", True),
        ("Check whether the account is linked to a known campaign cluster.", False),
        ("Escalate if network_density on the linked campaign exceeds 0.6.", False),
    ],
    "bot_network": [
        ("Check account creation date -- bot accounts typically cluster within days.", True),
        ("Check device_id and ip_region overlap with other accounts in the cluster.", True),
        ("Review posting cadence for non-human timing patterns.", True),
        ("Cross-reference campaign velocity_score against historical bot campaigns.", False),
        ("Escalate for platform-wide device block if network_density > 0.7.", False),
    ],
    "harassment": [
        ("Read the reported content in full context, not just the flagged excerpt.", True),
        ("Check the target account's report history for a pattern.", True),
        ("Check whether this account has prior harassment cases (repeat behavior).", True),
        ("Determine if multiple reporters are flagging the same target (coordination signal).", False),
        ("Escalate immediately if the content contains threat-level language.", False),
    ],
    "scam": [
        ("Extract and review any linked URLs from the account's comments.", True),
        ("Check account age vs. posting behavior -- scam accounts are usually new.", True),
        ("Check report_reason distribution for 'scam' or 'impersonation' concentration.", True),
        ("Check for shared device/IP with other scam-flagged accounts.", False),
        ("Escalate for platform-wide link block if the same domain repeats across accounts.", False),
    ],
    "fake_engagement": [
        ("Compare this account's engagement velocity to the campaign's average.", True),
        ("Check device_reuse_signal -- fake engagement clusters usually share devices.", True),
        ("Spot-check a sample of comments for authenticity vs. templated text.", True),
        ("Check campaign similarity_score -- high text similarity supports coordination.", False),
        ("Escalate if velocity_score is sustained (not a single burst).", False),
    ],
    "repeat_offender": [
        ("Pull the account's full prior case history.", True),
        ("Check whether prior violations follow a consistent pattern or escalate in severity.", True),
        ("Review whether the previous resolution actually held (no relapse).", True),
        ("Check current composite_risk_score against the score at last resolution.", False),
        ("Escalate to permanent-action review if this is the 3rd or later offense.", False),
    ],
}

records = []
idx = 1

for case_type in config.PLAYBOOK_TYPES:
    steps = PLAYBOOK_STEPS.get(case_type)
    if steps is None:
        continue
    for step_order, (description, is_checklist) in enumerate(steps, start=1):
        records.append({
            "playbook_id": f"PB-{idx:04d}",
            "case_type": case_type,
            "step_order": step_order,
            "step_description": description,
            "checklist_item": int(is_checklist),
        })
        idx += 1

playbooks = pd.DataFrame(records)
output_file = config.GENERATED_DIR / "playbooks.csv"
playbooks.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(playbooks.to_string(index=False))
    print(f"\nTotal Playbook Steps: {len(playbooks)}")
    print(f"Case types covered: {playbooks['case_type'].nunique()} / {len(config.PLAYBOOK_TYPES)}")
    print(f"Saved to: {output_file}")