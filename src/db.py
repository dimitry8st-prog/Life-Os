"""Life OS — работа с SQLite: инициализация схемы, базовые операции."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from src.config import PROJECT_ROOT

SCHEMA_PATH = PROJECT_ROOT / "schema.sql"


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Открывает соединение с включёнными внешними ключами."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    """Создаёт/обновляет схему из schema.sql (идемпотентно)."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection(db_path) as conn:
        conn.executescript(sql)


def content_hash(text: str) -> str:
    """SHA-256 контента для дедупликации."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_duplicate(conn: sqlite3.Connection, chash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM items WHERE content_hash = ? LIMIT 1", (chash,)
    ).fetchone()
    return row is not None


def log_failure(conn: sqlite3.Connection, stage: str, message: str,
                item_id: int | None = None) -> None:
    """Правило проекта: ошибки логируются, конвейер не прерывается."""
    conn.execute(
        "INSERT INTO pipeline_log (item_id, stage, level, message) VALUES (?, ?, 'ERROR', ?)",
        (item_id, stage, message),
    )
    if item_id is not None:
        conn.execute(
            "UPDATE items SET status = 'failed', error = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (message, item_id),
        )
    conn.commit()
