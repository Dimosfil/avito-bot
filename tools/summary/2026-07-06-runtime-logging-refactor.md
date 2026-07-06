# Handoff Summary: Runtime Logging Refactor

## Current Goal

Project goal remains Module 2 MVP: receive or simulate incoming customer
requests, let AI handle first-line dialogue, detect handoff intent, notify a
manager, and allow manager takeover while preserving client messages.

This thread focused on fixing stale manager-message rendering, refactoring
runtime storage/logging boundaries, and restarting the Docker runtime.

## What Changed

- Fixed cached Avito message history for long chats. `RuntimeStore` now returns
  the latest requested message window while preserving chronological rendering
  order.
- Added `app/storage_queries.py` as the SQL source-of-truth for SQLite and
  PostgreSQL statements.
- Refactored `app/storage.py` so it owns execution, row mapping, backup/export,
  and backend selection, but no longer embeds large SQL blocks inline.
- Added `app/admin_logging.py` for bounded in-memory admin/runtime logs,
  sequence assignment, response shaping, and secret redaction.
- Refactored `app/main.py` to use `AdminLogBuffer` instead of owning raw deque,
  sequence, and sanitizer logic.
- Added `tests/test_admin_logging.py`.
- Updated `tests/test_main.py` to clear the new log buffer between tests.
- Updated `tests/test_storage.py` with the long-chat latest-window regression.
- Added `tools/project-memory/specs/runtime-observability-architecture.md`.
- Updated `tools/project-memory/specs/technology-stack.md` to include
  `admin_logging.py` and `storage_queries.py`.

## Verification

Last checks run successfully:

- `uv run pytest` -> 76 passed, 1 Starlette/httpx deprecation warning.
- `uv run python -m compileall app tests` -> passed.
- `git diff --check` -> passed with only CRLF warnings.

Docker was rebuilt and started:

- Command: `docker compose up -d --build`
- Container: `avito-bot-avito-bot-1`
- Status: healthy
- Local URL: `http://127.0.0.1:8000`
- `/api/health`: `{"status":"ok"}`
- Config status showed Avito, DeepSeek, and Telegram configured.
- Auto-reply status: enabled, no current error, task waiting between polling
  cycles.

## Current Working Tree

Expected changed files from this thread:

- `app/main.py`
- `app/storage.py`
- `app/admin_logging.py`
- `app/storage_queries.py`
- `tests/test_admin_logging.py`
- `tests/test_main.py`
- `tests/test_storage.py`
- `tools/project-memory/specs/technology-stack.md`
- `tools/project-memory/specs/runtime-observability-architecture.md`
- this summary file

There is also an untracked `.codex/` directory present from local tooling; it
was not touched as part of the product change.

## Remaining Work

- Deploy the refactor to the active Bothost service if production should receive
  it. Docker local runtime is updated; remote Bothost was not deployed in this
  thread.
- Expand logging beyond the current buffer: chat scan start/end, persistence,
  AI decisions, handoff, Telegram notifications, manual takeover changes, and
  skipped-chat reasons are now specified but not fully implemented as events.
- Consider normalizing the older `module-2-ai-conversations.md` mojibake text in
  a separate documentation cleanup batch if it blocks future agents.
