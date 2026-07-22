"""Извлечение основного контента веб-страницы (фаза 1).

Убирает навигацию, скрипты, стили, рекламу, комментарии — берётся
основной текст (article/main, иначе body).
PubMed: прямой HTML часто отдаёт 403, поэтому используется NCBI E-utilities.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from src.logging_setup import get_logger

log = get_logger("extract.url")

NOISE_TAGS = ("script", "style", "nav", "header", "footer", "aside", "form",
              "iframe", "noscript", "button", "svg")
NOISE_HINTS = ("comment", "sidebar", "advert", "banner", "cookie", "popup", "menu")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
TIMEOUT = 30
PUBMED_PMID = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.I)
EUTILS_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EUTILS_TOOL = "lifeos"
EUTILS_EMAIL = "lifeos@local"


def parse_pubmed_pmid(url: str) -> str | None:
    """Извлекает PMID из URL PubMed (чистая функция)."""
    m = PUBMED_PMID.search(url)
    return m.group(1) if m else None


def parse_pubmed_xml(xml_text: str, fallback_title: str = "") -> dict:
    """Парсит ответ E-utilities (efetch, retmode=xml) в title + text."""
    root = ET.fromstring(xml_text)
    title_el = root.find(".//ArticleTitle")
    title = (title_el.text or "").strip() if title_el is not None else fallback_title

    parts: list[str] = []
    for block in root.findall(".//Abstract/AbstractText"):
        label = block.attrib.get("Label", "").strip()
        text = "".join(block.itertext()).strip()
        if not text:
            continue
        parts.append(f"{label}: {text}" if label else text)

    keywords = [
        kw.text.strip()
        for kw in root.findall(".//Keyword")
        if kw.text and kw.text.strip()
    ]
    if keywords:
        parts.append("Keywords: " + "; ".join(keywords))

    journal = root.find(".//Journal/Title")
    if journal is not None and journal.text:
        parts.insert(0, f"Journal: {journal.text.strip()}")

    doi_el = root.find(".//ELocationID[@EIdType='doi']")
    if doi_el is not None and doi_el.text:
        parts.insert(0, f"DOI: {doi_el.text.strip()}")

    text = "\n\n".join(parts).strip()
    return {"title": title or fallback_title, "text": text}


def extract_pubmed(pmid: str) -> dict:
    """Загружает статью PubMed через NCBI E-utilities."""
    log.info("Загрузка PubMed PMID %s через E-utilities", pmid)
    resp = requests.get(
        EUTILS_FETCH,
        params={
            "db": "pubmed",
            "id": pmid,
            "rettype": "abstract",
            "retmode": "xml",
            "tool": EUTILS_TOOL,
            "email": EUTILS_EMAIL,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    out = parse_pubmed_xml(resp.text, fallback_title=f"PubMed {pmid}")
    log.info("Извлечено %d символов, заголовок: %s", len(out["text"]), out["title"][:80])
    return out


def extract_url(url: str) -> dict:
    """Возвращает {'title': str, 'text': str}."""
    pmid = parse_pubmed_pmid(url)
    if pmid:
        return extract_pubmed(pmid)

    log.info("Загрузка URL: %s", url)
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return extract_from_html(resp.text, fallback_title=url)


def extract_from_html(html: str, fallback_title: str = "") -> dict:
    """Чистая функция извлечения из HTML (покрыта тестами без сети)."""
    soup = BeautifulSoup(html, "html.parser")

    title = (soup.title.get_text(strip=True) if soup.title else "") or fallback_title

    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()
    for tag in soup.find_all(attrs={"class": True}):
        classes = " ".join(tag.get("class", [])).lower()
        if any(hint in classes for hint in NOISE_HINTS):
            tag.decompose()

    root = soup.find("article") or soup.find("main") or soup.body or soup
    text = "\n".join(
        line.strip() for line in root.get_text("\n").splitlines() if line.strip()
    )
    log.info("Извлечено %d символов, заголовок: %s", len(text), title[:80])
    return {"title": title, "text": text}
