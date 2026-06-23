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

- Use DeepSeek for the first AI draft provider.
- Keep provider code behind `app/deepseek_client.py` and business prompt logic
  in `app/assistant.py` so another model provider can replace it later.
