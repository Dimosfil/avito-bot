# avito-bot

`avito-bot` is a modular marketing and sales-assistant platform.

The long-term product idea is a platform where a business can connect only the
modules it needs:

- auto-posting for channels and blogs;
- AI first-line communication with potential clients;
- manager handoff and secretary-style assistance;
- follow-up messaging for people who previously contacted the business.

## Current Focus

The first module to build is Module 2: AI conversation automation.
The first production channel target is Avito. Until real Avito Messenger API
access is confirmed, development must use a local/test Avito adapter with the
same normalized conversation contract.

## Run Locally

Install dependencies:

```powershell
uv sync
```

Create local secrets from the template:

```powershell
Copy-Item .env.example .env
```

Fill `AVITO_CLIENT_ID` and `AVITO_CLIENT_SECRET` in `.env`, or set them as user
environment variables.

Start the app:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000
```

Run checks:

```powershell
uv run pytest
uv run python -m compileall app tests
```

## Local Release Runtime

Development happens in the project source tree. The local production runtime is
the ignored `.release/` folder in the same project directory. Deploy to it only
after the dev checks pass:

```powershell
.\tools\deploy-local-release.ps1
```

The script runs tests, creates a clean release copy, syncs production
dependencies, starts Uvicorn without `--reload`, and verifies health at:

```text
http://127.0.0.1:8010
```

## Host Docker Runtime

The project root can also run as a single Docker service. The container starts
FastAPI/Uvicorn, serves the static manager UI, and keeps bot runtime state in a
mounted `.codex-runtime/` folder unless external storage is configured.

Prepare host environment:

```powershell
Copy-Item .\env.docker.example .\.env
```

Fill `.env` with Avito credentials and the selected AI provider credentials.
For Docker hosting, use `API_HOST=0.0.0.0` and `API_PORT=8000`. `PORT` is also
supported when a platform injects it. Keep
`HOST_PORT=8000` for local Docker Compose unless the host already uses that
browser port.

For production state storage, prefer the managed PostgreSQL database from the
hosting panel and set `DATABASE_URL` to its connection string. If
`DATABASE_URL` is blank and the host provides shared files through `SHARED_DIR`,
the app stores SQLite state and backups under `$SHARED_DIR/avito-bot/`. If
neither is available, it falls back to `.codex-runtime/`.

Build and start:

```powershell
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:8000
```

Current Bothost deployment uses the repository `Dockerfile`, domain
`https://avitobot.bothost.tech`, and web application port `8000`. Leave the
hosting panel's main file / entry point field empty for Dockerfile deployments.
Check the public runtime at:

```text
https://avitobot.bothost.tech/api/health
```

Useful operations:

```powershell
docker compose ps
docker compose logs -f avito-bot
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/config/status"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/storage/status"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/storage/backup"
docker compose down
```

Migrate existing local SQLite runtime state into PostgreSQL before switching a
host to `DATABASE_URL`:

```powershell
$env:DATABASE_URL = "<postgresql connection string>"
uv run python tools/migrate_runtime_storage.py
```

Do not delete `.codex-runtime/` on a live host. It stores server-side autoreply,
pending autoreply, and manager takeover state when external storage is not
configured. When `DATABASE_URL` is set, the same state is stored in PostgreSQL.

## Runtime Storage And Backups

The app has a small persistent runtime store for bot state and Avito sync
snapshots:

- server-side autoreply enabled/disabled state;
- pending autoreply records used to survive restarts after marking a chat read;
- manager takeover state per chat/listing;
- last seen Avito chats and messages;
- manager and bot actions used as an audit trail.

Storage selection:

- `DATABASE_URL` set to PostgreSQL: use the managed PostgreSQL database. This is
  the recommended production option on Bothost because it survives container VM
  replacement.
- `DATABASE_URL` blank and `SHARED_DIR` available: use SQLite at
  `$SHARED_DIR/avito-bot/avito-bot.sqlite3` and backups under
  `$SHARED_DIR/avito-bot/backups`.
- No external storage variables: use local `.codex-runtime/avito-bot.sqlite3`
  and `.codex-runtime/backups`.

Automatic backups run every `AVITO_BACKUP_INTERVAL_SECONDS` seconds, default
`21600` or 6 hours, and keep `AVITO_BACKUP_RETENTION_COUNT` backups, default
`14`. For SQLite, backups are consistent `.sqlite3` copies. For PostgreSQL, the
app writes a JSON export of application tables; the database itself should also
be protected by the hoster's managed PostgreSQL retention.

MVP target:

- accept incoming customer messages from supported channels or local test
  adapters;
- answer first questions through AI using business context and guardrails;
- detect handoff triggers such as `хочу КП`, `хочу сделку`, or equivalent
  buying intent;
- notify a manager when a dialogue needs human attention;
- let a manager manually take over at any time;
- show the manager the live customer conversation state.

Supported production channels are planned as adapters: Avito, VK, MAX,
Telegram, Drom, and the organization's website, where APIs are available.

## Avito Access Notes

Avito has two separate access gates:

- the `professionals/api` page says a tariff can provide API access keys;
- the Messenger API documentation separately limits chat/message API access by
  subscription level.

For Services, the Messenger API documentation says chat automation is available
on `Расширенная` and `Максимальная`. The project should still start with a
local/test adapter so the core AI and manager handoff workflow can be built
before production Avito access is confirmed.

The current hello-world app can:

- check whether credentials are configured;
- request an Avito access token;
- read the authorized account through `core/v1/accounts/self`;
- request chats through Messenger API;
- read and send messages for a selected chat when API permissions allow it;
- request per-listing Avito item statistics for views, contacts, and favorites;
- generate an AI draft reply for a selected chat through the configured
  provider: `deepseek` or `codex_app_server`;
- process unread Avito chats on demand or through the UI `Auto reply` polling
  switch; when enabled, a backend worker checks Avito independently of the
  browser tab, reads latest messages, generates an AI reply, sends it when no
  handoff trigger is detected, marks the chat read, and returns bot-processing
  estimates such as accepted time, estimated reply time, sent time, and actual
  duration;
- let a manager switch an individual chat into manual takeover mode so
  auto-reply skips that chat while manual Avito messages remain available;
- show a statistics view that links known listing metric rows back to loaded
  client conversations when the chat payload exposes matching listing data;
- receive local Avito webhook payloads at `/webhooks/avito/messenger`.

AI replies can be review-first through `AI draft`, or automatic for unread Avito
chats while `Auto reply` is enabled in the UI. Handoff-trigger messages are not
auto-sent and remain visible for manager attention.

Bot behavior rules are centralized in `app/bot_rules.py`: handoff phrases,
prompt guardrails, and deterministic cleanup such as removing repeated greetings.

## Documentation

- Product and runtime instructions: `AGENTS.md`
- Project runbook: `tools/AGENT_RUNBOOK.md`
- Canonical technology stack inventory:
  `tools/project-memory/specs/technology-stack.md`
- Durable feature specs: `tools/project-memory/specs/`
- Active plan: `tools/project-memory/pending-tasks.md`
- Avito integration notes:
  `tools/project-memory/specs/integration-contracts/avito-api.md`
