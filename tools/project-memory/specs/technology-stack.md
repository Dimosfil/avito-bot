# Technology Stack

Last reviewed: 2026-07-15

Canonical source: this file
Linked from: README.md

This is project documentation. Keep business rules, feature algorithms, workflow
contracts, state machines, and verification guarantees in project memory; keep
stack facts, commands, runtime assumptions, and operational notes here.

## Summary

- Primary stack: Python, FastAPI, static HTML/CSS/JavaScript, Avito HTTP API,
  configurable AI chat completion providers.
- Runtime model: local ASGI web app served by Uvicorn.
- Current confidence: verified from `pyproject.toml`, source files, and tests.

## Components

| Layer | Technology | Evidence | Notes |
| --- | --- | --- | --- |
| Language/runtime | Python 3.14 local, project requires >=3.12 | `pyproject.toml`, `python --version` | Python 3.14.3 used during setup. |
| Frontend | Static HTML/CSS/JavaScript | `app/static/` | No frontend build step yet. Shared browser helpers are split across `api.js`, `qualification.js`, and the page coordinator `app.js`. |
| Backend/API | FastAPI | `app/main.py`, `app/schemas.py`, `app/runtime_state.py`, `app/runtime_services.py`, `app/autoreply_logic.py`, `app/process_unread.py`, `app/autoreply_worker.py`, `app/avito_sync.py`, `app/reply_strategy.py`, `app/manager_notifications.py`, `app/manager_notification_service.py`, `app/ai_factory.py`, `app/http_errors.py`, `app/admin_logging.py`, `pyproject.toml` | Serves API and static UI. `app/main.py` is the composition root and compatibility facade; endpoint registration is grouped by router objects, while schemas, runtime state, runtime store/backup helpers, unread-processing use case, worker lifecycle, Avito sync/cache logic, reply-strategy selection, manager notification orchestration, AI factory, HTTP error mapping, and admin/runtime logging are separate modules. |
| Avito client | httpx | `app/avito_client.py`, `pyproject.toml` | Uses official Avito HTTP endpoints. |
| AI provider clients | httpx | `app/deepseek_client.py`, `app/codex_app_server_client.py`, `app/ai_client.py`, `app/assistant.py`, `pyproject.toml` | DeepSeek is the primary provider for short sales-assistant drafts; Codex App Server is an optional OpenAI-compatible fallback. |
| Data/storage | Runtime store with SQLite fallback and PostgreSQL support | `app/storage.py`, `app/storage_queries.py`, `app/runtime_state.py`, `app/main.py`, `tools/migrate_runtime_storage.py`, `.env.example` | Stores bot runtime state, Avito sync snapshots, manager actions, and backups. SQL statements live in `app/storage_queries.py`; `RuntimeStore` owns execution and row mapping. `DATABASE_URL` selects PostgreSQL; otherwise SQLite uses `SHARED_DIR` when available or `.codex-runtime/`. Existing SQLite runtime data can be copied into PostgreSQL with `uv run python tools/migrate_runtime_storage.py`. The manager UI opens from stored chats/messages first; `AVITO_LIVE_SYNC_ENABLED=false` keeps the UI in PostgreSQL/SQLite cache mode and disables live Avito polling/sending controls. |
| Build/package | uv | `pyproject.toml`, `uv.lock` | `uv sync` creates `.venv`. |
| Test/quality | pytest, compileall | `tests/`, `pyproject.toml` | Initial smoke tests exist. |
| Deployment/runtime | Uvicorn local dev server, local `.release/` runtime, and Docker Compose host runtime | README.md, `tools/AGENT_RUNBOOK.md`, `tools/deploy-local-release.ps1`, `Dockerfile`, `docker-compose.yml` | Local production deploy copies tested source into ignored `.release/` and runs without `--reload`; Docker runs the app in one container and bind-mounts `.codex-runtime/`. |
| Operator automation | Windows PowerShell 5.1-compatible scripts | `tools/avito-autoload/`, `tools/AGENT_RUNBOOK.md` | Generates regional Avito XML feeds and operates official Autoload endpoints with credentials read from environment variables. |

## Commands

| Purpose | Command | Evidence |
| --- | --- | --- |
| Install | `uv sync` | README.md |
| Run | `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` | README.md |
| Test | `uv run pytest` | README.md |
| Compile check | `uv run python -m compileall app tests` | README.md |
| Local release deploy | `.\tools\deploy-local-release.ps1` | README.md, `tools/AGENT_RUNBOOK.md` |
| Host Docker run | `docker compose up -d --build` | README.md, `tools/AGENT_RUNBOOK.md`, `docker-compose.yml` |
| Generate Avito regional feed | `.\tools\avito-autoload\New-AvitoRegionalFeed.ps1 ...` | `tools/avito-autoload/README.md` |
| Operate Avito Autoload | `.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 -Action ...` | `tools/avito-autoload/README.md` |

## External Services

| Service | Role | Evidence | Boundary |
| --- | --- | --- | --- |
| Avito API | First production channel for chats/messages plus a separate regional Autoload operator workflow | `tools/project-memory/specs/integration-contracts/avito-api.md`, `tools/project-memory/specs/integration-contracts/avito-autoload.md` | Credentials in env only; Messenger stays behind the channel adapter, while listing publication uses isolated operator scripts. |
| DeepSeek API | Default AI draft provider for sales replies | `tools/project-memory/specs/integration-contracts/connected-projects.md`, `app/deepseek_client.py` | API key in env only; selected with `AI_PROVIDER=deepseek`. |
| Codex App Server | Optional local/remote AI draft fallback | `tools/project-memory/specs/integration-contracts/connected-projects.md`, `app/codex_app_server_client.py`, `app/ai_client.py` | OpenAI-compatible chat-completions endpoint used as a fallback when DeepSeek is primary and `CODEX_APP_SERVER_BASE_URL` is configured; can still be selected directly with `AI_PROVIDER=codex_app_server`. |

## Gaps

- Full platform-neutral conversation domain storage is not complete; current
  persistence stores runtime state and Avito sync snapshots.
- Platform-neutral local/test channel adapter is not implemented.
- Final persisted manager notification and handoff workflow is not implemented.
- Public HTTPS webhook hosting is not configured.
- External production hosting is not configured; current production runtimes are
  the project-local `.release/` folder and the host Docker Compose service.
- Real Avito Messenger permission must be verified with credentials.
