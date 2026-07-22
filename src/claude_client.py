"""Life OS — клиент Claude API.

Один вызов API возвращает сразу: область (с уверенностью), тип материала,
саммари, ключевые идеи, научный блок (для paper) и предлагаемые теги.

Правила:
- API-ключ ТОЛЬКО из переменной окружения ANTHROPIC_API_KEY (.env).
- Импорт anthropic ленивый: тесты работают на моках без установленного SDK.
- Ответ модели — строго JSON; парсинг устойчив к ```json-ограждениям.
"""

from __future__ import annotations

import json
import os
import re

from src.config import AREAS
from src.logging_setup import get_logger

log = get_logger("claude")

SYSTEM_PROMPT = """Ты — обработчик материалов для персональной базы знаний Life OS.
Области: prompt-engineering, vibe-coding, longevity, immortality, other.
Отвечай ТОЛЬКО валидным JSON без пояснений и без markdown-ограждений, схема:
{
  "title": "название материала",
  "area": "prompt-engineering|vibe-coding|longevity|immortality|other",
  "confidence": 0.0-1.0,
  "type": "article|paper|video|book|note",
  "summary": "краткое содержание, 3-5 предложений",
  "key_ideas": ["5-7 ключевых идей"],
  "science": {"methodology": "...", "results": "...", "limitations": "..."} или null,
  "suggested_tags": ["теги без #"]
}
Правила: "science" заполняй только для научных работ (type=paper), иначе null.
Если материал не относится уверенно ни к одной области — area=other и низкий confidence.
Извлекай суть основного контента, игнорируя навигацию, рекламу и комментарии."""

MAX_INPUT_CHARS = 60_000  # грубое ограничение на объём передаваемого текста


class ClaudeProcessingError(RuntimeError):
    """Ошибка обработки материала через Claude API."""


class ClaudeClient:
    """Обёртка над anthropic.Anthropic. В тестах подменяется моком."""

    def __init__(self, model: str, max_tokens: int = 4000):
        self.model = model
        self.max_tokens = max_tokens
        self._client = None  # ленивое создание

    def _ensure_client(self):
        if self._client is None:
            try:
                import anthropic  # ленивый импорт
            except ImportError as exc:  # pragma: no cover
                raise ClaudeProcessingError(
                    "Пакет anthropic не установлен: pip install anthropic"
                ) from exc
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ClaudeProcessingError(
                    "ANTHROPIC_API_KEY не задан (создайте .env по образцу .env.example)"
                )
            self._client = anthropic.Anthropic()
        return self._client

    def process(self, text: str, source: str, source_type: str) -> dict:
        """Классификация + саммари одним вызовом. Возвращает словарь по схеме."""
        client = self._ensure_client()
        payload = text[:MAX_INPUT_CHARS]
        user_msg = (
            f"Источник: {source}\nТип источника: {source_type}\n\n"
            f"Материал:\n{payload}"
        )
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        return parse_model_json(raw)


def parse_model_json(raw: str) -> dict:
    """Парсит JSON-ответ модели, снимая возможные ```-ограждения.

    Валидирует и нормализует поля (чистая функция — покрыта тестами).
    """
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ClaudeProcessingError(f"Модель вернула невалидный JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ClaudeProcessingError("Ожидался JSON-объект")

    area = str(data.get("area", "other")).lower()
    if area not in AREAS:
        log.warning("Неизвестная область '%s' — заменена на other", area)
        area = "other"

    note_type = str(data.get("type", "article")).lower()
    if note_type not in ("article", "paper", "video", "book", "note"):
        note_type = "article"

    try:
        confidence = min(1.0, max(0.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    science = data.get("science") if note_type == "paper" else None
    if science is not None and not isinstance(science, dict):
        science = None

    return {
        "title": str(data.get("title", "")).strip() or "Без названия",
        "area": area,
        "confidence": confidence,
        "type": note_type,
        "summary": str(data.get("summary", "")).strip(),
        "key_ideas": [str(i).strip() for i in data.get("key_ideas", []) if str(i).strip()],
        "science": science,
        "suggested_tags": [
            str(t).strip().lstrip("#") for t in data.get("suggested_tags", []) if str(t).strip()
        ],
    }
