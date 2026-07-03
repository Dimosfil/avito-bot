# Agent Instructions

This file is the lightweight runtime entrypoint for this project. Detailed shared
rules are copied into focused modules under `patterns/AGENTS_RUNTIME/` so agents
can load only the context needed for the current task while preserving the same
behavior as the full instruction kit.

## Project

`avito-bot` is a modular marketing platform for marketplace and channel
automation. The product should help a business publish content, answer incoming
customer messages, assist managers, and act as a secretary for first-line sales
communication.

Initial implementation focus: Module 2, AI conversation automation for incoming
leads from marketplaces, social platforms, messengers, and the organization's
site.

## Project Goal

Current agreed goal: build the first MVP of Module 2. The MVP must receive or
simulate incoming customer requests, let AI handle the first-line dialogue,
detect handoff intent such as "хочу КП" or "хочу сделку", notify a manager,
and allow the manager to manually take over while seeing the client's messages.

Before implementation starts on a new project session, confirm a clear,
measurable project goal. If no goal is present in local instructions, project
memory, summaries, or the user's request, ask 1-3 focused questions to establish:

- Target user or stakeholder.
- Expected outcome.
- Success criteria or release definition.

Track the agreed goal in plans and final answers. At completion, report what was
implemented against each goal criterion and list remaining gaps as blockers.

## Loading Contract

- Start with this file.
- Read only the modules needed for the current request.
- Before acting on a concrete task, select and read the matching module(s);
  this entrypoint alone is enough only for greetings or status-neutral replies.
- If the request contains a GI chat command such as `gi ...`, `РіРё ...`, or a
  known mojibake form such as `Р С–Р С‘ ...`, treat it as a concrete task even when
  the message is short. First read `COMMANDS.md` when present, then read every
  runtime module routed to that command before acting.
- For state-changing GI commands that start, stop, restart, rebuild, deploy,
  test, install, reset, update, commit, push, or manage task-manager state, do
  not execute from memory, old chat examples, or a command name alone. If the
  command's routed module is unavailable, stop and report the missing path.
- For `gi restart`, `gi reboot`, `gi docker`, `ги рестарт`, `ги ребут`,
  `ги докер`, and equivalent aliases,
  `patterns/AGENTS_RUNTIME/09-project-operation-commands.md` is mandatory
  context before any process inspection, Docker build, stop, start, or success
  report.
- For broad or unclear work, read `patterns/AGENTS_RUNTIME/01-purpose.md`,
  `patterns/AGENTS_RUNTIME/03-rule-precedence.md`,
  `patterns/AGENTS_RUNTIME/06-tool-usage-and-token-economy.md`, and the most
  relevant task module.
- If a task crosses topics, read every matching module before acting.
- Prefer project-local instructions, runbooks, contracts, project memory, and
  service guides over shared defaults when they are more specific.

## Restore Context

If the user only sends a short greeting, thanks, acknowledgement, or
status-neutral message, do not run startup restore or read project files. Reply
briefly and ask what they want to do next.

Start here when a concrete restore/start task exists:

```powershell
.\tools\agent-start.ps1
```

If the startup script is unavailable, read only the smallest useful slices of:

- `AGENTS.md`
- latest relevant file in `tools/summary/`
- `tools/AGENT_WORKING_AGREEMENTS.md`
- `tools/AGENT_RUNBOOK.md`
- relevant notes in `tools/project-memory/`

Use the RAG startup flow and retrieve only task-relevant context.

## Runtime Module Routing

- Repository purpose, RAG startup, project memory, summaries, connected projects,
  and shared-rule propagation: `patterns/AGENTS_RUNTIME/01-purpose.md`
- Repository map: `patterns/AGENTS_RUNTIME/02-repository-map.md`
- Rule precedence and scope arbitration: `patterns/AGENTS_RUNTIME/03-rule-precedence.md`
- Authoring reusable rules, configuration boundaries, code quality, project
  info/stack inventory, and batch verification:
  `patterns/AGENTS_RUNTIME/04-content-and-authoring.md`
