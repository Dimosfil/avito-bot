# Pending Tasks

Use this file for active project-wide plans and multi-step work.

Keep entries concise and task-relevant. Do not store full diffs, large logs,
generated outputs, secrets, credentials, or private production data.

## Status Markers

- `[ ]` not started
- `[~]` in progress
- `[x]` done
- `[!]` blocked or needs attention

## Tasks

### Avito regional Autoload operator

Goal: publish truthful service-by-city listings through the official Avito
Autoload API with deterministic feeds, explicit commercial safeguards, and
terminal result verification.

- [x] Verify a one-city Moscow publication through the real Autoload API.
- [x] Record the durable integration contract and project rules.
- [x] Add regional XML generation and guarded API operator scripts.
- [x] Add an example two-city manifest and offline verification workflow.
- [ ] Replace the temporary diagnostic feed URL in the remote profile with a
  stable operator-controlled HTTPS feed.
- [x] Review the first published city result and approve the remaining city
  matrix.
- [x] Publish the approved 10-city matrix with truthful locations and stable
  per-city IDs.
- [x] Verify all 10 feed items as active with no `duplicate`, `linker`, or
  commercial-package errors in the 2026-07-15 rollout.
- [ ] Monitor every future rollout through terminal item results before
  increasing batch size.

### Module 2 MVP: AI conversation and manager handoff

Goal: build the first usable slice of AI first-line communication with manager
handoff.

Planned changes:

- [x] Record project goal and Module 2 behavior contract.
- [x] Record Avito as the first production channel target and document access
  gates.
- [x] Add local secret handling template for Avito credentials.
- [x] Choose implementation stack and local development shape.
- [x] Build hello-world backend and UI for Avito connectivity checks.
- [x] Probe real Avito token, account, chat-list, and message-read access.
- [x] Add DeepSeek-backed review-first AI draft generation.
- [ ] Design platform-neutral conversation domain model.
- [ ] Implement local/test Avito-compatible channel adapter for inbound and
  outbound messages.
- [ ] Implement AI reply orchestration behind a provider interface.
- [ ] Implement configurable handoff trigger detection.
- [ ] Implement manager takeover state transition.
- [ ] Add manager-facing conversation view or API endpoint.
- [ ] Add real Avito Messenger adapter after keys and permissions are confirmed.
- [ ] Add focused tests for dialogue states and handoff behavior.

Execution order:

- [x] Define stack and MVP architecture.
- [x] Build first runnable FastAPI UI for Avito token/account/chats checks.
- [x] Probe real Avito API access with keys outside git.
- [ ] Build domain model and storage.
- [ ] Build local Avito-compatible adapter and workflow service.
- [x] Add AI provider boundary with DeepSeek as the first provider.
- [ ] Add manager handoff and visibility path.
- [ ] Probe real Avito API access with keys outside git when available.
- [ ] Replace or supplement the local adapter with real Avito Messenger API
  calls if access is confirmed.
- [ ] Verify with local scenario tests.

Risks or dependencies:

- [x] Avito credentials and Messenger message-read access are verified for the
  current account.
- [!] Avito `client_secret` must stay only in local secret storage. Rotate it if
  it is ever exposed outside the trusted local workflow.
- [ ] Real Avito webhooks require a public HTTPS endpoint that responds with
  200 OK within Avito's timeout.
- [ ] AI provider key and model choice are not selected yet.
- [ ] Business knowledge base, tone, and forbidden commitments are not defined
  yet.
- [ ] Manager notification channel is not selected yet.

Verification:

- [ ] Incoming message creates or updates a conversation.
- [ ] AI answers only while conversation is AI-controlled.
- [ ] Trigger phrases move the conversation to handoff-required state.
- [ ] Manual manager takeover prevents further AI replies.
- [ ] Manager can see message history with sender roles.
# Refactor Batch: Reply Strategy Boundary

Status: completed in the first scoped batch. Follow-up refactors should extract
raw intake and normalization modules from the current Avito polling flow.

Goal: start the `gi refactor` modularization by separating reply selection from
Avito message intake and delivery while preserving current behavior.

Planned changes:

- Add a small backend reply-strategy module with explicit strategy names.
- Use the strategy in unread Avito auto-processing before sending replies.
- Preserve current AI and handoff behavior; do not change public API routes.
- Record reply strategy in durable manager-action payloads where replies are
  sent.
- Add focused tests for strategy selection and existing auto-reply behavior.

Risks/dependencies:

- `app/main.py` still owns most orchestration after this batch.
- Raw intake and normalization modules remain follow-up refactors.
- Existing tests monkeypatch `SalesAssistant` and `AvitoClient`; keep those
  seams stable.

Verification:

- `uv run pytest tests/test_reply_strategy.py tests/test_main.py`
- `uv run python -m compileall app tests`
- `git diff --check`
