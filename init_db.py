"""Life OS — инициализация: читает config.yaml, создаёт SQLite-БД по schema.sql.

Запуск:  python init_db.py
Критерий готовности фазы 0: скрипт отрабатывает без ошибок,
конфиг считывается, БД создаётся.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import load_config
from src.db import get_connection, init_db


def main() -> int:
    cfg = load_config()
    print(f"Проект: {cfg.raw.get('project_name', 'Life OS')}")
    print(f"Модель Claude: {cfg.claude_model}")
    print(f"Vault: {cfg.vault_path or 'НЕ ЗАДАН (будет запрошен при первом capture)'}")

    init_db(cfg.db_path)
    with get_connection(cfg.db_path) as conn:
        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
    print(f"БД создана: {cfg.db_path}")
    print(f"Таблицы: {', '.join(tables)}")

    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    print("Готово. Фаза 0: каркас работоспособен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
