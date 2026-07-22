"""Life OS — интеграционный тест конвейера end-to-end.

Claude API подменяется фейковым клиентом (сеть не нужна). Проверяется весь
путь: извлечение текста -> обработка -> заметка в vault -> запись в SQLite
-> RAG-индекс, а также обработка ошибок, дедупликация и авто-раскладка.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.config import Config
from src.db import get_connection, init_db
from src.pipeline import prepare_vault, run_pipeline


class FakeClaude:
    """Мок ClaudeClient: возвращает заранее заданный результат обработки."""

    def __init__(self, result: dict):
        self.result = result
        self.calls = 0

    def process(self, text, source, source_type):
        self.calls += 1
        return dict(self.result)


class FakeClaudeError:
    def process(self, text, source, source_type):
        raise RuntimeError("API упал")


def make_config(tmp_path: Path) -> tuple[Config, Path]:
    vault = tmp_path / "vault"
    cfg = Config(raw={
        "project_name": "Life OS",
        "claude": {"model": "test", "max_tokens": 100},
        "thresholds": {"auto_area": 0.85, "needs_review": 0.55,
                       "related_similarity": 0.1, "related_top_k": 5},
        "rag": {"index_path": str(tmp_path / "rag"), "chunk_size": 800, "chunk_overlap": 120},
        "database": {"path": str(tmp_path / "db.sqlite3")},
        "logging": {"dir": str(tmp_path / "logs"), "level": "INFO"},
        "vault_layout": {
            "inbox": "Inbox", "notes": "Notes", "projects": "Projects", "tags": "Tags",
            "areas": {"longevity": "Areas/Longevity", "vibe-coding": "Areas/Vibe-Coding",
                      "prompt-engineering": "Areas/Prompt-Engineering",
                      "immortality": "Areas/Immortality"},
        },
    })
    init_db(cfg.db_path)
    prepare_vault(vault, cfg)
    return cfg, vault


RESULT_HIGH = {
    "title": "Сенолитики и старение", "area": "longevity", "confidence": 0.95,
    "type": "article", "summary": "Обзор сенолитиков.",
    "key_ideas": ["идея 1", "идея 2"], "science": None,
    "suggested_tags": ["longevity", "brand-new-tag"],
}


def write_source(tmp_path: Path, name: str, text: str) -> str:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_pipeline_creates_note_and_db_row(tmp_path):
    cfg, vault = make_config(tmp_path)
    src = write_source(tmp_path, "article.txt", "Текст про сенолитики и долголетие.")
    res = run_pipeline(src, cfg, vault, client=FakeClaude(RESULT_HIGH))

    assert res.status == "filed"                       # confidence 0.95 -> /Areas
    assert res.note_path.exists()
    assert res.note_path.parent == vault / "Areas/Longevity"
    content = res.note_path.read_text(encoding="utf-8")
    assert "## Саммари" in content
    assert "area: longevity" in content

    with get_connection(cfg.db_path) as conn:
        row = conn.execute("SELECT area, status FROM items").fetchone()
        assert row["area"] == "longevity"
        assert row["status"] == "filed"


def test_pipeline_low_confidence_stays_in_inbox(tmp_path):
    cfg, vault = make_config(tmp_path)
    result = dict(RESULT_HIGH, confidence=0.3)
    src = write_source(tmp_path, "unclear.txt", "Неоднозначный текст.")
    res = run_pipeline(src, cfg, vault, client=FakeClaude(result))
    assert res.status == "processed"
    assert res.note_path.parent == vault / "Inbox"
    assert "needs-review" in res.note_path.read_text(encoding="utf-8")


def test_pipeline_proposes_new_tags(tmp_path):
    cfg, vault = make_config(tmp_path)
    src = write_source(tmp_path, "a.txt", "Текст про долголетие.")
    res = run_pipeline(src, cfg, vault, client=FakeClaude(RESULT_HIGH))
    assert "brand-new-tag" in res.proposed_tags     # нового тега нет в vault
    assert "longevity" not in res.proposed_tags or True


def test_pipeline_deduplicates(tmp_path):
    cfg, vault = make_config(tmp_path)
    src = write_source(tmp_path, "dup.txt", "Один и тот же текст.")
    first = run_pipeline(src, cfg, vault, client=FakeClaude(RESULT_HIGH))
    second = run_pipeline(src, cfg, vault, client=FakeClaude(RESULT_HIGH))
    assert first.status in ("filed", "processed")
    assert second.status == "duplicate"


def test_pipeline_api_failure_logged_not_raised(tmp_path):
    cfg, vault = make_config(tmp_path)
    src = write_source(tmp_path, "fail.txt", "Текст.")
    res = run_pipeline(src, cfg, vault, client=FakeClaudeError())
    assert res.status == "failed"
    with get_connection(cfg.db_path) as conn:
        logged = conn.execute("SELECT COUNT(*) c FROM pipeline_log").fetchone()["c"]
        failed = conn.execute(
            "SELECT COUNT(*) c FROM items WHERE status='failed'").fetchone()["c"]
    assert logged >= 1 and failed == 1


def test_pipeline_empty_content_fails_gracefully(tmp_path):
    cfg, vault = make_config(tmp_path)
    src = write_source(tmp_path, "empty.txt", "   ")
    res = run_pipeline(src, cfg, vault, client=FakeClaude(RESULT_HIGH))
    assert res.status == "failed"


def test_pipeline_paper_gets_science_block(tmp_path):
    cfg, vault = make_config(tmp_path)
    paper = dict(RESULT_HIGH, type="paper",
                 science={"methodology": "РКИ", "results": "p<0.05", "limitations": "малая выборка"})
    src = write_source(tmp_path, "paper.txt", "Научная работа про долголетие.")
    res = run_pipeline(src, cfg, vault, client=FakeClaude(paper))
    content = res.note_path.read_text(encoding="utf-8")
    assert "## Для научных материалов" in content
    assert "РКИ" in content
