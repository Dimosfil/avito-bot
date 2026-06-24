# Technology Stack

Last reviewed: 2026-06-24

Canonical source: this file
Linked from: README.md

This is project documentation. Keep business rules, feature algorithms, workflow
contracts, state machines, and verification guarantees in project memory; keep
stack facts, commands, runtime assumptions, and operational notes here.

## Summary

- Primary stack: Python, FastAPI, static HTML/CSS/JavaScript, Avito HTTP API.
- Runtime model: local ASGI web app served by Uvicorn.
- Current confidence: verified from `pyproject.toml`, source files, and tests.

## Components

| Layer | Technology | Evidence | Notes |
| --- | --- | --- | --- |
| Language/runtime | Python 3.14 local, project requires >=3.12 | `pyproject.toml`, `python --version` | Python 3.14.3 used during setup. |
| Frontend | Static HTML/CSS/JavaScript | `app/static/` | No frontend build step yet. |
| Backend/API | FastAPI | `app/main.py`, `pyproject.toml` | Serves API and static UI. |
| Avito client | httpx | `app/avito_client.py`, `pyproject.toml` | Uses official Avito HTTP endpoints. |
| Data/storage | In-memory webhook event list only | `app/main.py` | SQLite domain storage not implemented yet. |
| Build/package | uv | `pyproject.toml`, `uv.lock` | `uv sync` creates `.venv`. |
| Test/quality | pytest, compileall | `tests/`, `pyproject.toml` | Initial smoke tests exist. |
| Deployment/runtime | Uvicorn local dev server and local `.release/` runtime | README.md, `tools/AGENT_RUNBOOK.md`, `tools/deploy-local-release.ps1` | Local production deploy copies tested source into ignored `.release/` and runs without `--reload`. |

## Commands

| Purpose | Command | Evidence |
| --- | --- | --- |
| Install | `uv sync` | README.md |
| Run | `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` | README.md |
| Test | `uv run pytest` | README.md |
| Compile check | `uv run python -m compileall app tests` | README.md |
| Local release deploy | `.\tools\deploy-local-release.ps1` | README.md, `tools/AGENT_RUNBOOK.md` |

## External Services

| Service | Role | Evidence | Boundary |
| --- | --- | --- | --- |
| Avito API | First production channel for chats/messages | `tools/project-memory/specs/integration-contracts/avito-api.md` | Credentials in env only; API behind Avito client/adapter. |

## Gaps

- Persistent conversation storage is not implemented.
- AI provider boundary is not implemented.
- Final manager handoff UI is not implemented.
- Public HTTPS webhook hosting is not configured.
- External production hosting is not configured; current production runtime is
  the project-local `.release/` folder.
- Real Avito Messenger permission must be verified with credentials.
