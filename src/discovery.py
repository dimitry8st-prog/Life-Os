"""Поиск свежих материалов в разрешённых RSS/Atom-источниках."""

from __future__ import annotations

import calendar
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import feedparser


@dataclass(frozen=True)
class Candidate:
    url: str
    title: str
    published_at: dt.datetime
    topic: str
    source: str
    score: int


def _published(entry: Any) -> dt.datetime:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return dt.datetime.fromtimestamp(calendar.timegm(parsed), tz=dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc)


def _normalise_url(url: str) -> str:
    return re.sub(r"[?#].*$", "", url.strip()).rstrip("/")


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {_normalise_url(item) for item in data.get("seen_urls", [])}
    except (OSError, ValueError, TypeError):
        return set()


def save_seen(path: Path, urls: set[str], keep: int = 5000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"seen_urls": sorted(urls)[-keep:], "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def discover(discovery_cfg: dict[str, Any], seen: set[str], now: dt.datetime | None = None) -> list[Candidate]:
    """Возвращает лучшие свежие URL; страницы сайтов напрямую не сканирует."""
    now = now or dt.datetime.now(dt.timezone.utc)
    lookback = dt.timedelta(days=int(discovery_cfg.get("lookback_days", 14)))
    topic_keywords = discovery_cfg.get("topics", {})
    candidates: dict[str, Candidate] = {}

    for source in discovery_cfg.get("sources", []):
        if not source.get("enabled", True):
            continue
        feed = feedparser.parse(source["url"], request_headers={"User-Agent": "LifeOS/1.0 RSS reader"})
        for entry in feed.entries:
            url = _normalise_url(entry.get("link", ""))
            if not url or url in seen:
                continue
            published = _published(entry)
            if now - published > lookback:
                continue
            haystack = " ".join((entry.get("title", ""), entry.get("summary", ""))).lower()
            allowed_topics = source.get("topics") or list(topic_keywords)
            for topic in allowed_topics:
                hits = sum(1 for keyword in topic_keywords.get(topic, []) if keyword.lower() in haystack)
                if not hits:
                    continue
                recency = max(0, int(lookback.days - (now - published).days))
                score = hits * 10 + recency + int(source.get("priority", 0))
                item = Candidate(url, entry.get("title", url).strip(), published, topic, source.get("name", source["url"]), score)
                if url not in candidates or item.score > candidates[url].score:
                    candidates[url] = item

    return sorted(candidates.values(), key=lambda item: (item.score, item.published_at), reverse=True)[: int(discovery_cfg.get("max_per_run", 12))]
