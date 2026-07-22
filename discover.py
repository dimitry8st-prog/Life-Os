"""Автоматический поиск и добавление свежих материалов в Life OS."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from capture import ensure_vault_path, report
from src.config import PROJECT_ROOT, load_config
from src.db import init_db
from src.discovery import discover, load_seen, save_seen
from src.logging_setup import setup_logging
from src.pipeline import prepare_vault, run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Life OS — поиск свежих статей")
    parser.add_argument("--dry-run", action="store_true", help="только показать найденные материалы")
    args = parser.parse_args()

    load_dotenv()
    cfg = load_config()
    discovery_cfg = cfg.raw.get("discovery", {})
    log = setup_logging(cfg.log_dir, cfg.raw.get("logging", {}).get("level", "INFO"))
    state_path = PROJECT_ROOT / discovery_cfg.get("state_path", "data/discovery_state.json")
    seen = load_seen(state_path)
    candidates = discover(discovery_cfg, seen)

    if not candidates:
        print("Свежих релевантных материалов не найдено.")
        return 0
    for item in candidates:
        print(f"[{item.topic}] {item.title} — {item.source}\n  {item.url}")
    if args.dry_run:
        return 0

    init_db(cfg.db_path)
    vault = ensure_vault_path()
    prepare_vault(vault, cfg)
    failures = 0
    for item in candidates:
        result = run_pipeline(item.url, cfg, vault)
        report(item.url, result)
        if result.status in {"processed", "filed", "duplicate"}:
            seen.add(item.url)
        else:
            failures += 1
    save_seen(state_path, seen)
    log.info("Автопоиск завершён: %d кандидатов, %d ошибок", len(candidates), failures)
    return 1 if failures == len(candidates) else 0


if __name__ == "__main__":
    raise SystemExit(main())
