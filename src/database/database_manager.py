"""
Sentinelx Enterprise
Database Manager

Central SQLite database manager used throughout the application.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable, Optional


class DatabaseManager:
    """
    Central database access layer.

    All repositories communicate with SQLite only through this class.

    FIX: this used to cache a single sqlite3.Connection on self.connection
    and reuse it for the lifetime of the process. That breaks under
    Streamlit, which reruns the page script on a new thread on every widget
    interaction (typing in search, clicking a button) -- sqlite3 connections
    are thread-affine, so the second thread's use of the cached connection
    raised "SQLite objects created in a thread can only be used in that
    same thread."

    Fix: keep one connection PER THREAD (via threading.local()) instead of
    one connection for the whole process. Each thread lazily opens its own
    connection the first time it needs one, and reuses that same one on
    later calls from that same thread -- so there's no cross-thread reuse,
    and no reliance on a single shared connection surviving Streamlit's
    module-caching/rerun behavior.
    """

    def __init__(self, database_path: str):

        self.database_path = Path(database_path)

        self._local = threading.local()

    def connect(self) -> sqlite3.Connection:

        connection = getattr(self._local, "connection", None)

        if connection is None:

            connection = sqlite3.connect(self.database_path)

            connection.row_factory = sqlite3.Row

            self._local.connection = connection

        return connection

    def close(self):

        connection = getattr(self._local, "connection", None)

        if connection:

            connection.close()

            self._local.connection = None

    def execute(
        self,
        query: str,
        parameters: Iterable[Any] = (),
    ):

        connection = self.connect()

        cursor = connection.cursor()

        cursor.execute(query, tuple(parameters))

        connection.commit()

        return cursor

    def executemany(
        self,
        query: str,
        parameters: Iterable[Iterable[Any]],
    ):

        connection = self.connect()

        cursor = connection.cursor()

        cursor.executemany(query, parameters)

        connection.commit()

        return cursor

    def fetch_one(
        self,
        query: str,
        parameters: Iterable[Any] = (),
    ):

        cursor = self.execute(query, parameters)

        return cursor.fetchone()

    def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] = (),
    ):

        cursor = self.execute(query, parameters)

        return cursor.fetchall()

    def table_exists(self, table_name: str) -> bool:

        result = self.fetch_one(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name=?
            """,
            (table_name,),
        )

        return result is not None

    def begin(self):

        self.connect().execute("BEGIN")

    def commit(self):

        self.connect().commit()

    def rollback(self):

        self.connect().rollback()

    def __enter__(self):

        self.connect()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if exc_type is None:
            self.commit()
        else:
            self.rollback()

        self.close()
