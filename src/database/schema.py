"""
src/database/schema.py
======================
Single source of truth for the SentinelX database schema reference.

The actual CREATE TABLE statements live in scripts/init_db.py
(which is the script that builds the .db file). This module provides
Python-level constants for table/column names used by data_loader.py
and dashboard pages, so column names are never typed as raw strings
more than once.

Do NOT add another CREATE TABLE block here — init_db.py owns that.
"""

DB_PATH = "database/sentinelx.db"

# Canonical table names
TABLES = [
    "campaigns",
    "moderators",
    "accounts",
    "comments",
    "reports",
    "cases",
    "case_evidence",
    "case_notes",
    "case_timeline",
    "signal_scores",
    "playbooks",
    "policy_experiments",
    "counterfactual_runs",
    "audit_log",
]

# Key columns referenced across dashboard pages
ACCOUNT_COLS  = ["account_id","created_at","device_id","ip_region",
                 "display_name","status","risk_score","campaign_id"]
CASE_COLS     = ["case_id","campaign_id","account_id","case_type",
                 "priority","status","opened_at","resolved_at",
                 "assigned_moderator_id"]
CAMPAIGN_COLS = ["campaign_id","campaign_type","first_detected_at",
                 "velocity_score","similarity_score","network_density","status"]
SIGNAL_COLS   = ["signal_id","account_id","computed_at",
                 "account_age_signal","report_volume_signal",
                 "device_reuse_signal","ip_region_signal",
                 "toxicity_signal","composite_risk_score"]
# FIX (issue #14): this said "final_risk", which was only ever the DB
# column name because data_loader.py used to rebuild the table around
# whatever generate_signal_scores.py's CSV called it. The approved schema
# (scripts/init_db.py) calls this column "composite_risk_score", and
# data_loader.py now renames it on load to match -- this reference list
# was left stale and pointing at the old name.