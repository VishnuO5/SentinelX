"""
init_db.py
SentinelX -- Database initialization script.

Creates the SQLite database at database/sentinelx.db with all 14 tables
from the approved schema (Draft v1). This script only creates structure --
no data is inserted here. That happens in generate_dataset.py.

Usage:
    py scripts/init_db.py

Safe to re-run: existing tables are dropped and recreated, so you can
run this again if the schema changes or the db gets into a bad state.
"""

import sqlite3
import os
import logging

# ---------------------------------------------------------------------------
# Config (named constants, no magic strings -- mirrors PraxisIQ pattern)
# ---------------------------------------------------------------------------

DB_DIR = "database"
DB_FILENAME = "sentinelx.db"
DB_PATH = os.path.join(DB_DIR, DB_FILENAME)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_LEVEL = logging.INFO

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger("init_db")


# ---------------------------------------------------------------------------
# Schema -- one CREATE TABLE statement per approved table.
# Order matters: tables referenced by foreign keys are created first.
# ---------------------------------------------------------------------------

SCHEMA_STATEMENTS = [
    # 1. campaigns (created before accounts/cases since both FK into it)
    """
    CREATE TABLE campaigns (
        campaign_id         TEXT PRIMARY KEY,
        campaign_type        TEXT NOT NULL,
        first_detected_at    DATETIME NOT NULL,
        velocity_score        REAL,
        similarity_score      REAL,
        network_density        REAL,
        status                TEXT NOT NULL
    );
    """,

    # 2. moderators (created before cases/case_notes/etc. since they FK into it)
    """
    CREATE TABLE moderators (
        moderator_id        TEXT PRIMARY KEY,
        name                  TEXT NOT NULL,
        role                  TEXT NOT NULL,
        active_case_count    INTEGER DEFAULT 0
    );
    """,

    # 3. accounts
    """
    CREATE TABLE accounts (
        account_id      TEXT PRIMARY KEY,
        created_at        DATETIME NOT NULL,
        device_id         TEXT,
        ip_region         TEXT,
        display_name      TEXT,
        status            TEXT NOT NULL,
        risk_score        REAL,
        campaign_id       TEXT,
        FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
    );
    """,

    # 4. comments
    """
    CREATE TABLE comments (
        comment_id        TEXT PRIMARY KEY,
        account_id          TEXT NOT NULL,
        text                TEXT NOT NULL,
        toxicity_label      TEXT,
        toxicity_score      REAL,
        posted_at           DATETIME NOT NULL,
        platform_surface    TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(account_id)
    );
    """,

    # 5. reports
    """
    CREATE TABLE reports (
        report_id       TEXT PRIMARY KEY,
        comment_id        TEXT,
        account_id        TEXT NOT NULL,
        report_reason     TEXT NOT NULL,
        reported_at       DATETIME NOT NULL,
        reporter_type     TEXT NOT NULL,
        FOREIGN KEY (comment_id) REFERENCES comments(comment_id),
        FOREIGN KEY (account_id) REFERENCES accounts(account_id)
    );
    """,

    # 6. cases
    """
    CREATE TABLE cases (
        case_id                TEXT PRIMARY KEY,
        campaign_id              TEXT,
        account_id                TEXT NOT NULL,
        case_type                TEXT NOT NULL,
        priority                  TEXT NOT NULL,
        status                    TEXT NOT NULL,
        opened_at                 DATETIME NOT NULL,
        resolved_at               DATETIME,
        assigned_moderator_id     TEXT,
        FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id),
        FOREIGN KEY (account_id) REFERENCES accounts(account_id),
        FOREIGN KEY (assigned_moderator_id) REFERENCES moderators(moderator_id)
    );
    """,

    # 7. case_evidence
    """
    CREATE TABLE case_evidence (
        evidence_id       TEXT PRIMARY KEY,
        case_id             TEXT NOT NULL,
        evidence_type       TEXT NOT NULL,
        reference_id        TEXT NOT NULL,
        added_at            DATETIME NOT NULL,
        added_by            TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(case_id),
        FOREIGN KEY (added_by) REFERENCES moderators(moderator_id)
    );
    """,

    # 8. case_notes
    """
    CREATE TABLE case_notes (
        note_id          TEXT PRIMARY KEY,
        case_id            TEXT NOT NULL,
        moderator_id       TEXT NOT NULL,
        note_text          TEXT NOT NULL,
        created_at         DATETIME NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(case_id),
        FOREIGN KEY (moderator_id) REFERENCES moderators(moderator_id)
    );
    """,

    # 9. case_timeline
    """
    CREATE TABLE case_timeline (
        event_id            TEXT PRIMARY KEY,
        case_id                TEXT NOT NULL,
        event_type             TEXT NOT NULL,
        event_timestamp        DATETIME NOT NULL,
        event_description      TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(case_id)
    );
    """,

    # 10. signal_scores
    """
    CREATE TABLE signal_scores (
        signal_id                TEXT PRIMARY KEY,
        account_id                  TEXT NOT NULL,
        computed_at                 DATETIME NOT NULL,
        account_age_signal          REAL,
        report_volume_signal        REAL,
        device_reuse_signal         REAL,
        ip_region_signal            REAL,
        toxicity_signal             REAL,
        composite_risk_score        REAL,
        FOREIGN KEY (account_id) REFERENCES accounts(account_id)
    );
    """,

    # 11. playbooks
    """
    CREATE TABLE playbooks (
        playbook_id        TEXT PRIMARY KEY,
        case_type             TEXT NOT NULL,
        step_order            INTEGER NOT NULL,
        step_description      TEXT NOT NULL,
        checklist_item        BOOLEAN DEFAULT 0
    );
    """,

    # 12. policy_experiments
    """
    CREATE TABLE policy_experiments (
        experiment_id           TEXT PRIMARY KEY,
        experiment_name           TEXT NOT NULL,
        parameter_changed         TEXT NOT NULL,
        baseline_value             REAL,
        tested_value               REAL,
        baseline_precision         REAL,
        baseline_recall            REAL,
        tested_precision           REAL,
        tested_recall              REAL,
        false_positive_delta       REAL,
        run_at                     DATETIME NOT NULL
    );
    """,

    # 13. counterfactual_runs
    """
    CREATE TABLE counterfactual_runs (
        run_id                       TEXT PRIMARY KEY,
        policy_description             TEXT NOT NULL,
        cases_affected_count           INTEGER,
        cases_would_have_flagged       INTEGER,
        cases_would_have_missed        INTEGER,
        run_at                         DATETIME NOT NULL
    );
    """,

    # 14. audit_log
    """
    CREATE TABLE audit_log (
        log_id           TEXT PRIMARY KEY,
        case_id            TEXT NOT NULL,
        moderator_id        TEXT,
        action              TEXT NOT NULL,
        timestamp           DATETIME NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(case_id),
        FOREIGN KEY (moderator_id) REFERENCES moderators(moderator_id)
    );
    """,
]

