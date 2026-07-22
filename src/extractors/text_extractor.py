"""Чтение локального текста / заметки (фаза 1). Строго utf-8."""

from __future__ import annotations

from pathlib import Path

from src.logging_setup import get_logger

log = get_logger("extract.text")


def extract_text(path: Path) -> dict:
    """Возвращает {'title': str, 'text': str}."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    log.info("Прочитан файл %s (%d символов)", path.name, len(text))
    return {"title": path.stem, "text": text}
