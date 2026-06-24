## Language Preferences

- Prefer one language command with three ordered choices when the user wants
  language preferences for project work. Treat `gi language`, `gi язык`, `ги язык`,
  `gi project language`, `gi проект язык`, `ги проект язык`,
  `gi язык проекта`, and `ги язык проекта` as requests to configure, in order:
  project working environment languages, commit-message languages, and task
  languages in
  `tools/project-memory/system-preferences.json` and
  `tools/project-memory/git-preferences.json`.
- Apply the configured project working-environment language order to plans,
  checklists, progress updates,
  final answers, clarifying questions, and user-facing explanations. Do not use
  it to rewrite existing task text, code, commands, logs, quoted text, or a
  response language the user explicitly requested for a specific message.
- Apply the configured project working-environment language order to
  agent-created or agent-updated project orientation documentation produced by
  `gi info` / `ги инфо`, including purpose, visible functionality, common
  workflows, and stack overview text. The first configured language is primary;
  if multiple languages are configured, write the primary language first and add
  one clear translation per additional configured language. Do not use
  commit-message or task-manager language preferences for this documentation.
- Apply the configured task language order to agent-created task titles, task
  descriptions, and task-manager updates.
- For task titles, descriptions, and task-manager updates, treat the first
  configured task language as the main language. If exactly one task language is
  configured, write task text only in that language. If multiple task languages
  are configured, write the main-language text first and then add one clear
  translation per additional language. Do not duplicate the same content twice
  in one language, and do not mix untranslated labels, templates, or Definition
  of Done text from another configured language into the main-language text.
- For each `gi язык` choice, preserve the user's selected order. The first
  selected language in each choice is primary for that surface.
- When no current selection exists for a `gi язык` unified language surface,
  use `1 2` as the default ordered selection: `English`, then `Russian`.
- If `gi язык` or an equivalent unified project-language command is sent
  without explicit languages, run a three-step chat flow instead of asking for
  one free-form line. First show a compact `Current settings` block for all
  three language surfaces. At each step, show the same plain numbered
  selection checklist of available languages with the current selection checked,
  add a final unchecked `Cancel / Отмена` option, name the current surface, and
  tell the user they may reply with numbers, language names, or cancel/отмена.
  Render each option as a plain inline checkbox marker with the number and
  label on the same physical line, such as `[x] 1. English` or
  `[ ] 2. Russian`. Do not use Markdown task-list syntax such as
  `- [x] 1. English` or ordered-task syntax such as `1. [x] English`, because
  some chat renderers split the checkbox control and label onto separate lines.
  Never emit a standalone checkbox line followed by a separate numbered label
  line.
- If the user selects `Cancel / Отмена`, replies `cancel` or `отмена`, or
  chooses only the cancel option during the language flow, stop the flow without
  changing any language preference files.
- When the user replies to that flow with a numeric-only answer such as `1 2`,
  interpret the numbers against the most recent language checklist and apply the
  resulting ordered languages to the current step. Do not ask which languages the
  numbers mean when the checklist was just shown.
- Keep commit-message language preferences separate from the agent's
  user-facing working language unless the user uses the unified project-language
  command.
- Treat `gi commit language`, `gi коммит язык`, `ги коммит язык`, and older
  `gi язык коммита` forms as requests to configure commit-message languages in
  `tools/project-memory/git-preferences.json`.
- Treat `gi system language`, `gi систем язык`, and `ги систем язык` as
  requests to configure the agent's project working language in
  `tools/project-memory/system-preferences.json`.
- Follow `tools/project-memory/system-preferences.json` for progress updates,
  final answers, clarifying questions, user-facing explanations, and
  agent-created task artifacts. Do not use it to rewrite existing task text,
  code, commands, logs, quoted text, or a response language the user explicitly
  requested for a specific message.
