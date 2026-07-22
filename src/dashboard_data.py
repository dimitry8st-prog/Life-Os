"""Запросы и подготовка данных для интерактивного дашборда."""

from __future__ import annotations

import sqlite3
from pathlib import Path


AREA_LABELS = {
    "prompt-engineering": "Промпт-инжиниринг",
    "vibe-coding": "Вайб-кодинг",
    "longevity": "Долголетие",
    "immortality": "Бессмертие",
    "other": "Прочее",
}


def list_items(conn: sqlite3.Connection, search: str = "", area: str = "Все",
               state: str = "Все", note_type: str = "Все") -> list[sqlite3.Row]:
    clauses = ["i.status != 'failed'"]
    params: list[object] = []
    if search:
        clauses.append("(lower(i.title) LIKE ? OR lower(i.source) LIKE ?)")
        term = f"%{search.lower()}%"
        params.extend([term, term])
    if area != "Все":
        clauses.append("i.area = ?")
        params.append(area)
    if note_type != "Все":
        clauses.append("i.note_type = ?")
        params.append(note_type)
    if state == "Непрочитанные":
        clauses.append("COALESCE(r.is_read, 0) = 0")
    elif state == "Прочитанные":
        clauses.append("r.is_read = 1")
    elif state == "Избранное":
        clauses.append("r.is_favorite = 1")
    sql = f"""
        SELECT i.*, COALESCE(r.is_read, 0) AS is_read,
               COALESCE(r.is_favorite, 0) AS is_favorite
        FROM items i LEFT JOIN reading_state r ON r.item_id = i.id
        WHERE {' AND '.join(clauses)}
        ORDER BY datetime(i.created_at) DESC, i.id DESC
    """
    return conn.execute(sql, params).fetchall()


def set_state(conn: sqlite3.Connection, item_id: int, field: str, value: bool) -> None:
    if field not in {"is_read", "is_favorite"}:
        raise ValueError("Недопустимое поле состояния")
    conn.execute(
        f"""INSERT INTO reading_state (item_id, {field}) VALUES (?, ?)
        ON CONFLICT(item_id) DO UPDATE SET {field}=excluded.{field}, updated_at=datetime('now')""",
        (item_id, int(value)),
    )
    conn.commit()


def note_preview(note_path: str | None, limit: int = 420) -> str:
    if not note_path:
        return "Саммари пока недоступно."
    path = Path(note_path)
    if not path.exists():
        return "Файл заметки не найден на этом компьютере."
    text = path.read_text(encoding="utf-8")
    marker, next_marker = "## Саммари", "## Ключевые идеи"
    if marker in text:
        text = text.split(marker, 1)[1].split(next_marker, 1)[0].strip()
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"