# Table names in creation order -- used for the summary log at the end.
TABLE_NAMES = [
    "campaigns", "moderators", "accounts", "comments", "reports",
    "cases", "case_evidence", "case_notes", "case_timeline",
    "signal_scores", "playbooks", "policy_experiments",
    "counterfactual_runs", "audit_log",
]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def ensure_db_dir():
    """Create the database/ directory if it doesn't exist yet."""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        logger.info(f"Created directory: {DB_DIR}")


def create_schema(conn: sqlite3.Connection):
    """Drop and recreate all 14 tables, in FK-safe order."""
    cursor = conn.cursor()

    # Enable foreign key enforcement (off by default in SQLite)
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Drop in reverse order so FK dependents go before their parents
    for table_name in reversed(TABLE_NAMES):
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
    logger.info("Dropped existing tables (if any).")

    # Create in forward order (parents before children)
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)
    conn.commit()
    logger.info(f"Created {len(SCHEMA_STATEMENTS)} tables.")


def verify_schema(conn: sqlite3.Connection):
    """Sanity check: confirm all 14 expected tables now exist."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    existing = {row[0] for row in cursor.fetchall()}

    missing = [t for t in TABLE_NAMES if t not in existing]
    if missing:
        logger.error(f"Missing tables after creation: {missing}")
        raise RuntimeError(f"Schema creation incomplete. Missing: {missing}")

    logger.info(f"Verified all {len(TABLE_NAMES)} tables exist:")
    for t in TABLE_NAMES:
        logger.info(f"  - {t}")


def main():
    logger.info("SentinelX database initialization starting...")
    ensure_db_dir()

    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        verify_schema(conn)
    finally:
        conn.close()

    logger.info(f"Done. Database created at: {os.path.abspath(DB_PATH)}")
    logger.info("Next step: scripts/generate_dataset.py will populate these tables.")


if __name__ == "__main__":
    main()
