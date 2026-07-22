"""Life OS — юнит-тесты модулей (без сети и без Claude API)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.claude_client import ClaudeProcessingError, parse_model_json
from src.extractors.pdf_extractor import resolve_pdf_url
from src.extractors.url_extractor import extract_from_html, parse_pubmed_pmid, parse_pubmed_xml
from src.extractors.youtube_extractor import parse_video_id
from src.rag.index import RagIndex, chunk_text, cosine, tokenize
from src.vault import (choose_target_folder, collect_existing_tags,
                       make_filename, split_tags)

LAYOUT = {
    "inbox": "Inbox",
    "areas": {"longevity": "Areas/Longevity", "vibe-coding": "Areas/Vibe-Coding"},
}


# --- claude_client: парсинг ответа модели ---

def test_parse_model_json_plain():
    raw = ('{"title":"T","area":"longevity","confidence":0.9,"type":"article",'
           '"summary":"S","key_ideas":["a","b"],"science":null,"suggested_tags":["#x"]}')
    data = parse_model_json(raw)
    assert data["area"] == "longevity"
    assert data["suggested_tags"] == ["x"]          # решётка снята


def test_parse_model_json_strips_fences():
    raw = '```json\n{"title":"T","area":"other","confidence":0.2,"type":"note"}\n```'
    assert parse_model_json(raw)["area"] == "other"


def test_parse_model_json_unknown_area_and_clamped_confidence():
    raw = '{"title":"T","area":"cooking","confidence":7,"type":"essay"}'
    data = parse_model_json(raw)
    assert data["area"] == "other"
    assert data["confidence"] == 1.0
    assert data["type"] == "article"


def test_parse_model_json_science_only_for_paper():
    raw = ('{"title":"T","area":"longevity","confidence":0.9,"type":"article",'
           '"science":{"methodology":"m"}}')
    assert parse_model_json(raw)["science"] is None


def test_parse_model_json_invalid_raises():
    with pytest.raises(ClaudeProcessingError):
        parse_model_json("это не JSON")


# --- extractors ---

def test_extract_from_html_removes_noise():
    html = """<html><head><title>Статья</title></head><body>
      <nav>МЕНЮ</nav><div class="sidebar-ads">РЕКЛАМА</div>
      <article><p>Полезный текст.</p></article>
      <div class="comments">КОММЕНТАРИЙ</div><script>var x=1;</script>
    </body></html>"""
    out = extract_from_html(html)
    assert out["title"] == "Статья"
    assert "Полезный текст." in out["text"]
    for noise in ("МЕНЮ", "РЕКЛАМА", "КОММЕНТАРИЙ", "var x"):
        assert noise not in out["text"]


def test_resolve_pdf_url_arxiv_and_biorxiv():
    assert resolve_pdf_url("https://arxiv.org/abs/2401.01234") == \
        "https://arxiv.org/pdf/2401.01234"
    assert "full.pdf" in resolve_pdf_url("https://www.biorxiv.org/content/10.1101/2024.01.01.573000v1")
    assert resolve_pdf_url("https://example.com/x.pdf") == "https://example.com/x.pdf"


def test_parse_video_id():
    assert parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_video_id("https://example.com") is None


def test_parse_pubmed_pmid():
    assert parse_pubmed_pmid("https://pubmed.ncbi.nlm.nih.gov/42361992/") == "42361992"
    assert parse_pubmed_pmid("https://example.com") is None


def test_parse_pubmed_xml():
    xml = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <Article>
      <Journal><Title>Free Radic Biol Med</Title></Journal>
      <ArticleTitle>Magnetotactic bacterium extends lifespan</ArticleTitle>
      <Abstract>
        <AbstractText>Magnetotactic bacteria were studied in C. elegans.</AbstractText>
      </Abstract>
      <ELocationID EIdType="doi">10.1016/j.example</ELocationID>
    </Article>
    <KeywordList><Keyword>ferroptosis</Keyword><Keyword>aging</Keyword></KeywordList>
  </PubmedArticle>
</PubmedArticleSet>"""
    out = parse_pubmed_xml(xml)
    assert out["title"] == "Magnetotactic bacterium extends lifespan"
    assert "Magnetotactic bacteria were studied" in out["text"]
    assert "DOI: 10.1016/j.example" in out["text"]
    assert "Keywords: ferroptosis; aging" in out["text"]