- Windows shell and networking policy: `patterns/AGENTS_RUNTIME/05-windows-command-policy.md`
- Token economy, verification command lookup, `gi info`, `gi stack`,
  `gi refactor`, feature contracts, and large-output handling:
  `patterns/AGENTS_RUNTIME/06-tool-usage-and-token-economy.md`
- Startup, restore, project goal, bug evidence, PDF inspection, repository
  cleanup, filesystem boundaries, and first-message handling:
  `patterns/AGENTS_RUNTIME/07-startup-and-scope.md`
- Config-service, service guide/contract lookup, task manager commands,
  manager-backed and local sprint commands, and web-service port registration:
  `patterns/AGENTS_RUNTIME/08-config-service-and-task-manager.md`
- Dev/prod online service publication, FTP deploy, restart/reboot,
  Docker/Compose restart, first test, full test, default reset, installer
  packaging, SQL/vector inspection, and project/RAG rebuild commands:
  `patterns/AGENTS_RUNTIME/09-project-operation-commands.md`
- Nested repositories, private local app data, product-plan intent signals, and
  missing required entities:
  `patterns/AGENTS_RUNTIME/10-private-scope-and-missing-context.md`
- Project, commit, task, and response language preferences:
  `patterns/AGENTS_RUNTIME/11-language-preferences.md`
- UI focus, app launch focus, and frontend verification expectations:
  `patterns/AGENTS_RUNTIME/12-ui-and-focus.md`
- Progress-update style: `patterns/AGENTS_RUNTIME/13-progress-updates.md`
- Update intake and `updates/` handling: `patterns/AGENTS_RUNTIME/14-update-intake.md`
- Verification policy: `patterns/AGENTS_RUNTIME/15-verification.md`
- Git policy: `patterns/AGENTS_RUNTIME/16-git-policy.md`

## Durable Memory

Durable project knowledge lives in `tools/project-memory/`. Put product behavior,
business rules, workflow contracts, implementation-driving specifications,
architecture decisions, and verified findings there, not only in chat or handoff
summaries.

Do not store raw work results, generated product outputs, screenshots, photos,
crawled/downloaded files, large logs, model outputs, build artifacts, export
bundles, or run datasets in `tools/project-memory/`. Use a project-local
artifact/evidence/output/data/docs-asset location and keep only compact
manifests, summaries, checksums, or links in project memory when needed.

General project documentation lives in `README.md`, `docs/`, and the runbook.
Keep overview, visible functionality, stack, commands, operations, and
troubleshooting there.

## Common Commands

Install dependencies:

```powershell
# TODO
```

Run:

```powershell
# TODO
```

Test:

```powershell
# TODO
```

Build:

```powershell
# TODO
```

Inspect logs:

```powershell
# TODO
```

## Working Areas

- Source: `TODO`
- Tests: `TODO`
- Tools: `tools/`
- Summaries: `tools/summary/`
- Project memory: `tools/project-memory/`

## Local Rules

- Do not revert user changes unless explicitly requested.
- Treat dirty worktrees as normal.
- Keep changes scoped to the current task.
- Ask before destructive operations, broad formatting-only churn, dependency
  replacements, data migrations, public API or storage contract changes, or
  unrelated scope expansion.
- Treat this project root as the filesystem boundary for normal work unless the
  user gives an explicit concrete path and action.
- Before filesystem writes, verify the active project root and target identity
  from local instructions, README, manifests, git remote, service id, or project
  memory. If the task appears to target a different product, repository, or
  absolute path outside this root, stop and warn the user unless the current
  message explicitly authorizes that exact external path and action.
- Preserve text encodings when editing files.
- Production runtime state is business-critical. `gi prod`, production reboot,
  and local release deploys must preserve `.release/.codex-runtime/` state,
  including server-side autoreply, pending autoreply, and manager takeover
  state. If no previous production runtime state exists, seed it from the
  development `.codex-runtime/` before starting `.release`. Never report the
  production bot as successfully deployed or rebooted if server-side autoreply
  was enabled before the operation and is disabled afterward.
