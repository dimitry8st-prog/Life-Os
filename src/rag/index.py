"""Life OS — локальный RAG-индекс (фаза 3).

Реализация без внешних зависимостей: TF-IDF-векторы + косинусная близость.
Индекс хранится в JSON (data/rag_index/index.json). Позже слой эмбеддингов
можно заменить на sentence-transformers, не меняя интерфейс.

Интерфейс:
    idx = RagIndex(path)
    idx.add(note_id, title, text)
    idx.related(text, top_k, threshold) -> [(note_id, title, similarity), ...]
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from src.logging_setup import get_logger

log = get_logger("rag")

TOKEN_RE = re.compile(r"[\w\-]{3,}", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Чанкинг по символам с перекрытием (параметры — из config.yaml)."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size должен быть больше overlap")
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class RagIndex:
    """Простой персистентный TF-IDF индекс заметок."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.docs: dict[str, dict] = {}   # note_id -> {"title": str, "tf": {...}}
        self.df: Counter = Counter()      # document frequency
        self._load()

    # --- персистентность ---

    def _load(self) -> None:
        index_file = self.path / "index.json"
        if index_file.exists():
            data = json.loads(index_file.read_text(encoding="utf-8"))
            self.docs = data.get("docs", {})
            self.df = Counter(data.get("df", {}))
            log.info("RAG-индекс загружен: %d заметок", len(self.docs))

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        payload = {"docs": self.docs, "df": dict(self.df)}
        (self.path / "index.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    # --- векторизация ---

    def _tf(self, text: str) -> dict[str, float]:
        counts = Counter(tokenize(text))
        total = sum(counts.values()) or 1
        return {t: c / total for t, c in counts.items()}

    def _tfidf(self, tf: dict[str, float]) -> dict[str, float]:
        n_docs = max(1, len(self.docs))
        return {
            t: weight * math.log(1 + n_docs / (1 + self.df.get(t, 0)))
            for t, weight in tf.items()
        }

    # --- API ---

    def add(self, note_id: str, title: str, text: str) -> None:
        tf = self._tf(text)
        if note_id not in self.docs:
            for token in tf:
                self.df[token] += 1
        self.docs[note_id] = {"title": title, "tf": tf}
        log.info("RAG: добавлена заметка %s (%d термов)", note_id, len(tf))

    def related(self, text: str, top_k: int = 5,
                threshold: float = 0.75) -> list[tuple[str, str, float]]:
        """Топ-k заметок по косинусной близости выше порога."""
        query = self._tfidf(self._tf(text))
        scored = []
        for note_id, doc in self.docs.items():
            sim = cosine(query, self._tfidf(doc["tf"]))
            if sim >= threshold:
                scored.append((note_id, doc["title"], round(sim, 4)))
        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:top_k]
