"""
SentinelX Configuration
-----------------------

Central configuration for the SentinelX platform.

All project-wide constants should live here.
Every generator, module, and utility imports this file.

Author: Vishnu Prasath
Project: SentinelX
"""

from pathlib import Path
from datetime import datetime

# =============================================================================
# PROJECT PATHS
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "data"
DATABASE_DIR = PROJECT_ROOT / "database"
SCRIPT_DIR = PROJECT_ROOT / "scripts"
ASSETS_DIR = PROJECT_ROOT / "assets"
GENERATED_DIR = PROJECT_ROOT / "generated_data"

DATABASE_PATH = DATABASE_DIR / "sentinelx.db"
JIGSAW_DATASET = DATA_DIR / "train.csv"

# =============================================================================
# RANDOMNESS
# =============================================================================

# Keeping a fixed seed ensures reproducible synthetic datasets.
RANDOM_SEED = 42

# FIX (was datetime.now()): a fixed anchor means every re-run produces
# byte-identical dates given the same seed. datetime.now() silently broke
# reproducibility on every re-run despite the fixed seed.
CURRENT_TIME = datetime(2026, 6, 1, 0, 0, 0)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# =============================================================================
# DATASET SIZE
# =============================================================================

NUM_ACCOUNTS = 600
NUM_COMMENTS = 3000

# NOTE: campaigns are NOT generated directly from this number. They emerge
# from the clustering logic in generate_behaviour.py (one campaign per
# cluster that forms). This is a target/expected order of magnitude, not
# an enforced count -- the real number currently produced is 16. If you
# need the count to match exactly, tune the clustering parameters in
# generate_behaviour.py, not this constant.
NUM_CAMPAIGNS = 15

NUM_MODERATORS = 8

NUM_POLICY_EXPERIMENTS = 6
NUM_COUNTERFACTUAL_RUNS = 5

# Individual (non-campaign) cases opened against high-risk standalone accounts
NUM_STANDALONE_CASES = 40

# =============================================================================
# RISK SCORING
# =============================================================================

# FIX: this used to be hardcoded as 0.7 directly inside a SQL query in
# mission_control_repository.py. Under the real (non-random) Unified Signal
# Engine formula, composite_risk_score currently ranges ~0.04-0.66, so
# nothing ever crossed 0.7 and the "High Risk Accounts" KPI silently showed
# zero. 0.4 is chosen because it sits just above the organic-account ceiling
# (~0.36) and inside the campaign-account range (~0.35-0.66), so it actually
# separates coordinated-campaign accounts from normal ones. Revisit this
# number once more campaigns/accounts are generated -- it's a judgment call,
# not a derived statistic.
HIGH_RISK_THRESHOLD = 0.4

# =============================================================================
# UNIFIED ABUSE TAXONOMY
# FIX: previously CASE_TYPES, CAMPAIGN_TYPES, and account "profiles" used
# three different, misaligned vocabularies (e.g. "spam" vs "coordinated_spam"
# vs "scam_links"). One list now drives account behavioral profiles,
# campaign types, case types, and playbook categories, so every module
# in the schema can join on the same value.
# =============================================================================

# "normal" is the only non-abusive profile; the rest map 1:1 onto
# campaign_type / case_type / playbook case_type everywhere in the schema.
ACCOUNT_PROFILES = [
    "normal", "spam", "bot_network", "harassment",
    "scam", "fake_engagement", "repeat_offender",
]

ABUSE_TYPES = [t for t in ACCOUNT_PROFILES if t != "normal"]

CAMPAIGN_TYPES = ABUSE_TYPES
CASE_TYPES = ABUSE_TYPES
PLAYBOOK_TYPES = ABUSE_TYPES

ACCOUNT_PROFILE_DISTRIBUTION = {
    "normal": 0.72,
    "spam": 0.08,
    "bot_network": 0.05,
    "harassment": 0.05,
    "scam": 0.04,
    "fake_engagement": 0.04,
    "repeat_offender": 0.02,
}

# =============================================================================
# ACCOUNT STATUS DISTRIBUTION
# =============================================================================

ACCOUNT_STATUS_DISTRIBUTION = {
    "active": 0.82,
    "under_review": 0.08,
    "suspended": 0.07,
    "banned": 0.03,
}

# =============================================================================
# REGIONS
# Synthetic geographical regions only.
# =============================================================================

IP_REGIONS = [
    "India-North", "India-South", "India-East", "India-West",
    "US-East", "US-West", "Europe-West", "Europe-Central",
    "South-East-Asia", "Middle-East",
]

# =============================================================================
# BEHAVIOURAL PROFILE RULES
# Drives comment volume, toxicity, report likelihood, and how tightly an
# abusive cluster shares devices. This is the single source of truth
# consumed by every downstream generator (accounts, comments, reports,
# campaigns, signals, cases).
# =============================================================================

PROFILE_RULES = {
    "normal": {
        "comments": (1, 8), "toxicity_prob": (0.00, 0.15),
        "report_prob": (0.00, 0.03), "account_age_days": (180, 1825),
        "cluster": False,
    },
    "spam": {
        "comments": (15, 45), "toxicity_prob": (0.35, 0.65),
        "report_prob": (0.35, 0.70), "account_age_days": (1, 60),
        "cluster": True,
    },
    "bot_network": {
        "comments": (20, 60), "toxicity_prob": (0.55, 0.90),
        "report_prob": (0.60, 0.95), "account_age_days": (0, 10),
        "cluster": True,
    },
    "harassment": {
        "comments": (10, 35), "toxicity_prob": (0.60, 0.95),
        "report_prob": (0.50, 0.90), "account_age_days": (30, 1095),
        "cluster": True,
    },
    "scam": {
        "comments": (12, 40), "toxicity_prob": (0.40, 0.75),
        "report_prob": (0.50, 0.95), "account_age_days": (0, 20),
        "cluster": True,
    },
    "fake_engagement": {
        "comments": (10, 30), "toxicity_prob": (0.10, 0.35),
        "report_prob": (0.15, 0.45), "account_age_days": (0, 30),
        "cluster": True,
    },
    "repeat_offender": {
        "comments": (18, 50), "toxicity_prob": (0.50, 0.85),
        "report_prob": (0.55, 0.90), "account_age_days": (365, 2190),
        "cluster": True,
    },
}

# =============================================================================
# REPORT REASONS
# =============================================================================

REPORT_REASON_BY_ABUSE_TYPE = {
    "spam": ["spam", "misinformation"],
    "bot_network": ["spam", "fake_engagement"],
    "harassment": ["harassment", "hate_speech"],
    "scam": ["scam", "impersonation"],
    "fake_engagement": ["fake_engagement", "spam"],
    "repeat_offender": ["harassment", "spam", "hate_speech"],
    "normal": ["spam", "misinformation", "harassment"],
}

REPORTER_TYPES = ["user", "automated_system", "trusted_flagger"]

# =============================================================================
# MODERATOR ROLES
# =============================================================================

MODERATOR_ROLES = ["analyst", "senior_analyst", "lead"]

# =============================================================================
# SIGNAL SCORE WEIGHTS
# Used by the Unified Signal Engine. Must sum to 1.0.
# =============================================================================

SIGNAL_WEIGHTS = {
    "account_age": 0.15,
    "report_volume": 0.30,
    "device_reuse": 0.25,
    "ip_region": 0.10,
    "toxicity": 0.20,
}

assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9, "SIGNAL_WEIGHTS must sum to 1.0"

# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"