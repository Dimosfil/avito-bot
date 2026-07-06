# Handoff Summary: Business Algorithm And Modular Refactor

Date: 2026-07-06

## Business Algorithm

The user asked to write and fix the main business algorithm of `avito-bot`.
The agreed product logic is Module 2: AI first-line conversation automation for
incoming leads. The MVP receives or simulates customer requests, lets AI handle
routine first-line dialogue, detects buying/handoff intent such as commercial
proposal or deal requests, notifies a manager, and lets the manager manually
take over while preserving the full client conversation.

Durable source of truth added:

- `tools/project-memory/specs/business-rules/main-business-algorithm.md`

This document defines the platform-neutral workflow, actors, states, handoff
algorithm, AI conversation behavior, channel-adapter boundary, persistence,
failure handling, invariants, and verification criteria.

## User-Facing Visual Flow

The user then clarified that the algorithm must be understandable for a normal
user and include a visual explanation. A user-facing document was added:

- `docs/business-flow.md`

It explains, in Russian, how a client message enters the system, how AI answers,
when a lead becomes hot, how the manager is notified, and when AI stops. It
contains Mermaid diagrams for the simple business flow, roles, and modular
pipeline.

`README.md` now links to `docs/business-flow.md` near the current-focus section.

## Key Avito Intake Finding

The user asked how the key moment of receiving messages from Avito works.
Current implementation finding:

- The main production path is polling, not real webhook-driven processing.
- Backend calls Avito Messenger API for chat lists and messages.
- `_process_unread` fetches unread chats, also checks recently updated read
  chats, loads messages, persists them, finds the latest non-system inbound
  client message, and then decides whether to send AI, handoff, or skip.
- `/webhooks/avito/messenger` exists, but currently only records payloads and
  audit events. It does not yet normalize the event into the main conversation
  flow or trigger AI processing.

The important future direction is to make polling, webhook, manual import, and
simulator feed the same raw-intake contract.

## Modular Architecture Decision

The user clarified the intended architecture: raw message intake, processing,
decision-making, and reply production must be separate modules. Replies must
also be strategy-based: AI, operator, prepared template, rule-based auto-reply,
handoff notice, or no reply.

This decision was fixed in:

- `tools/project-memory/specs/business-rules/main-business-algorithm.md`
- `docs/business-flow.md`

The canonical pipeline is:

```text
raw intake -> normalization -> storage -> decision -> reply strategy -> outbound delivery
```

This is now a product/architecture rule: replacing AI with a template,
operator, or rule-based response must not require rewriting Avito intake,
normalization, persistence, or channel delivery.

## Refactor Batch 1: Reply Strategy Boundary

The user authorized `gi refactor` / "делай всё что надо". The first safe
refactor batch introduced an explicit reply-strategy boundary without changing
public API behavior.

Added:

- `app/reply_strategy.py`
- `tests/test_reply_strategy.py`

Changed:

- `app/main.py` now uses pre/post draft strategy decisions.
- Manager-action audit payloads now include `reply_strategy` for AI auto-reply
  and handoff notice paths.
- `tests/test_main.py` now verifies that an AI auto-reply records
  `"reply_strategy": "ai"`.

The supported strategy names are:

- `ai`
- `operator`
- `template`
- `rule_based`
- `handoff_notice`
- `no_reply`

The batch preserved existing user-visible behavior.

## Refactor Batch 2: Reduce `main.py`

The user challenged why `app/main.py` had about 1300 lines. Current finding:
`main.py` had accumulated routes, worker lifecycle, Avito sync, auto-reply
orchestration, runtime-state wrappers, notification orchestration, schemas,
logging, and helper proxies.

Second refactor batch removed two low-risk responsibilities from `main.py`:

- Telegram/manager notification proxy functions were removed. `main.py` now
  calls `app.manager_notifications` directly, and tests patch the real module.
- Pydantic API/request response classes moved into `app/schemas.py`.

Added:

- `app/schemas.py`

Updated:

- `tests/test_main.py`
- `tools/project-memory/specs/features/module-2-ai-conversations.md`
- `tools/project-memory/specs/technology-stack.md`

Line-count result:

- Before these reductions, `app/main.py` was 1355 lines.
- After the current refactor batches, `app/main.py` is 1255 lines.

## Current Remaining Refactor Work

The most important remaining oversized area is `_process_unread` in
`app/main.py`. It is the business heart of the Avito auto-reply flow and still
mixes Avito polling, storage, AI drafting, handoff, manager notification,
delivery, duplicate protection, and logging.

Recommended next batches:

1. Extract `_process_unread` into a service/use-case module.
2. Extract raw-intake and normalization modules so polling/webhook/import/local
   simulator share one inbound contract.
3. Extract autoreply worker lifecycle into `app/autoreply_worker.py`.
4. Extract Avito sync/cache helpers into a dedicated module.
5. Later split FastAPI routes into routers.

Avoid doing all of this in one unverified pass. Keep behavior stable and test
after each batch.

## Verification

Checks run after the refactor work:

- `uv run pytest` passed: 83 tests passed, 1 existing Starlette/TestClient
  deprecation warning.
- `uv run python -m compileall app tests` passed.
- `git diff --check` passed with no whitespace errors; Git only reported
  existing LF/CRLF conversion warnings.

## Repository State

There are uncommitted changes from this thread. Important changed/new files:

- `README.md`
- `docs/business-flow.md`
- `app/main.py`
- `app/reply_strategy.py`
- `app/schemas.py`
- `tests/test_main.py`
- `tests/test_reply_strategy.py`
- `tools/project-memory/pending-tasks.md`
- `tools/project-memory/specs/business-rules/main-business-algorithm.md`
- `tools/project-memory/specs/features/module-2-ai-conversations.md`
- `tools/project-memory/specs/technology-stack.md`

There is also an untracked `.codex/` directory. It was not touched during the
work and should be reviewed before any commit/stage operation.
