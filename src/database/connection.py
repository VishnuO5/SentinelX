"""
SentinelX Enterprise

Database Connection Factory
"""

from __future__ import annotations

from pathlib import Path

from src.database.database_manager import DatabaseManager

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_PATH = PROJECT_ROOT / "database" / "sentinelx.db"

db = DatabaseManager(str(DATABASE_PATH))