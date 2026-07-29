"""Shared pytest fixtures."""

import tempfile
from pathlib import Path

import pytest

from optirc_lite.config import settings
from optirc_lite.storage.sqlite_store import SQLiteStore


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    """Route SQLite storage to a temp directory for isolated tests."""
    db_path = tmp_path / "optirc_lite.db"
    monkeypatch.setattr("optirc_lite.config.settings.database_path", db_path)
    store = SQLiteStore(path=db_path)
    store.init()
    return store
