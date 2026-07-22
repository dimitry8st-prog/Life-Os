"""Life OS — генерация .md-заметки в строгом формате из ТЗ.

Жёсткие правила:
- Раздел «Мои мысли» ВСЕГДА пустой (только ручное заполнение).
- Раздел «Для научных материалов» включается только при type: paper.
- Существующие файлы НИКОГДА не перезаписываются: при коллизии имени
  добавляется числовой суффикс.
- Запись строго в utf-8.
"""

from __future__ import annotations

from pathlib import Path

NOTE_TEMPLATE = """---
title: {title}
date: {date}
source: {source}
area: {area}
type: {note_type}
tags: {tags}
related: {related}
status: {status}
---

## Саммари
{summary}

## Ключевые идеи
{key_ideas}
{science_block}
## Мои мысли


## Исходник
{source}
"""

SCIENCE_BLOCK = """
## Для научных материалов
- Методология: {methodology}
- Результаты: {results}
- Ограничения: {limitations}
"""


def render_note(meta: dict, body: dict) -> str:
    """Собирает текст заметки. Научный блок — только при type == 'paper'."""
    science = ""
    if meta.get("note_type") == "paper":
        sci = body.get("science") or {}
        science = SCIENCE_BLOCK.format(
            methodology=sci.get("methodology", ""),
            results=sci.get("results", ""),
            limitations=sci.get("limitations", ""),
        )
    key_ideas = "\n".join(f"- {idea}" for idea in body.get("key_ideas", []))
    related = ", ".join(f"[[{r}]]" for r in meta.get("related", []))
    tags = "[" + ", ".join(meta.get("tags", [])) + "]"
    return NOTE_TEMPLATE.format(
        title=meta.get("title", ""),
        date=meta.get("date", ""),
        source=meta.get("source", ""),
        area=meta.get("area", "other"),
        note_type=meta.get("note_type", "article"),
        tags=tags,
        related=related,
        status=meta.get("status", "inbox"),
        summary=body.get("summary", ""),
        key_ideas=key_ideas,
        science_block=science,
    )


def safe_write_note(directory: Path, filename: str, content: str) -> Path:
    """Пишет заметку, НИКОГДА не перезаписывая существующие файлы."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    stem, suffix = target.stem, target.suffix or ".md"
    counter = 1
    while target.exists():
        target = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    target.write_text(content, encoding="utf-8")
    return target


def parse_frontmatter(text: str) -> dict:
    """Минимальный парсер YAML-frontmatter заметки (покрыт тестами)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta
