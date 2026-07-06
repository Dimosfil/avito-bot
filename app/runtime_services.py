from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from app import runtime_state
from app.config import Settings
from app.storage import RuntimeStore


def get_runtime_store(
    *,
    settings: Settings,
    root: Path,
    runtime_dir: Path,
    current_store: RuntimeStore | None,
    current_key: tuple[str, str, str] | None,
) -> tuple[RuntimeStore, tuple[str, str, str]]:
    candidate = RuntimeStore.from_settings(settings, root=root, runtime_dir=runtime_dir)
    candidate_key = candidate.cache_key()
    if current_store is None or current_key != candidate_key:
        candidate.ensure_schema()
        return candidate, candidate_key
    return current_store, current_key


async def backup_worker_loop(
    *,
    get_settings: Callable[[], Settings],
    get_store: Callable[[], RuntimeStore],
    activity: dict[str, Any],
    record_admin_log: Callable[[str, str, Any | None], None],
    error_detail: Callable[[Exception], object],
) -> None:
    while True:
        await asyncio.sleep(get_settings().backup_interval_seconds)
        try:
            store = get_store()
            store.create_backup(keep=get_settings().backup_retention_count)
        except Exception as exc:  # pragma: no cover - surfaced through storage status/logs
            activity["last_backup_error"] = error_detail(exc)
            record_admin_log("error", "backup_failed", {"error": error_detail(exc)})


def migrate_legacy_runtime_json_to_store(
    *,
    store: RuntimeStore,
    autoreply_pending_path: Path,
    autoreply_state_path: Path,
    bot_control_state_path: Path,
) -> None:
    if store.get_state("autoreply_pending") is None and autoreply_pending_path.exists():
        pending = runtime_state.load_json_file(autoreply_pending_path, default={})
        if isinstance(pending, dict):
            store.set_state("autoreply_pending", pending)
    if store.get_state("autoreply_enabled") is None and autoreply_state_path.exists():
        state = runtime_state.load_json_file(autoreply_state_path, default={})
        if isinstance(state, dict):
            store.set_state("autoreply_enabled", bool(state.get("enabled") is True))
    if store.get_state("bot_control") is None and bot_control_state_path.exists():
        state = runtime_state.load_json_file(bot_control_state_path, default={})
        if isinstance(state, dict):
            store.set_state("bot_control", state)
