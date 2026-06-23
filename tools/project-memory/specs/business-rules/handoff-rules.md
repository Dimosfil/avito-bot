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
- False positives should be reversible by the manager returning the conversation
  to AI only if the product later supports that action.

## MVP Non-Goals

- Fully automated deal closing.
- Legal or pricing commitments without configured business rules.
- Hidden AI messages after a manager takes control.
