# Runtime Observability Architecture

Last reviewed: 2026-07-06

This specification records backend architecture boundaries for runtime logging
and storage query organization in Module 2.

## Runtime Log Pipeline

- Runtime diagnostic log delivery uses the `ai-logger` package from Git via
  `pyproject.toml` / `uv.lock`. `avito-bot` must not depend on the sibling
  `D:\AI\ai_logger` checkout path because Dockerfile-only hosted deployments
  cannot access machine-local paths.
- Application code records compact events through the local
  `_record_admin_log(...)` boundary, but it must not implement plugin fan-out,
  server delivery, file delivery, retry buffering, or backend-specific
  conversion inline.
- `app/admin_logging.py` is a compatibility bridge: it keeps the existing
  `/api/admin/logs` in-memory buffer and sanitizes event details before
  forwarding them to the external `ai_logger.Logger`.
- `ai_logger.LogAggregator` or the built-in fallback aggregator owns delivery
  to configured plugins. Plugin failures are retained and must not break lead
  processing.
- `AI_LOGGER_*` environment variables configure forwarding. Use
  `AI_LOGGER_JSONL_PATH` for JSON Lines, `AI_LOGGER_SERVER_URL` for the separate
  `ai_logger` ingest server, and `AI_LOGGER_SERVER_TOKEN` when the ingest server
  requires bearer authentication.
- `/api/admin/logs` exposes only sanitized log details. Secret-like keys such as
  tokens, API keys, passwords, and secrets must be redacted before the response
  leaves the backend.
- The admin buffer remains in memory for current runtime diagnostics. Durable
  business events, handoff records, manager actions, and Avito sync data remain
  in `RuntimeStore`.

## Lead Processing Event Model

The logging module is diagnostic, but it must mirror the key Module 2 process
boundaries so managers and developers can understand why the bot acted or did
not act.

Required event categories:

- `autoreply_start` and `autoreply_stop`: record backend auto-reply lifecycle
  changes with the effective polling interval.
- `live_sync_blocked`: record attempts to use live Avito sync when
  `AVITO_LIVE_SYNC_ENABLED=false`.
- `config_error`, `avito_http_status_error`, and `avito_request_failed`: record
  integration failures without exposing credentials or raw tokens.
- `chat_scan_start` and `chat_scan_end`: record every unread-processing scan
  with compact counts and duration.
- `chats_persisted`, `messages_persisted`, `chat_persistence_failed`, and
  `message_persistence_failed`: record cache persistence results without full
  payloads.
- `message_accepted`, `ai_draft_decision`, `ai_auto_reply_sent`, and
  `chat_processing_failed`: record the AI reply path and failures.
- `handoff_detected` and `manager_notification_attempted`: record handoff and
  manager notification outcomes.
- `manual_takeover_changed`, `chat_manager_folder`, and `chat_skipped`: record
  manual control and skip reasons.
- `backup_failed`, `autoreply_worker_failed`, `webhook_received`, and
  `webhook_persistence_failed`: record supporting runtime failures and webhook
  intake.

Business process boundaries:

- New inbound Avito message: persist the chat and message snapshot first.
- AI auto-reply path: record decision context, send result, and any Avito error.
- Handoff path: record handoff reason, transfer reply result, Telegram
  notification result, and manager-action persistence.
- Manual takeover path: record state change and skip reason when auto-reply does
  not answer.
- Cache-only path: record that live actions were blocked and that UI data came
  from stored runtime state.

Diagnostic log records must stay compact. Full chat transcripts, large API
payloads, screenshots, raw secrets, and generated model outputs do not belong in
admin logs. Store durable business facts through `RuntimeStore` and expose only
small references or summaries in logs.

## Storage Query Boundary

- Fixed SQL statements are owned by `app/storage_queries.py`.
- `RuntimeStore` owns execution, connection handling, row mapping, backup/export
  orchestration, and backend selection between SQLite and PostgreSQL.
- New fixed SQL statements should be added as named constants or validated query
  helpers in `app/storage_queries.py`, not embedded inside storage methods.
- Cached Avito message lists must return the latest requested window of a long
  chat while preserving chronological order for rendering. This keeps manager
  history views focused on the current conversation tail rather than the oldest
  stored messages.

## Verification

- Logging behavior is covered by `tests/test_admin_logging.py`.
- Runtime store query behavior is covered by `tests/test_storage.py`, including
  the long-chat latest-message-window regression.
