"""
scripts/generate_moderators.py

SentinelX - Generate Moderators

Creates the moderator roster referenced by cases.assigned_moderator_id.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import config

random.seed(config.RANDOM_SEED)

FIRST_NAMES = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ishita", "Vikram", "Sanya"]
LAST_NAMES  = ["Sharma", "Nair", "Reddy", "Iyer", "Kapoor", "Menon", "Rao", "Verma"]

# Fixed role distribution — 1 lead, 2 senior, 5 analyst = 8 total
ROLE_PLAN = ["lead"] + ["senior_analyst"] * 2 + ["analyst"] * 5

cases = pd.read_csv(config.GENERATED_DIR / "cases.csv")
open_counts = (
    cases[cases["status"].isin(["open", "in_progress", "escalated"])]
    .groupby("assigned_moderator_id")
    .size()
)

records = []
for i, role in enumerate(ROLE_PLAN, start=1):
    moderator_id = f"MOD-{i:03d}"
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    records.append({
        "moderator_id": moderator_id,
        "name": name,
        "role": role,
        "active_case_count": int(open_counts.get(moderator_id, 0)),
    })

moderators = pd.DataFrame(records)

output_file = config.GENERATED_DIR / "moderators.csv"
moderators.to_csv(output_file, index=False)

if __name__ == "__main__":
    print(moderators)
    print(f"\nSaved to: {output_file}")