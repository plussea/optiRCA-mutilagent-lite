"""Shared pytest fixtures."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from optirc_lite.config import settings
from optirc_lite.storage.sqlite_store import SQLiteStore


@pytest.fixture(autouse=True)
def disable_llm_in_tests():
    """Tests run deterministically with rule fallback; LLM tests opt in explicitly."""
    with patch("optirc_lite.tools.llm.llm_tool.enabled", return_value=False):
        yield


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    """Route SQLite storage to a temp directory for isolated tests."""
    db_path = tmp_path / "optirc_lite.db"
    monkeypatch.setattr("optirc_lite.config.settings.database_path", db_path)
    store = SQLiteStore(path=db_path)
    store.init()
    return store
