"""
tests/conftest.py
====================
Shared pytest fixtures.

Read-only tests run directly against the real database/sentinelx.db --
safe, since they never write.

Write-action tests (assign, status change, add note, moderation
validation) use the `isolated_db` fixture instead: it copies the real
database to a throwaway temp file and redirects the relevant
repositories' `db` singleton at the copy for the duration of the test,
so nothing ever touches your real project data.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REAL_DB = PROJECT_ROOT / "database" / "sentinelx.db"


@pytest.fixture(scope="session", autouse=True)
def _require_real_db():
    assert REAL_DB.exists(), (
        "database/sentinelx.db not found. Run the data generation pipeline "
        "(scripts/generate_*.py + py -m src.database.data_loader) before running tests."
    )


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Redirects moderator_repository, case_repository, and moderation_service
    at a throwaway copy of the real database, so write-tests never mutate
    real project data.

    Each of these three modules does its own `from src.database.connection
    import db`, which binds its own module-level name at import time --
    patching connection.db alone would NOT redirect them, since they
    already hold their own reference. Each one must be patched by name.
    """
    from src.database.database_manager import DatabaseManager

    temp_path = tmp_path / "test_sentinelx.db"
    shutil.copy(REAL_DB, temp_path)

    test_db = DatabaseManager(str(temp_path))

    monkeypatch.setattr("src.repositories.moderator_repository.db", test_db)
    monkeypatch.setattr("src.repositories.case_repository.db", test_db)
    monkeypatch.setattr("src.services.moderation_service.db", test_db)

    return test_db


@pytest.fixture
def sample_accounts_df():
    import pandas as pd
    return pd.read_csv(PROJECT_ROOT / "generated_data" / "accounts.csv", parse_dates=["created_at"])


@pytest.fixture
def sample_comments_df():
    import pandas as pd
    return pd.read_csv(PROJECT_ROOT / "generated_data" / "comments.csv", parse_dates=["posted_at"])


@pytest.fixture
def sample_reports_df():
    import pandas as pd
    return pd.read_csv(PROJECT_ROOT / "generated_data" / "reports.csv")