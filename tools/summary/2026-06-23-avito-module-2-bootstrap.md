# Handoff Summary: Module 2 Avito Bootstrap

## Product Direction

The project is a modular marketing and sales-assistant platform. The first
module to build is Module 2: AI first-line conversation automation with manager
handoff.

The target workflow is: incoming lead message, AI handles routine first
questions, trigger phrases such as `хочу КП` or `хочу сделку` request manager
handoff, and a manager can manually take over at any time.

## Avito Decision

Avito is the first production channel target.

Important distinction:

- `https://www.avito.ru/professionals/api` indicates that connecting a tariff can
  provide API access keys.
- `https://developers.avito.ru/api-catalog/messenger/documentation` separately
  states subscription-level requirements for Messenger API access.

Do not assume that having API keys means chat/message access is available. Check
real Messenger API scopes/permissions when credentials exist.

## Implementation Direction

Build the core module through a channel-adapter boundary:

- platform-neutral conversation and message model;
- local/test Avito-compatible adapter first;
- real Avito Messenger adapter after access is confirmed;
- AI provider behind an interface;
- handoff trigger detection configurable outside channel adapters;
- manager view/API for history and takeover.

## Durable Records Updated

- `README.md`
- `AGENTS.md`
- `tools/project-memory/specs/features/module-2-ai-conversations.md`
- `tools/project-memory/specs/business-rules/handoff-rules.md`
- `tools/project-memory/specs/integration-contracts/avito-api.md`
- `tools/project-memory/specs/integration-contracts/connected-projects.md`
- `tools/project-memory/pending-tasks.md`

## Next Useful Step

Choose the MVP stack and scaffold the first runnable service. Recommended
direction discussed in chat: Python, FastAPI, SQLite, local Avito-compatible
adapter, mock AI provider first, then real provider and real Avito adapter.

## 2026-06-23 Runnable Hello World

Implemented a first FastAPI hello-world integration console:

- backend entrypoint: `app/main.py`;
- Avito HTTP client: `app/avito_client.py`;
- env handling: `app/config.py`;
- UI: `app/static/index.html`, `app/static/app.js`, `app/static/styles.css`;
- tests: `tests/`;
- package/dependencies: `pyproject.toml`, `uv.lock`.

The app can check config, request an Avito token, read account info, list chats,
read messages, send text messages, mark chats read, and receive local webhook
payloads. Real Avito calls require `AVITO_CLIENT_ID` and `AVITO_CLIENT_SECRET`
from `.env` or process environment. At implementation time, the running Codex
process did not see those variables.

Verification:

- `uv sync`
- `uv run pytest`
- `uv run python -m compileall app tests`
- `git diff --check`
- local server health on `http://127.0.0.1:8001/api/health`

## 2026-06-23 Live Avito Access

After the user added Avito credentials to Windows User environment, the local
server was restarted with those variables loaded into the process. The app saw
`AVITO_CLIENT_ID` and `AVITO_CLIENT_SECRET`.

Live checks through the local API initially showed partial access, then
succeeded after a local response-shape fix:

- token check returned 200;
- account lookup returned 200;
- chat list lookup returned 200 and one chat for `limit=1`;
- selected chat message lookup now returns 200 with messages and metadata.

The intermediate `500` was caused by the local app expecting a bare list while
Avito returns `{ "messages": [...], "meta": ... }`.

No account metadata, chat content, customer data, access token, client id, or
client secret should be recorded in repository files or summaries.

## 2026-06-23 DeepSeek Assistant

Added a DeepSeek-backed AI assistant for review-first reply drafts:

- `app/deepseek_client.py` calls `https://api.deepseek.com/chat/completions`;
- default model is `deepseek-v4-flash`;
- thinking mode is disabled for short sales drafts;
- `app/assistant.py` builds the sales prompt and detects handoff phrases;
- UI has `DeepSeek`, `AI draft`, and `Use draft` controls.

Live checks succeeded:

- DeepSeek key was detected in environment;
- AI ping returned ok;
- AI draft generation returned a draft for a selected Avito chat.

AI output is not auto-sent. The manager must review the draft, click `Use
draft`, then explicitly send it.

## 2026-06-23 Conversation Timeline UI

Updated the Avito message view so managers can understand who wrote what and
when:

- messages are sorted chronologically before rendering;
- each day gets a date separator;
- each message shows role and time;
- Avito system messages, client messages, and manager messages use separate
  visual treatment;
- the timeline shows explicit start and latest-message markers.
- after config check, the UI loads Avito chats by default on page open.

AI prompt building also sorts messages chronologically before sending the recent
conversation to DeepSeek.
