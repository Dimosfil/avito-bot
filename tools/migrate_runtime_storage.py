from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.storage import APPLICATION_TABLES, RuntimeStore

RUNTIME_DIR = ROOT / ".codex-runtime"
DEFAULT_SQLITE_PATH = RUNTIME_DIR / "avito-bot.sqlite3"
DEFAULT_BACKUP_DIR = RUNTIME_DIR / "backups"


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate avito-bot runtime storage into DATABASE_URL.")
    parser.add_argument("--source-sqlite", type=Path, default=DEFAULT_SQLITE_PATH)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")
    if not args.source_sqlite.exists():
        raise SystemExit(f"Source SQLite database does not exist: {args.source_sqlite}")

    source = RuntimeStore(database_url=None, sqlite_path=args.source_sqlite, backup_dir=args.backup_dir)
    target = RuntimeStore(database_url=args.database_url, sqlite_path=None, backup_dir=args.backup_dir)

    migrate_legacy_runtime_json(source)
    export = source.export_data()
    source_counts = _counts(export)

    if args.dry_run:
        print(json.dumps({"dry_run": True, "source_counts": source_counts}, ensure_ascii=False, indent=2))
        return

    imported_counts = target.import_data(export)
    target_counts = _counts(target.export_data())
    print(
        json.dumps(
            {
                "dry_run": False,
                "source_counts": source_counts,
                "imported_counts": imported_counts,
                "target_counts": target_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def migrate_legacy_runtime_json(store: RuntimeStore) -> None:
    legacy_specs = (
        ("autoreply_pending", RUNTIME_DIR / "autoreply-pending.json", "raw"),
        ("autoreply_enabled", RUNTIME_DIR / "autoreply-state.json", "enabled_bool"),
        ("bot_control", RUNTIME_DIR / "bot-control-state.json", "raw"),
    )
    for state_key, path, mode in legacy_specs:
        if store.get_state(state_key) is not None or not path.exists():
            continue
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        store.set_state(state_key, bool(data.get("enabled") is True) if mode == "enabled_bool" else data)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _counts(export: dict[str, Any]) -> dict[str, int]:
    tables = export.get("tables", {})
    if not isinstance(tables, dict):
        return {table: 0 for table in APPLICATION_TABLES}
    return {table: len(rows) for table in APPLICATION_TABLES if isinstance((rows := tables.get(table, [])), list)}


if __name__ == "__main__":
    main()
