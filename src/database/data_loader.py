"""
src/database/data_loader.py
===========================
Loads all generated CSV files into sentinelx.db.

FIX vs. previous version: this used to call
    df.to_sql(table, conn, if_exists="replace")
which silently DROPPED every PRIMARY KEY / FOREIGN KEY / NOT NULL
constraint from the approved schema (scripts/init_db.py) and replaced
each table with a pandas-inferred, constraint-free version.

Now this script:
  1. Runs scripts/init_db.py's real schema first, so every table exists
     with its actual PK/FK/NOT NULL constraints intact.
  2. Inserts each CSV's rows via an explicit, named-column INSERT
     (executemany), so column order/naming drift between a CSV and the
     schema fails loudly instead of silently redefining the table.
  3. Maps known column-name drift explicitly (see COLUMN_RENAMES below)
     instead of letting it happen by accident.

Load order respects FK constraints — parent tables first.
Only loads CSVs that actually exist in generated_data/.

Orphaned / helper CSVs that are NOT loaded into the DB:
  - behaviour.csv            (used only during generation, not needed at runtime)
  - campaigns_detected.csv   (intermediate output, superseded by campaigns.csv)
  - cluster_campaign_map.csv (generation helper only)
  - investigations.csv       (superseded by cases.csv + signal_scores.csv)

Run this after:
  py scripts/generate_behaviour.py
  py scripts/generate_campaigns.py
  py scripts/generate_accounts.py
  py scripts/generate_comments.py
  py scripts/compute_campaign_similarity.py
  py scripts/generate_reports.py
  py scripts/generate_cases.py
  py scripts/generate_moderators.py
  py scripts/generate_signal_scores.py
  py scripts/generate_case_timeline.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATABASE = PROJECT_ROOT / "database" / "sentinelx.db"
GEN = PROJECT_ROOT / "generated_data"

# Import the single source of truth for the schema (scripts/init_db.py)
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import init_db  # noqa: E402  (scripts/init_db.py)


# ── Load order must respect FK dependencies ────────────────────────────────
# Only CSVs that actually exist and are needed at runtime.
LOAD_ORDER = [
    ("campaigns.csv", "campaigns"),
    ("moderators.csv", "moderators"),
    ("accounts.csv", "accounts"),
    ("comments.csv", "comments"),
    ("reports.csv", "reports"),
    ("cases.csv", "cases"),
    ("signal_scores.csv", "signal_scores"),
    ("case_timeline.csv", "case_timeline"),
    ("case_evidence.csv", "case_evidence"),
    ("playbooks.csv", "playbooks"),
    ("policy_experiments.csv", "policy_experiments"),
    ("counterfactual_runs.csv", "counterfactual_runs"),
]

# FIX: explicit, visible mapping for any CSV column whose name doesn't
# match the approved schema's column name. generate_signal_scores.py
# writes "final_risk"; the approved schema (init_db.py) calls that column
# "composite_risk_score". Previously this drift was silently absorbed by
# to_sql(if_exists="replace") redefining the table around whatever the
# CSV happened to contain. Now it's a one-line, documented rename instead
# of an accident.
COLUMN_RENAMES = {
    "signal_scores": {
        "final_risk": "composite_risk_score",
    },
}


def get_table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cursor = conn.execute(f"PRAGMA table_info({table});")
    return [row[1] for row in cursor.fetchall()]


def load_table(conn: sqlite3.Connection, csv_name: str, table: str) -> int:
    path = GEN / csv_name
    if not path.exists():
        print(f"  SKIP  {table:<22} ({csv_name} not found)")
        return 0

    df = pd.read_csv(path)

    renames = COLUMN_RENAMES.get(table, {})
    if renames:
        df = df.rename(columns=renames)

    schema_columns = get_table_columns(conn, table)
    csv_columns = list(df.columns)

    missing_in_csv = [c for c in schema_columns if c not in csv_columns]
    extra_in_csv = [c for c in csv_columns if c not in schema_columns]

    if missing_in_csv:
        raise ValueError(
            f"{table}: CSV '{csv_name}' is missing column(s) required by the "
            f"schema: {missing_in_csv}. Refusing to load — fix the generator "
            f"script or add a rename in COLUMN_RENAMES."
        )
    if extra_in_csv:
        print(
            f"  NOTE  {table:<22} CSV has extra column(s) not in schema, "
            f"ignoring: {extra_in_csv}"
        )

    # Insert only the columns the schema actually has, in schema order,
    # via a plain parameterized executemany -- this respects whatever
    # PRIMARY KEY / FOREIGN KEY / NOT NULL constraints init_db.py defined,
    # instead of pandas silently redefining the table around the CSV.
    df = df[schema_columns].where(pd.notna(df[schema_columns]), None)
    placeholders = ", ".join("?" for _ in schema_columns)
    col_list = ", ".join(schema_columns)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    conn.executemany(sql, df.itertuples(index=False, name=None))
    print(f"  OK    {table:<22} {len(df):>6} rows")
    return len(df)


def load_all() -> None:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 55)
    print("  SentinelX — Data Loader")
    print("=" * 55)

    # Step 1: (re)create the real, constrained schema. This is the fix for
    # constraints being silently dropped -- every table now exists with its
    # actual PRIMARY KEY / FOREIGN KEY / NOT NULL clauses before any row is
    # inserted.
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    init_db.create_schema(conn)
    init_db.verify_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON;")

    total = 0
    for csv_name, table in LOAD_ORDER:
        total += load_table(conn, csv_name, table)

    conn.commit()
    conn.close()

    print("=" * 55)
    print(f"  Done — {total:,} rows loaded across {len(LOAD_ORDER)} tables")
    print("=" * 55)
    print()
    print("  Database ready at:", DATABASE)


if __name__ == "__main__":
    load_all()