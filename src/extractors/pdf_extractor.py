"""Извлечение контента из PDF, включая ссылки arXiv/bioRxiv (фаза 2)."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from src.logging_setup import get_logger

log = get_logger("extract.pdf")

ARXIV_ABS = re.compile(r"arxiv\.org/abs/([\w.\-/]+)", re.I)
BIORXIV = re.compile(r"biorxiv\.org/content/([\w.\-/]+?)(?:\.full)?(?:\.pdf)?$", re.I)


def resolve_pdf_url(url: str) -> str:
    """Преобразует ссылку arXiv/bioRxiv в прямую ссылку на PDF (чистая функция)."""
    m = ARXIV_ABS.search(url)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}"
    m = BIORXIV.search(url)
    if m:
        return f"https://www.biorxiv.org/content/{m.group(1)}.full.pdf"
    return url


def extract_pdf(source: str | Path) -> dict:
    """Возвращает {'title': str, 'text': str} из локального PDF или URL."""
    from pypdf import PdfReader  # ленивый импорт

    src = str(source)
    if src.lower().startswith(("http://", "https://")):
        import requests
        pdf_url = resolve_pdf_url(src)
        log.info("Скачивание PDF: %s", pdf_url)
        resp = requests.get(pdf_url, timeout=60)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            path = Path(tmp.name)
        title_fallback = pdf_url
    else:
        path = Path(src)
        title_fallback = path.stem

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    meta_title = (reader.metadata.title or "").strip() if reader.metadata else ""
    log.info("PDF: %d страниц, %d символов", len(pages), len(text))
    return {"title": meta_title or title_fallback, "text": text}
