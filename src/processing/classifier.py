"""Правила разрешения области по порогам из config.yaml.

Сама классификация выполняется в src/claude_client.py (один вызов API
возвращает и область, и саммари). Здесь — чистая пороговая логика,
покрытая тестами.
"""

from __future__ import annotations

from src.config import AREAS


def resolve_area(area: str, confidence: float, thresholds: dict) -> str:
    """other при неизвестной области или уверенности ниже needs_review."""
    if area not in AREAS:
        return "other"
    if confidence < float(thresholds.get("needs_review", 0.55)):
        return "other"
    return area
