"""Life OS — оркестратор конвейера.

Вход (URL / PDF / текст / YouTube)
  → извлечение контента
  → дедупликация по SHA-256
  → Claude API (классификация + саммари + научный блок + теги)
  → related-связи через RAG
  → .md-заметка (строгий формат) в /Inbox или /Areas/<область>
  → запись в SQLite (+ теги, + связи)
  → добавление в RAG-индекс

Правила: ошибки логируются (файл + pipeline_log, статус failed) и не роняют
процесс; существующие заметки никогда не перезаписываются.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from src.claude_client import ClaudeClient
from src.config import Config
from src.db import content_hash, get_connection, is_duplicate, log_failure
from src.extractors.pdf_extractor import extract_pdf
from src.extractors.text_extractor import extract_text
from src.extractors.url_extractor import extract_url
from src.extractors.youtube_extractor import extract_youtube
from src.logging_setup import get_logger
from src.processing.classifier import resolve_area
from src.processing.note_writer import render_note, safe_write_note
from src.rag.index import RagIndex
from src.vault import (choose_target_folder, collect_existing_tags,
                       ensure_vault_structure, make_filename, split_tags)
from src.vault_pages import generate_vault_pages

log = get_logger("pipeline")

YOUTUBE_HOSTS = ("youtube.com", "youtu.be")


def detect_source_type(source: str) -> str:
    """url | pdf | text | youtube — по виду источника."""
    low = source.lower()
    if low.startswith(("http://", "https://")):
        if any(h in low for h in YOUTUBE_HOSTS):
            return "youtube"
        if "ar5iv" in low:
            return "url"
        if low.endswith(".pdf") or "arxiv.org" in low or "biorxiv.org" in low:
            return "pdf"
        return "url"
    suffix = Path(source).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    return "text"


EXTRACTORS = {
    "url": extract_url,
    "pdf": extract_pdf,
    "text": extract_text,
    "youtube": extract_youtube,
}


@dataclass
class PipelineResult:
    status: str                 # processed | filed | duplicate | failed
    note_path: Path | None = None
    area: str = "other"
    confidence: float = 0.0
    related: list = field(default_factory=list)
    proposed_tags: list = field(default_factory=list)
    error: str | None = None


def run_pipeline(source: str, cfg: Config, vault: Path,
                 client: ClaudeClient | None = None) -> PipelineResult:
    """Полный прогон одного материала. Никогда не бросает исключений наружу."""
    client = client or ClaudeClient(cfg.claude_model,
                                    cfg.raw.get("claude", {}).get("max_tokens", 4000))
    conn = get_connection(cfg.db_path)
    item_id: int | None = None
    stype = detect_source_type(source)
    log.info("=== Захват: %s (тип: %s) ===", source, stype)

    try:
        # 1. Извлечение
        try:
            extracted = EXTRACTORS[stype](source)
        except Exception as exc:
            log.error("Извлечение не удалось: %s", exc)
            log_failure(conn, "extract", f"{source}: {exc}")
            return PipelineResult(status="failed", error=str(exc))

        text = extracted["text"]
        if not text.strip():
            log_failure(conn, "extract", f"{source}: пустой контент")
            return PipelineResult(status="failed", error="Пустой контент")

        # 2. Дедупликация
        chash = content_hash(text)
        if is_duplicate(conn, chash):
            log.warning("Дубликат по хэшу, пропуск: %s", source)
            return PipelineResult(status="duplicate", error="Дубликат контента")

        # Черновая запись в БД (для привязки ошибок последующих этапов)
        cur = conn.execute(
            "INSERT INTO items (source, source_type, title, content_hash, status) "
            "VALUES (?, ?, ?, ?, 'inbox')",
            (source, stype, extracted["title"], chash),
        )
        item_id = cur.lastrowid
        conn.commit()

        # 3. Обработка через Claude API
        try:
            result = client.process(text, source, stype)
        except Exception as exc:
            log.error("Claude API: %s", exc)
            log_failure(conn, "classify", str(exc), item_id)
            return PipelineResult(status="failed", error=str(exc))

        thresholds = cfg.thresholds
        confidence = result["confidence"]
        area = resolve_area(result["area"], confidence, thresholds)
        needs_review = area == "other" and result["area"] != "other" or \
            confidence < float(thresholds.get("needs_review", 0.55))
        if needs_review:
            log.info("Низкая уверенность %.2f -> other + #needs-review", confidence)

        # 4. Теги: только существующие; новые — предложить
        existing_tags = collect_existing_tags(vault)
        tags, proposed = split_tags(result["suggested_tags"], existing_tags)
        if needs_review:
            tags.append("needs-review")

        # 5. Related через RAG
        rag = RagIndex(cfg.rag_index_path)
        related = rag.related(
            text,
            top_k=int(thresholds.get("related_top_k", 5)),
            threshold=float(thresholds.get("related_similarity", 0.75)),
        )
        related_titles = [title for _, title, _ in related]

        # 6. Заметка
        today = dt.date.today().isoformat()
        target = choose_target_folder(
            vault, cfg.vault_layout, area, confidence,
            float(thresholds.get("auto_area", 0.85)),
        )
        filed = target != vault / cfg.vault_layout.get("inbox", "Inbox")
        meta = {
            "title": result["title"], "date": today, "source": source,
            "area": area, "note_type": result["type"],
            "tags": [f"#{t}" for t in tags], "related": related_titles,
            "status": "filed" if filed else "inbox",
        }
        body = {"summary": result["summary"], "key_ideas": result["key_ideas"],
                "science": result["science"]}
        try:
            note_path = safe_write_note(
                target, make_filename(result["title"], today), render_note(meta, body)
            )
        except Exception as exc:
            log.error("Запись заметки: %s", exc)
            log_failure(conn, "write", str(exc), item_id)
            return PipelineResult(status="failed", error=str(exc))
        log.info("Заметка создана: %s", note_path)

        # 7. Финализация в SQLite: item, теги, связи
        status = "filed" if filed else "processed"
        conn.execute(
            "UPDATE items SET title=?, area=?, area_confidence=?, note_type=?, "
            "note_path=?, status=?, updated_at=datetime('now') WHERE id=?",
            (result["title"], area, confidence, result["type"],
             str(note_path), status, item_id),
        )
        for tag in tags:
            conn.execute("INSERT OR IGNORE INTO tags (name, approved) VALUES (?, 1)", (tag,))
            conn.execute(
                "INSERT OR IGNORE INTO item_tags (item_id, tag_id) "
                "SELECT ?, id FROM tags WHERE name=?", (item_id, tag),
            )
        for tag in proposed:
            conn.execute("INSERT OR IGNORE INTO tags (name, approved) VALUES (?, 0)", (tag,))
        for rel_id, _, sim in related:
            if str(rel_id).isdigit():
                conn.execute(
                    "INSERT OR IGNORE INTO relations (item_id, related_id, similarity) "
                    "VALUES (?, ?, ?)", (item_id, int(rel_id), sim),
                )
        conn.commit()

        # 8. RAG-индекс
        try:
            rag.add(str(item_id), result["title"], text)
            rag.save()
        except Exception as exc:
            log.error("RAG-индексация: %s", exc)  # не критично для заметки
            log_failure(conn, "index", str(exc), item_id)

        if proposed:
            log.info("Предложены новые теги (нужно одобрение): %s", ", ".join(proposed))

        try:
            generate_vault_pages(vault)
        except Exception as exc:
            log.error("HTML-страницы vault: %s", exc)

        return PipelineResult(status=status, note_path=note_path, area=area,
                              confidence=confidence, related=related,
                              proposed_tags=proposed)
    finally:
        conn.close()


def prepare_vault(vault: Path, cfg: Config) -> None:
    ensure_vault_structure(vault, cfg.vault_layout)
