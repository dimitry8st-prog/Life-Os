"""Life OS — тесты фазы 0.

По правилам проекта тесты обязательны минимум на:
1) классификацию области (здесь — чистая логика порогов resolve_area);
2) парсинг frontmatter.
Плюс smoke-тесты каркаса: конфиг читается, БД создаётся.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.db import content_hash, get_connection, init_db
from src.pipeline import detect_source_type
from src.processing.classifier import resolve_area
from src.processing.note_writer import parse_frontmatter, render_note, safe_write_note

THRESHOLDS = {"auto_area": 0.85, "needs_review": 0.55}


# --- классификация: пороги ---

def test_resolve_area_confident():
    assert resolve_area("longevity", 0.9, THRESHOLDS) == "longevity"


def test_resolve_area_low_confidence_goes_other():
    assert resolve_area("longevity", 0.3, THRESHOLDS) == "other"


def test_resolve_area_unknown_area_goes_other():
    assert resolve_area("cooking", 0.99, THRESHOLDS) == "other"


# --- frontmatter ---

def test_parse_frontmatter_roundtrip():
    meta = {
        "title": "Test", "date": "2026-07-06", "source": "https://example.com",
        "area": "longevity", "note_type": "article",
        "tags": ["#longevity"], "related": [], "status": "inbox",
    }
    body = {"summary": "Кратко.", "key_ideas": ["Идея 1", "Идея 2"]}
    parsed = parse_frontmatter(render_note(meta, body))
    assert parsed["title"] == "Test"
    assert parsed["area"] == "longevity"
    assert parsed["status"] == "inbox"


def test_parse_frontmatter_missing():
    assert parse_frontmatter("Просто текст без frontmatter") == {}


def test_science_block_only_for_paper():
    meta = {"title": "T", "date": "2026-07-06", "source": "s",
            "area": "longevity", "note_type": "article",
            "tags": [], "related": [], "status": "inbox"}
    body = {"summary": "S", "key_ideas": []}
    assert "Для научных материалов" not in render_note(meta, body)
    meta["note_type"] = "paper"
    assert "Для научных материалов" in render_note(meta, body)


def test_my_thoughts_section_is_empty():
    meta = {"title": "T", "date": "2026-07-06", "source": "s",
            "area": "other", "note_type": "note",
            "tags": [], "related": [], "status": "inbox"}
    note = render_note(meta, {"summary": "S", "key_ideas": []})
    thoughts = note.split("## Мои мысли")[1].split("## Исходник")[0]
    assert thoughts.strip() == ""


# --- защита от перезаписи ---

def test_safe_write_never_overwrites(tmp_path):
    p1 = safe_write_note(tmp_path, "note.md", "v1")
    p2 = safe_write_note(tmp_path, "note.md", "v2")
    assert p1 != p2
    assert p1.read_text(encoding="utf-8") == "v1"
    assert p2.read_text(encoding="utf-8") == "v2"


# --- определение типа источника ---

def test_detect_source_type():
    assert detect_source_type("https://example.com/article") == "url"
    assert detect_source_type("https://arxiv.org/abs/1234") == "pdf"   # arXiv -> PDF
    assert detect_source_type("https://ar5iv.labs.arxiv.org/html/2211.01910") == "url"
    assert detect_source_type("https://youtu.be/abc") == "youtube"
    assert detect_source_type("paper.pdf") == "pdf"
    assert detect_source_type("notes.txt") == "text"


# --- smoke: конфиг и БД ---

def test_config_loads():
    cfg = load_config()
    assert cfg.raw.get("project_name") == "Life OS"
    assert cfg.claude_model


def test_db_init(tmp_path):
    db = tmp_path / "test.sqlite3"
    init_db(db)
    with get_connection(db) as conn:
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"items", "tags", "item_tags", "relations", "pipeline_log"} <= tables


def test_content_hash_dedup_stable():
    assert content_hash("abc") == content_hash("abc")
    assert content_hash("abc") != content_hash("abd")
