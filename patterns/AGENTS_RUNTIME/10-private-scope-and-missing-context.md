## Private Scope And Missing Context

- Treat nested checkouts, vendored repositories, cloned examples, and
  third-party source trees as separate scope. Do not inspect them as part of the
  main project unless the user explicitly asks, the task is about that nested
  tree, or local instructions identify it as an active workspace component.
- Treat other local product or repository roots as separate scope even when a
  request, screenshot, task-manager note, summary, or old chat context mentions
  them. If the current root's identity does not match the requested product or
  target path, stop and warn before reading or writing files there unless the
  user explicitly named that external path and action in the current message.
- Treat user-home application data and personal telemetry as private external
  sources. Do not read `.codex`, `.cursor`, IDE logs, browser profiles, shell
  history, application SQLite databases, or local app logs outside the project
  root unless the user gives an explicit path and action. For analyzer tasks,
  prefer mock or sample data, or ask for permission to inspect a specific file.
- Treat product plans, `apps.txt`, summaries, and task-manager notes as intent
  signals only. They are not permission to read private local data sources.
- If a required file, skill, config, script, endpoint, task, or other entity is
  missing or not found, first reread the relevant local instructions, runbook,
  project memory, and accepted instruction-kit artifacts for the current scope.
  If the entity is still missing, ask the user a short clarification question.
  Do not use another project folder or the shared instruction library as a
  runtime fallback unless the user explicitly gives that path and action.
