"""Life OS — загрузка и валидация конфигурации (config.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

AREAS = ("prompt-engineering", "vibe-coding", "longevity", "immortality", "other")


@dataclass
class Config:
    """Типизированная обёртка над config.yaml."""

    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def vault_path(self) -> Path | None:
        value = self.raw.get("vault_path")
        return Path(value) if value else None

    def _resolve(self, value: str) -> Path:
        """Абсолютные пути — как есть; относительные — от корня проекта."""
        p = Path(value)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def db_path(self) -> Path:
        return self._resolve(self.raw.get("database", {}).get("path", "data/lifeos.sqlite3"))

    @property
    def log_dir(self) -> Path:
        return self._resolve(self.raw.get("logging", {}).get("dir", "logs"))

    @property
    def claude_model(self) -> str:
        return self.raw.get("claude", {}).get("model", "claude-sonnet-4-6")

    @property
    def thresholds(self) -> dict[str, Any]:
        return self.raw.get("thresholds", {})

    @property
    def vault_layout(self) -> dict[str, Any]:
        return self.raw.get("vault_layout", {})

    @property
    def rag_index_path(self) -> Path:
        return self._resolve(self.raw.get("rag", {}).get("index_path", "data/rag_index"))

    @property
    def rag_params(self) -> dict[str, Any]:
        return self.raw.get("rag", {})


def load_config(path: Path | None = None) -> Config:
    """Читает config.yaml (utf-8). Бросает FileNotFoundError, если файла нет."""
    cfg_path = path or CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Config(raw=data)


def save_vault_path(vault_path: Path, path: Path | None = None) -> None:
    """Однократно записывает путь к vault в config.yaml (правило: не хардкодить)."""
    cfg_path = path or CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data["vault_path"] = str(vault_path)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
