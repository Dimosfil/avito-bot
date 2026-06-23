# Avito API Integration

## Purpose

Avito is the first planned production channel for Module 2 AI conversation
automation.

## Official Sources

- Developer portal: `https://developers.avito.ru/`
- API key/account page: `https://www.avito.ru/professionals/api`
- Messenger API documentation:
  `https://developers.avito.ru/api-catalog/messenger/documentation`
- Auth API documentation:
  `https://developers.avito.ru/api-catalog/auth/documentation`

## Access Finding

The Avito `professionals/api` page says that custom API integration can be set
up independently and that the user should connect any tariff to get access keys
on that page.

This means API keys may become available after connecting a professional tariff.
It does not by itself prove that every API section is available on every tariff.

The official Messenger API description states that:

- in Goods and Jobs, Messenger API is available only on the `Максимальный`
  subscription level;
- in Services, Messenger API is available on `Расширенный` and `Максимальный`
  subscription levels.

Treat these as two separate gates:

- API key availability through `professionals/api`;
- Messenger API permission/scopes for chat reading, message sending, and
  webhooks.

The official API catalog exposes these relevant sections for the MVP:

- `auth`: token retrieval and refresh;
- `user`: authorized account information, balance, and operation history;
- `messenger`: chats, messages, message sending, read marks, webhooks, images,
  voice files, and blacklist;
- `accounts-hierarchy`: company/employee account checks and related operations,
  relevant if Avito account hierarchy affects chat access.

## Messenger Endpoints Needed For MVP

- `GET /messenger/v2/accounts/{user_id}/chats`
- `GET /messenger/v2/accounts/{user_id}/chats/{chat_id}`
- `GET /messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/`
- `POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/messages`
- `POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/read`
- `POST /messenger/v3/webhook`
- `POST /messenger/v1/webhook/unsubscribe`

Additional Messenger endpoints documented but not required for the first text
MVP:

- image upload and image message sending;
- message deletion;
- voice file retrieval;
- blacklist operations;
- subscription listing.

## Auth

Avito Auth API exposes `/token` operations for access-token retrieval and
refresh. Store `client_id`, `client_secret`, access tokens, and refresh tokens
outside git in local environment/config storage.

Documented token flows:

- `grant_type=client_credentials` with `client_id` and `client_secret`;
- `grant_type=authorization_code` with `client_id`, `client_secret`, and `code`;
- `grant_type=refresh_token` with `client_id`, `client_secret`, and
  `refresh_token`.

The first smoke check should use `client_credentials` and then call
`GET /core/v1/accounts/self` from the `user` API to discover the authorized
account id for `AVITO_USER_ID`.

As of 2026-06-23, the user has obtained Avito `client_id` and `client_secret`.
The actual values are secrets and must not be stored in git, project memory,
handoff summaries, screenshots committed to the repository, or chat logs beyond
what the user explicitly shares. Use local `.env` based on `.env.example`.

If a full secret was exposed outside the local trusted workflow, rotate it in
the Avito API cabinet before production use.

## Implementation Rule

Build the Avito integration behind a channel adapter. The core conversation
workflow must continue to work through a local/test adapter even when production
Avito keys or Messenger API scopes are unavailable.

Current implementation map:

- FastAPI app entrypoint: `app/main.py`
- Avito HTTP client: `app/avito_client.py`
- Environment/settings handling: `app/config.py`
- Browser UI: `app/static/index.html`, `app/static/app.js`,
  `app/static/styles.css`
- Tests: `tests/`

The current UI is a hello-world integration console, not the final manager
handoff workspace.

DeepSeek AI integration map:

- DeepSeek HTTP client: `app/deepseek_client.py`
- Sales assistant prompt and handoff detection: `app/assistant.py`
- UI draft action: `app/static/app.js`
- DeepSeek key env var: `DEEPSEEK_API_KEY`
- Default model: `deepseek-v4-flash`

DeepSeek is called only for AI draft generation and ping checks. Do not store
DeepSeek API keys, model responses containing private customer data, or raw
conversation payloads in project memory.

## Live Access Status

As of 2026-06-23, live Avito API smoke checks through the local app succeeded
after fixing the local message response shape:

- token check: `POST /api/avito/token-check` returned success;
- account check: `GET /api/avito/account` returned account metadata;
- chat list check: `GET /api/avito/chats?limit=1` returned success;
- selected chat message lookup returned success with messages and `meta`.
- DeepSeek ping returned success.
- DeepSeek draft generation for a selected Avito chat returned a draft.

Earlier, selected chat message lookup returned a local `500` because the app
expected a bare list while Avito returns an object with `messages` and `meta`.
That was an application response-shape bug, not an Avito access failure.

Do not store returned account metadata, chat payloads, messages, customer data,
or tokens in project memory. Use this note only as access evidence.

## Safe Manual Smoke Check

Use only environment variables. Do not paste secrets into commands, files, or
chat.

```powershell
$tokenResponse = Invoke-RestMethod `
  -Method Post `
  -Uri "https://api.avito.ru/token" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{
    grant_type = "client_credentials"
    client_id = $env:AVITO_CLIENT_ID
    client_secret = $env:AVITO_CLIENT_SECRET
  }

$headers = @{ Authorization = "Bearer $($tokenResponse.access_token)" }
Invoke-RestMethod `
  -Method Get `
  -Uri "https://api.avito.ru/core/v1/accounts/self" `
  -Headers $headers
```

If account lookup succeeds, use the returned user/account id as
`AVITO_USER_ID`. The next check is Messenger read access:

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "https://api.avito.ru/messenger/v2/accounts/$env:AVITO_USER_ID/chats?limit=1" `
  -Headers $headers
```

Expected outcomes:

- success means real Avito Messenger adapter can be implemented next;
- `401` means token/auth setup is wrong;
- `403` means token works but Messenger API permission/subscription is missing;
- empty chat list can be valid if the account has no chats yet.
