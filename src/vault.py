"""Life OS — работа с хранилищем Obsidian.

- Создание структуры папок из config.yaml (если отсутствует).
- Сбор существующих тегов из хранилища (правило: новые теги только предлагать).
- Выбор папки назначения: /Inbox по умолчанию, /Areas/<область> при
  уверенности >= thresholds.auto_area (фаза 4).
"""

from __future__ import annotations

import re
from pathlib import Path

from src.logging_setup import get_logger

log = get_logger("vault")

TAG_RE = re.compile(r"#([\w\-/]+)")
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def ensure_vault_structure(vault: Path, layout: dict) -> None:
    """Создаёт папки хранилища по config.yaml (идемпотентно)."""
    folders = [layout.get("inbox", "Inbox"), layout.get("notes", "Notes"),
               layout.get("projects", "Projects"), layout.get("tags", "Tags")]
    folders += list((layout.get("areas") or {}).values())
    for folder in folders:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    log.info("Структура хранилища проверена: %s", vault)


def collect_existing_tags(vault: Path) -> set[str]:
    """Собирает все теги (#tag и tags: во frontmatter) из .md-файлов хранилища."""
    tags: set[str] = set()
    for md in vault.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        tags.update(TAG_RE.findall(text))
    log.info("Найдено существующих тегов: %d", len(tags))
    return tags


def split_tags(suggested: list[str], existing: set[str]) -> tuple[list[str], list[str]]:
    """Разделяет предложенные моделью теги на (используем, предлагаем_владельцу).

    Правило проекта: в заметку идут только уже существующие теги;
    новые — возвращаются отдельным списком для предложения.
    """
    approved = [t for t in suggested if t in existing]
    proposed = [t for t in suggested if t not in existing]
    return approved, proposed


def choose_target_folder(vault: Path, layout: dict, area: str,
                         confidence: float, auto_area_threshold: float) -> Path:
    """/Areas/<область> при высокой уверенности, иначе /Inbox."""
    areas = layout.get("areas") or {}
    if area in areas and confidence >= auto_area_threshold:
        return vault / areas[area]
    return vault / layout.get("inbox", "Inbox")


def make_filename(title: str, date: str) -> str:
    """Безопасное имя файла для Windows: <YYYY-MM-DD> <название>.md."""
    clean = INVALID_FILENAME.sub("", title).strip().strip(".")
    clean = re.sub(r"\s+", " ", clean)[:80] or "untitled"
    return f"{date} {clean}.md"
