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
mount. Preserve this folder across container rebuilds and restarts.

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
```

Expected result:

```text
Health returns {"status":"ok"}. Config status shows booleans and never prints
the Avito client secret.
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
- Keep `.env` out of git.
- `AVITO_USER_ID` is optional for startup; the app tries to infer it from
  `GET /core/v1/accounts/self`.
- Real Avito webhooks require a public HTTPS URL and should point to
  `/webhooks/avito/messenger`.
