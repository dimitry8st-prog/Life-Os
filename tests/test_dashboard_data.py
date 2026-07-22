import sqlite3

import pytest

from src.dashboard_data import list_items, set_state


@pytest.fixture
def conn():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE items (id INTEGER PRIMARY KEY, source TEXT, title TEXT, area TEXT,
          note_type TEXT, status TEXT, created_at TEXT, area_confidence REAL, note_path TEXT);
        CREATE TABLE reading_state (item_id INTEGER PRIMARY KEY, is_read INTEGER DEFAULT 0,
          is_favorite INTEGER DEFAULT 0, updated_at TEXT);
        INSERT INTO items VALUES (1, 'https://example.org', 'AI Agents', 'vibe-coding',
          'article', 'filed', datetime('now'), 0.9, NULL);
    """)
    return db


def test_filters_and_reading_state(conn):
    assert len(list_items(conn, search="agents")) == 1
    assert len(list_items(conn, state="Непрочитанные")) == 1
    set_state(conn, 1, "is_read", True)
    assert len(list_items(conn, state="Прочитанные")) == 1
    set_state(conn, 1, "is_favorite", True)
    assert len(list_items(conn, state="Избранное")) == 1


def test_rejects_unknown_state_field(conn):
    with pytest.raises(ValueError):
        set_state(conn, 1, "bad_field", True)
