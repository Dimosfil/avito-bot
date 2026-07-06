# Runtime Observability Architecture

Last reviewed: 2026-07-06

This specification records backend architecture boundaries for runtime logging
and storage query organization in Module 2.

## Admin Runtime Logs

- Admin/runtime log events are owned by `app/admin_logging.py`.
- API route code may record events through the shared log buffer, but it must
  not implement secret redaction, bounded retention, sequence assignment, or log
  response shaping inline.
- `/api/admin/logs` exposes only sanitized log details. Secret-like keys such as
  tokens, API keys, passwords, and secrets must be redacted before the response
  leaves the backend.
- The log buffer is intentionally in-memory for current runtime diagnostics.
  Durable business events, handoff records, manager actions, and Avito sync data
  remain in `RuntimeStore`.

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
- Future logging work should add process events for chat scan start/end,
  message persistence, AI draft decisions, handoff detection, Telegram
  notification attempts, manual takeover changes, and skipped-chat reasons.

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
