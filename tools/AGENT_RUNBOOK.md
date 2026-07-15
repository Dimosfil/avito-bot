# Agent Runbook

Every command should be copy-pasteable from the project root.

## Install

```powershell
uv sync
```

## Run

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Local Release

The local production runtime is `.release/` inside the project root. Deploy only
through the guarded script so the source/dev tree is tested before the release
copy is replaced:

```powershell
.\tools\deploy-local-release.ps1
```

Default release URL:

```text
http://127.0.0.1:8010
```

Production runtime state is business-critical. The deploy script must preserve
`.release/.codex-runtime/` across releases, including server-side autoreply,
pending autoreply, and manager takeover state. If there is no previous
production runtime state, seed it from the development `.codex-runtime/` before
starting the release. Do not report `gi prod` or `gi reboot` as successful when
the server-side autoreply was enabled before the operation but is disabled
afterward.

## Host Docker

```powershell
Copy-Item .\env.docker.example .\.env
docker compose up -d --build
```

Default Docker URL:

```text
http://127.0.0.1:8000
```

Docker keeps runtime state in the host `.codex-runtime/` folder through a bind
mount when external storage is not configured. Preserve this folder across
container rebuilds and restarts. On Bothost production, prefer managed
PostgreSQL through `DATABASE_URL`; if shared files are enabled through
`SHARED_DIR`, SQLite and backups fall back to `$SHARED_DIR/avito-bot/`.

## Bothost Deployment

Current Bothost deployment settings:

- App display name: `AvitoBot`.
- Source: GitHub repository `https://github.com/Dimosfil/avito-bot`.
- Runtime source: `Dockerfile`.
- Template/category shown by Bothost: `VK` / `Vk_api`. This is only a hosting
  panel category; the app runtime is still defined by the project Dockerfile.
- Domain access: enabled.
- Public domain: `avitobot.bothost.tech`.
- Web application port: `8000`.
- Main file / entry point: leave empty for Dockerfile deployments.
- Region shown by Bothost: `Новосибирск 7 (nsk7)`, `Россия`.

Required deployment environment variables:

```text
API_HOST=0.0.0.0
API_PORT=8000
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=<secret>
DEEPSEEK_MODEL=deepseek-v4-flash
AVITO_CLIENT_ID=<secret>
AVITO_CLIENT_SECRET=<secret>
DATABASE_URL=<Bothost PostgreSQL connection string>
```

Optional or currently blank variables:

```text
HOST_PORT=8000
PORT=
AVITO_USER_ID=
AVITO_WEBHOOK_URL=
CODEX_APP_SERVER_BASE_URL=
CODEX_APP_SERVER_API_KEY=
CODEX_APP_SERVER_MODEL=codex
AVITO_DATABASE_PATH=
AVITO_BACKUP_DIR=
AVITO_BACKUP_INTERVAL_SECONDS=21600
AVITO_BACKUP_RETENTION_COUNT=14
```

Bothost health check URL:

```text
https://avitobot.bothost.tech/api/health
```

Useful commands:

```powershell
docker compose ps
docker compose logs -f avito-bot
docker compose down
```

## Test

```powershell
uv run pytest
uv run python -m compileall app tests
```

## Build

```powershell
# TODO
```

## Smoke Check

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/config/status"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/storage/status"
```

Expected result:

```text
Health returns {"status":"ok"}. Config status shows booleans and never prints
the Avito client secret. Storage status shows the active backend, backup
directory, and latest backup path without printing database credentials.
```

## Logs

```powershell
# TODO
```

## Environment Notes

- Use `.env` or user environment variables for `AVITO_CLIENT_ID` and
  `AVITO_CLIENT_SECRET`.
- Select the AI provider with `AI_PROVIDER`; supported values are `deepseek`
  and `codex_app_server`.
- For DeepSeek, use `.env` or user environment variables for `DEEPSEEK_API_KEY`.
  Optional model override: `DEEPSEEK_MODEL`; default is `deepseek-v4-flash`.
- For Codex App Server, set `CODEX_APP_SERVER_BASE_URL` to an OpenAI-compatible
  API base that exposes `/chat/completions`. Optional settings:
  `CODEX_APP_SERVER_API_KEY` and `CODEX_APP_SERVER_MODEL`.
- `API_HOST` and `API_PORT` are the preferred Docker host/port variables for
  Docker deployments. Use `API_HOST=0.0.0.0` and `API_PORT=8000`.
- `PORT` is also supported when a hosting platform injects it. Local Docker
  Compose uses `HOST_PORT=8000` for the browser URL.
- `DATABASE_URL` enables PostgreSQL runtime storage. Leave it blank for local
  SQLite.
- `AVITO_DATABASE_PATH` overrides the SQLite file path.
- `AVITO_BACKUP_DIR` overrides backup storage. If it is blank and `SHARED_DIR`
  exists, backups go to `$SHARED_DIR/avito-bot/backups`; otherwise they go to
  `.codex-runtime/backups`.
- Keep `.env` out of git.
- `AVITO_USER_ID` is optional for startup; the app tries to infer it from
  `GET /core/v1/accounts/self`.
- Real Avito webhooks require a public HTTPS URL and should point to
  `/webhooks/avito/messenger`.

## Avito Regional Autoload

Regional listing publication is an operator workflow, separate from the
conversation bot runtime. Full instructions are in
`tools/avito-autoload/README.md`.

Generate a local XML feed from a reviewed manifest:

```powershell
.\tools\avito-autoload\New-AvitoRegionalFeed.ps1 `
  -ManifestPath .\tools\avito-autoload\regional-services.local.json `
  -OutputPath .\tools\avito-autoload\regional-services.local.xml
```

Check credentials and Autoload access without changing remote state:

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 -Action CheckAccess
```

Initialize a missing profile in the disabled state:

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action InitializeProfile `
  -ConfirmChange
```

After hosting the XML at a controlled public HTTPS URL, configure the profile
disabled first, inspect it, then repeat with `-AutoloadState Enabled`:

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action SetProfile `
  -FeedUrl "https://example.com/feeds/avito-services.xml" `
  -FeedName "Regional services" `
  -AutoloadState Disabled `
  -Rate 1 `
  -TimeSlot 12 `
  -ConfirmChange
```

Start and monitor a real upload only after reviewing `ListingFee`, the feed,
and the remote profile:

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action StartUpload `
  -ConfirmPublish

.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action WatchCurrentUpload
```

Do not report publication success from the initial `200` response. Wait for a
terminal upload status and an item section such as `success_added`, then verify
the returned public listing URL and intended city. Use `ListingFee=Package` for
guarded trials; `PackageBBL` and `BBL` can spend wallet funds.
