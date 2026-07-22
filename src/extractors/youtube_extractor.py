"""Транскрипты YouTube (фаза 4)."""

from __future__ import annotations

import re

from src.logging_setup import get_logger

log = get_logger("extract.youtube")

VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|shorts/)([\w\-]{11})")


def parse_video_id(url: str) -> str | None:
    """Извлекает ID видео из ссылки (чистая функция — покрыта тестами)."""
    m = VIDEO_ID.search(url)
    return m.group(1) if m else None


def extract_youtube(url: str) -> dict:
    """Возвращает {'title': str, 'text': str} — транскрипт видео."""
    from youtube_transcript_api import YouTubeTranscriptApi  # ленивый импорт

    video_id = parse_video_id(url)
    if not video_id:
        raise ValueError(f"Не удалось извлечь ID видео из ссылки: {url}")
    log.info("Загрузка транскрипта YouTube: %s", video_id)
    segments = YouTubeTranscriptApi().fetch(video_id, languages=["ru", "en"])
    text = " ".join(s.text for s in segments)
    return {"title": f"YouTube {video_id}", "text": text}
