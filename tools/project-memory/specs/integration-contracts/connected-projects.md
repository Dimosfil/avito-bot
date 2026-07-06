# Connected Projects And External Services

## Purpose

This register records external services, documentation, APIs, and sibling
systems that affect `avito-bot` behavior.

## Avito

Role: first production channel target for Module 2 AI conversation automation.

Canonical sources:

- Developer portal: `https://developers.avito.ru/`
- API key/account page: `https://www.avito.ru/professionals/api`
- Messenger API documentation:
  `https://developers.avito.ru/api-catalog/messenger/documentation`
- Auth API documentation:
  `https://developers.avito.ru/api-catalog/auth/documentation`

Data/API contract:

- Avito provides OAuth/token-based API access.
- Messenger API provides chat list, chat details, message list, send message,
  mark read, webhook subscribe, and webhook unsubscribe operations.
- Incoming Avito messages must be normalized into the project's platform-neutral
  conversation/message model.

Access and privacy boundary:

- Never commit Avito `client_id`, `client_secret`, access tokens, refresh
  tokens, account IDs, customer messages, or webhook secrets.
- Store credentials only in local environment/config storage outside git.
- Treat Avito customer messages as private lead data.

Current decision:

- Start implementation with an Avito-compatible local/test adapter.
- Add the real Avito adapter only after API keys and Messenger API permissions
  are confirmed.

Known caveat:

- The Avito `professionals/api` page indicates that a tariff can provide API
  keys. The Messenger API documentation separately states subscription-level
  constraints for chat/message API access. Treat key availability and Messenger
  API permission as separate checks.

## DeepSeek

Role: first AI provider for review-first sales reply drafts in Module 2.

Canonical sources:

- API docs: `https://api-docs.deepseek.com/`
- Chat completions API:
  `https://api-docs.deepseek.com/api/create-chat-completion`
- Models and pricing:
  `https://api-docs.deepseek.com/quick_start/pricing`

Data/API contract:

- The project calls the OpenAI-compatible
  `POST https://api.deepseek.com/chat/completions` endpoint.
- Default model is `deepseek-v4-flash`.
- Thinking mode is disabled for short draft replies.
- The assistant returns a draft only; the app does not auto-send AI output.

Access and privacy boundary:

- Never commit `DEEPSEEK_API_KEY`.
- Customer conversations sent to DeepSeek are private lead data and should be
  minimized to the selected chat context needed for a reply draft.
- Do not store raw DeepSeek prompts or responses in project memory.

Current decision:

- Use `AI_PROVIDER=deepseek` as the default AI draft provider.
- Keep provider code behind provider clients and factory selection in
  `app/main.py`; keep business prompt logic in `app/assistant.py`.

## Codex App Server

Role: optional fallback AI provider for review-first and automatic sales
replies in Module 2 when DeepSeek is primary and a Codex-compatible local or
remote app server is available.

Data/API contract:

- Primary production policy is `AI_PROVIDER=deepseek`; when
  `CODEX_APP_SERVER_BASE_URL` is configured, Codex App Server acts as the
  fallback if DeepSeek fails.
- Direct selection with `AI_PROVIDER=codex_app_server` remains available for
  diagnostics or explicitly Codex-backed runs.
- Configure `CODEX_APP_SERVER_BASE_URL` to an OpenAI-compatible API base that
  exposes `POST /chat/completions`.
- Optional settings: `CODEX_APP_SERVER_API_KEY` and
  `CODEX_APP_SERVER_MODEL`.
- The app sends the same `messages`, `temperature`, `max_tokens`, and
  non-streaming chat-completion payload shape used by other providers.

Access and privacy boundary:

- Never commit `CODEX_APP_SERVER_API_KEY`.
- Treat customer conversations sent to the Codex App Server as private lead
  data; only the current chat context needed for a reply should be sent.
- Do not store raw Codex App Server prompts or responses in project memory.

## Bothost

Role: current public Docker hosting target for the Module 2 MVP web runtime.

Canonical runtime:

- GitHub source: `https://github.com/Dimosfil/avito-bot`.
- Runtime source of truth: project `Dockerfile`.
- Public domain: `https://avitobot.bothost.tech`.
- Health endpoint: `https://avitobot.bothost.tech/api/health`.

Current hosting decision:

- Bothost may show the app under a platform/template category such as `VK` /
  `Vk_api`, but that category is not the application contract. The service must
  run from the repository Dockerfile.
- Enable domain access for the app.
- Set the web application port to `8000`.
- Leave the panel's main file / entry point field empty for Dockerfile
  deployments; the Dockerfile `CMD` starts `uvicorn app.main:app`.
- Keep `PORT=8000` unless Bothost injects another runtime port.

Deployment environment contract:

- Required variables: `PORT`, `AI_PROVIDER`, `DEEPSEEK_API_KEY`,
  `DEEPSEEK_MODEL`, `AVITO_CLIENT_ID`, and `AVITO_CLIENT_SECRET`.
- Optional variables: `HOST_PORT`, `AVITO_USER_ID`, `AVITO_WEBHOOK_URL`,
  `CODEX_APP_SERVER_BASE_URL`, `CODEX_APP_SERVER_API_KEY`, and
  `CODEX_APP_SERVER_MODEL`.

Access and privacy boundary:

- Never store real deployment secret values in project memory, docs, committed
  examples, screenshots, logs, or chat.
- Store real values only in Bothost environment variables, local ignored `.env`
  files, or another approved secret store.

## ai_logger

Role: external runtime diagnostics and log delivery package for Module 2.

Canonical sources:

- Local checkout: `D:\AI\ai_logger`
- Package name: `ai-logger`
- Python import package: `ai_logger`

Data/API contract:

- `avito-bot` records compact runtime events through `_record_admin_log(...)`.
- `app/admin_logging.py` keeps the existing `/api/admin/logs` in-memory view
  and forwards sanitized events to `ai_logger.Logger` when the external package
  is installed. If it is unavailable, the app uses a built-in compatible
  fallback for the admin buffer and JSONL delivery so Docker images remain
  self-contained.
- `ai_logger.LogAggregator` owns plugin delivery to JSONL, HTTP, or the
  separate ingest server when the external package is installed. The built-in
  fallback supports the local JSONL path and admin in-memory buffer.
- Configure `AI_LOGGER_SERVER_URL` to send records to the standalone
  `ai_logger` server `/ingest`; configure `AI_LOGGER_JSONL_PATH` for direct
  local JSON Lines output.

Access and privacy boundary:

- Never send raw Avito credentials, AI provider keys, bearer tokens, cookies, or
  full customer transcripts through diagnostic log detail.
- Keep log details compact and sanitized before forwarding to `ai_logger`.
- Treat JSONL fallback files as runtime artifacts, not project memory.

Current decision:

- Do not require the local checkout as an install dependency for `avito-bot`;
  machine-local file dependencies break Dockerfile-only builds and hosted
  deployments.
- Preserve existing `avito-bot` admin log API while using `ai_logger` as an
  optional external logging direction.
