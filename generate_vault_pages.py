"""Life OS — пересборка HTML-страниц vault для просмотра в браузере.

Запуск:  python generate_vault_pages.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import load_config
from src.vault_pages import generate_vault_pages


def main() -> int:
    cfg = load_config()
    vault = cfg.vault_path
    if not vault:
        print("Ошибка: vault_path не задан в config.yaml")
        return 1
    n = generate_vault_pages(vault)
    print(f"Готово: {n} HTML-страниц в {vault}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
