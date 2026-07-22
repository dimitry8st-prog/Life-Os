"""Life OS — точка входа конвейера захвата знаний.

Запуск:
    python capture.py <url | путь_к_PDF | путь_к_txt>
    python capture.py --batch файл_со_списком.txt   (по одному источнику на строку)

Конвейер: извлечение -> Claude API -> заметка в vault -> SQLite -> RAG.
Ошибки отдельных материалов логируются и не прерывают пакет.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

from src.config import load_config, save_vault_path
from src.db import init_db
from src.logging_setup import setup_logging
from src.pipeline import prepare_vault, run_pipeline


def ensure_vault_path() -> Path:
    """Правило CLAUDE.md: путь к vault спрашиваем один раз и пишем в конфиг."""
    cfg = load_config()
    if cfg.vault_path:
        return cfg.vault_path
    entered = input("Путь к хранилищу Obsidian (например C:/Users/.../ObsidianVault): ").strip()
    vault = Path(entered)
    save_vault_path(vault)
    print(f"Сохранено в config.yaml: vault_path = {vault}")
    return vault


def report(source: str, res) -> None:
    if res.status == "failed":
        print(f"[ОШИБКА]   {source}: {res.error}")
    elif res.status == "duplicate":
        print(f"[ДУБЛИКАТ] {source}")
    else:
        where = "в /Areas" if res.status == "filed" else "в /Inbox"
        print(f"[OK]       {source} -> {res.note_path} "
              f"(область: {res.area}, уверенность: {res.confidence:.2f}, {where})")
        if res.related:
            print(f"           связи: {', '.join(t for _, t, _ in res.related)}")
        if res.proposed_tags:
            print(f"           предложены новые теги (нужно одобрение): "
                  f"{', '.join(res.proposed_tags)}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="capture", description="Life OS — захват материала")
    parser.add_argument("source", help="URL, путь к файлу или (с --batch) список источников")
    parser.add_argument("--batch", action="store_true",
                        help="источник — текстовый файл со списком (по строке на источник)")
    args = parser.parse_args()

    load_dotenv()
    cfg = load_config()
    log = setup_logging(cfg.log_dir, cfg.raw.get("logging", {}).get("level", "INFO"))
    init_db(cfg.db_path)
    vault = ensure_vault_path()
    prepare_vault(vault, cfg)

    sources = [args.source]
    if args.batch:
        sources = [
            line.strip()
            for line in Path(args.source).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]

    failures = 0
    for src in sources:
        res = run_pipeline(src, cfg, vault)
        report(src, res)
        failures += res.status == "failed"

    log.info("Пакет завершён: %d источников, %d ошибок", len(sources), failures)
    return 1 if failures == len(sources) else 0


if __name__ == "__main__":
    raise SystemExit(main())
