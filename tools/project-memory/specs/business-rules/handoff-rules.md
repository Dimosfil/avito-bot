# Handoff Rules

## Purpose

Handoff rules decide when Module 2 should stop autonomous AI handling and bring
a human manager into the dialogue.

## Initial Trigger Phrases

The initial configured phrases are:

- `хочу КП`
- `хочу коммерческое предложение`
- `хочу сделку`
- `готов купить`
- `готов оформить`
- `свяжите с менеджером`
- `позовите менеджера`

The exact list must be configurable and extendable per business account.

## Intent Categories

Trigger categories:

- commercial proposal request;
- explicit deal or purchase intent;
- request for human manager;
- escalation, complaint, or uncertainty that AI should not resolve alone.

## Required Behavior

- Trigger detection may use exact phrases, normalized phrases, and later model
  classification, but the workflow outcome must be the same:
  `handoff_requested`.
- AI must not continue negotiating once `manager_active` is set.
- Manager manual takeover overrides AI automation immediately.
- A manager should see the trigger reason that caused the alert.
- When a handoff trigger is detected during backend auto-processing, the backend
  must persist the chat in the qualified-buying list, record a durable
  `handoff_required` manager action, and send a Telegram manager notification
  when `TELEGRAM_BOT_TOKEN` and `MANAGER_TELEGRAM_CHAT_ID` are configured.
- Chats in the qualified-buying list stay in AI mode by default. This keeps the
  client warm while a manager is busy or has not connected yet.
- A handoff trigger should produce a short client-facing AI reply such as
  a two-block confirmation marked with `✅` and `📋` before notifying the
  manager. The text is owned by the configurable bot-rules resource rather than
  hard-coded in orchestration code. The chat becomes manual only after a
  manager explicitly turns manual mode on.
- Telegram notification failures must be recorded with the handoff action but
  must not cause an Avito auto-processing failure or an accidental AI reply.
- Manual takeover is reversible: a manager may return any chat to AI by turning
  manual mode off for that chat.

## MVP Non-Goals

- Fully automated deal closing.
- Legal or pricing commitments without configured business rules.
- Hidden AI messages after a manager takes control.
