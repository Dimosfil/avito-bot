from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage import RuntimeStore


def load_json_file(path: Path, *, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def normalize_chat_ids(chat_ids: list[Any]) -> set[str]:
    return {str(chat_id).strip() for chat_id in chat_ids if str(chat_id).strip()}


def load_autoreply_pending(store: RuntimeStore, legacy_path: Path) -> dict[str, dict[str, Any]]:
    data = store.get_state("autoreply_pending")
    if data is None:
        data = load_json_file(legacy_path, default={}) if legacy_path.exists() else {}
        if isinstance(data, dict):
            store.set_state("autoreply_pending", data)
    if not isinstance(data, dict):
        return {}
    pending: dict[str, dict[str, Any]] = {}
    for chat_id, item in data.items():
        if isinstance(chat_id, str) and isinstance(item, dict):
            pending[chat_id] = item
    return pending


def write_autoreply_pending(store: RuntimeStore, legacy_path: Path, pending: dict[str, dict[str, Any]]) -> None:
    store.set_state("autoreply_pending", pending)
    write_json_file(legacy_path, pending)


def save_autoreply_pending_item(
    store: RuntimeStore,
    legacy_path: Path,
    chat_id: str,
    item: dict[str, Any],
) -> None:
    pending = load_autoreply_pending(store, legacy_path)
    pending[chat_id] = item
    write_autoreply_pending(store, legacy_path, pending)


def clear_autoreply_pending(store: RuntimeStore, legacy_path: Path, chat_id: str) -> None:
    pending = load_autoreply_pending(store, legacy_path)
    if chat_id not in pending:
        return
    del pending[chat_id]
    if pending:
        write_autoreply_pending(store, legacy_path, pending)
    else:
        store.set_state("autoreply_pending", {})
        legacy_path.unlink(missing_ok=True)


def load_autoreply_enabled(store: RuntimeStore, legacy_path: Path) -> bool:
    data = store.get_state("autoreply_enabled")
    if data is None:
        legacy = load_json_file(legacy_path, default={}) if legacy_path.exists() else {}
        data = bool(isinstance(legacy, dict) and legacy.get("enabled") is True)
        store.set_state("autoreply_enabled", data)
    return bool(data)


def save_autoreply_enabled(store: RuntimeStore, legacy_path: Path, enabled: bool) -> None:
    store.set_state("autoreply_enabled", enabled)
    write_json_file(legacy_path, {"enabled": enabled})


def load_bot_control_state(
    store: RuntimeStore,
    legacy_path: Path,
) -> tuple[set[str], set[str], set[str], set[str]]:
    data = store.get_state("bot_control")
    if data is None and legacy_path.exists():
        data = load_json_file(legacy_path, default={})
        if isinstance(data, dict):
            store.set_state("bot_control", data)
    if not isinstance(data, dict):
        return set(), set(), set(), set()

    return (
        _string_set(data.get("known_chat_ids", [])),
        _string_set(data.get("known_item_keys", [])),
        _string_set(data.get("manager_takeover_chat_ids", [])),
        _string_set(data.get("explicit_manager_takeover_chat_ids", [])),
    )


def save_bot_control_state(
    store: RuntimeStore,
    legacy_path: Path,
    *,
    known_chat_ids: set[str],
    known_item_keys: set[str],
    manager_takeover_chat_ids: set[str],
    explicit_manager_takeover_chat_ids: set[str],
) -> None:
    data = {
        "known_chat_ids": sorted(known_chat_ids),
        "known_item_keys": sorted(known_item_keys),
        "manager_takeover_chat_ids": sorted(manager_takeover_chat_ids),
        "explicit_manager_takeover_chat_ids": sorted(explicit_manager_takeover_chat_ids),
    }
    store.set_state("bot_control", data)
    write_json_file(legacy_path, data)


def load_qualified_buying_chat_ids(store: RuntimeStore, state_key: str) -> set[str]:
    data = store.get_state(state_key)
    if isinstance(data, list):
        return normalize_chat_ids(data)
    if isinstance(data, dict):
        return normalize_chat_ids(data.get("chat_ids", []))
    return set()


def save_qualified_buying_chat_ids(store: RuntimeStore, state_key: str, chat_ids: set[str]) -> None:
    store.set_state(state_key, sorted(chat_ids))


def load_processed_inbound_messages(store: RuntimeStore, state_key: str) -> dict[str, str]:
    data = store.get_state(state_key)
    if not isinstance(data, dict):
        return {}
    return {str(chat_id): str(message_key) for chat_id, message_key in data.items() if chat_id and message_key}


def mark_processed_inbound_message(store: RuntimeStore, state_key: str, state: dict[str, str], chat_id: str, key: str) -> None:
    state[chat_id] = key
    store.set_state(state_key, state)


def load_notified_message_keys(store: RuntimeStore, state_key: str) -> dict[str, set[str]]:
    data = store.get_state(state_key)
    if not isinstance(data, dict):
        return {}
    result: dict[str, set[str]] = {}
    for chat_id, message_keys in data.items():
        if not chat_id or not isinstance(message_keys, list):
            continue
        result[str(chat_id)] = {str(message_key) for message_key in message_keys if message_key}
    return result


def save_notified_message_keys(store: RuntimeStore, state_key: str, state: dict[str, set[str]]) -> None:
    data = {chat_id: sorted(message_keys)[-100:] for chat_id, message_keys in state.items() if message_keys}
    store.set_state(state_key, data)


def mark_notified_message_key(
    store: RuntimeStore,
    state_key: str,
    state: dict[str, set[str]],
    chat_id: str,
    key: str,
) -> None:
    state.setdefault(chat_id, set()).add(key)
    save_notified_message_keys(store, state_key, state)


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if item}
