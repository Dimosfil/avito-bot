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
- Use `.env` or user environment variables for `DEEPSEEK_API_KEY`.
- Optional AI model override: `DEEPSEEK_MODEL`; default is
  `deepseek-v4-flash`.
- Keep `.env` out of git.
- `AVITO_USER_ID` is optional for startup; the app tries to infer it from
  `GET /core/v1/accounts/self`.
- Real Avito webhooks require a public HTTPS URL and should point to
  `/webhooks/avito/messenger`.