# --- rag ---

def test_chunk_text_overlap():
    chunks = chunk_text("a" * 2000, chunk_size=800, overlap=120)
    assert len(chunks) == 3
    assert all(len(c) <= 800 for c in chunks)


def test_chunk_text_invalid_params():
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=100, overlap=100)


def test_cosine_identity_and_orthogonal():
    a = {"x": 1.0, "y": 2.0}
    assert cosine(a, a) == pytest.approx(1.0)
    assert cosine(a, {"z": 1.0}) == 0.0
    assert cosine({}, a) == 0.0


def test_rag_related_finds_similar(tmp_path):
    # RAG работает на пересечении токенов (лемматизация — задача будущей итерации),
    # поэтому запрос содержит те же словоформы, что и релевантный документ.
    idx = RagIndex(tmp_path / "rag")
    idx.add("1", "Сенолитики и старение",
            "сенолитики удаляют сенесцентные клетки замедляют старение организма")
    idx.add("2", "Промпты для Claude",
            "промпт инжиниринг структура запроса роли примеры few-shot")
    hits = idx.related("сенолитики старение сенесцентные клетки организма",
                       top_k=5, threshold=0.1)
    assert hits and hits[0][0] == "1"


def test_rag_ranks_relevant_above_irrelevant(tmp_path):
    idx = RagIndex(tmp_path / "rag")
    idx.add("1", "Долголетие", "долголетие старение метформин рапамицин продление жизни")
    idx.add("2", "Кодинг", "python код функция класс тест отладка")
    hits = idx.related("метформин рапамицин продление жизни долголетие",
                       top_k=5, threshold=0.0)
    assert hits[0][0] == "1"
    assert hits[0][2] > (hits[1][2] if len(hits) > 1 else 0)


def test_rag_persistence(tmp_path):
    path = tmp_path / "rag"
    idx = RagIndex(path)
    idx.add("1", "T", "уникальный текст про долголетие")
    idx.save()
    reloaded = RagIndex(path)
    assert "1" in reloaded.docs


def test_tokenize_filters_short():
    assert "ab" not in tokenize("ab abc где-то")
    assert "где-то" in tokenize("ab abc где-то")


# --- vault ---

def test_split_tags_only_existing_used():
    used, proposed = split_tags(["longevity", "new-tag"], {"longevity", "ai"})
    assert used == ["longevity"]
    assert proposed == ["new-tag"]


def test_collect_existing_tags(tmp_path):
    (tmp_path / "note.md").write_text(
        "---\ntags: [#longevity]\n---\nтекст #senolytics", encoding="utf-8")
    tags = collect_existing_tags(tmp_path)
    assert {"longevity", "senolytics"} <= tags


def test_choose_target_folder_thresholds(tmp_path):
    high = choose_target_folder(tmp_path, LAYOUT, "longevity", 0.9, 0.85)
    low = choose_target_folder(tmp_path, LAYOUT, "longevity", 0.7, 0.85)
    other = choose_target_folder(tmp_path, LAYOUT, "other", 0.99, 0.85)
    assert high == tmp_path / "Areas/Longevity"
    assert low == tmp_path / "Inbox"
    assert other == tmp_path / "Inbox"


def test_make_filename_windows_safe():
    name = make_filename('Прорыв: сенолитики? <тест>/"2026"', "2026-07-07")
    assert name.endswith(".md")
    for ch in '<>:"/\\|?*':
        assert ch not in name
