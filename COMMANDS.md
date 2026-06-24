# General Instructions Commands

Command examples for working with the shared `general-instructions` kit.

For full policies, see `AGENTS.md`, `patterns/GIT_WORKFLOW.md`, and
`patterns/FIRST_MESSAGE_HANDLING.md`.

## Agent Execution Guard

Agents must treat entries in this file as chat commands, not shell commands.
Before executing any state-changing `gi ...` / `ги ...` command, read the
current project's `AGENTS.md` loading contract and the routed
`patterns/AGENTS_RUNTIME/` module for that command. If the routed module is
missing, stop and report the missing path instead of acting from memory.

For `gi restart`, `gi reboot`, `ги рестарт`, `ги ребут`, and equivalent aliases,
read `patterns/AGENTS_RUNTIME/09-project-operation-commands.md` before any
process inspection, stop, start, or success report.

## Команды Для Чата С Агентом

Префикс `gi` — короткая команда для локального instruction kit. Не
переименовывай в `GAI`. `gi` = `general-instructions`, не `git`.
Это команды для чата с агентом, не команды PowerShell. Если пользователь хочет
именно терминальную PowerShell-команду, он пишет `PS` или получает реальную
команду/путь к скрипту, например `.\tools\agent-start.ps1`.

```text
gi help
ги хелп
gi commands
ги команды
gi обновись
gi init https://github.com/Dimosfil/general-instructions.git
инит https://github.com/Dimosfil/general-instructions.git
init https://github.com/Dimosfil/general-instructions.git
инит <path-to-general-instructions>
инит правила <path-to-general-instructions>
gi язык
ги язык
gi язык: 1 2
ги язык: 1 2
gi language: Russian English
gi проект язык: Russian
ги проект язык: Russian
gi project language: Russian
gi язык проекта: Russian
gi коммит язык: Russian
ги коммит язык: Russian
gi язык коммита: Russian
gi язык коммита: English only
gi систем язык: Russian
ги систем язык: Russian
gi саммари
gi старт
gi restore
gi sql
gi sqlite
gi vector
gi stack
ги стек
gi rebuild
gi tools rebuild
gi rag rebuild
gi tools rebuild sql
gi rag rebuild sql
gi tools rebuild chunks
gi rag rebuild chunks
gi tools rebuild vector
gi rag rebuild vector
gi tools rebuild manifest
gi rag rebuild manifest
gi tools rebuild evals
gi rag rebuild evals
gi refactor
gi рефактор
ги рефактор
gi full refactor
ги ребилд
ги тулс ребилд
ги раг ребилд
ги тулс ребилд sql
ги раг ребилд sql
ги тулс ребилд чанки
ги раг ребилд чанки
ги тулс ребилд вектор
ги раг ребилд вектор
ги тулс ребилд манифест
ги раг ребилд манифест
ги тулс ребилд тесты
ги раг ребилд тесты
gi config
gi config service
gi config service url=http://127.0.0.1:4100
gi config service on
gi config service off
gi prod
gi production
gi прод
ги прод
gi ftp config
gi ftp
ги фтп конфиг
ги фтп
ги конфиг сервис on
ги конфиг сервис off
gi reboot
gi restart
gi first test
gi default
gi defaults
ги дефолт
gi первый тест
ги первый тест
ги ребут
ги рестарт
ги конфиг сервис урл=http://127.0.0.1:4100
gi install
gi инсталл
ги инсталл
gi старт спринт
gi гит-обзор
gi git summary
gi тест-план
gi test plan
gi test task
ги тест таск
gi test
ги тест
gi tm
gi active task
gi next task
gi add sprint
gi create sprint
gi добавить спринт
gi manager test
gi tm test
gi план
gi post plan
gi пуш
gi коммит
gi только пуш
gi коммит пуш
gi пул
```

### GI Help / Command Index

```text
gi help
gi хелп
ги help
ги хелп
gi commands
gi команды
ги команды
```

`gi help` asks the agent to show a compact list of available GI chat commands
with short descriptions. The agent reads the local command index when present,
prefers project-local additions over this shared baseline, and does not run
startup restore, resume old work, call task managers, mutate files, or execute
the listed commands.

| Command | Description |
| --- | --- |
| `gi help`, `ги хелп`, `gi commands`, `ги команды` | Show the local GI command list with short descriptions. |
| `gi обновить`, `gi обновись` | Apply accepted instruction-kit updates and migrations. |
| `gi init <source>`, `инит <source>`, `инит правила <source>` | Bootstrap or restore shared instructions from `general-instructions`. |
| `gi start`, `gi старт`, `gi restore` | Restore minimal project context and ask for the current task. |
| `gi summary`, `gi саммари` | Write a thematic thesis-based handoff summary under `tools/summary/`. |
| `gi language`, `gi язык` | Configure project working-environment languages. |
| `gi project language`, `gi проект язык`, `gi язык проекта` | Configure project-facing language preferences. |
| `gi commit language`, `gi коммит язык`, `gi язык коммита` | Configure commit-message languages. |
| `gi system language`, `gi систем язык` | Configure agent working-response language. |
| `gi sql`, `gi sqlite` | Inspect SQLite/FTS project-memory readiness and metrics. |
| `gi vector` | Inspect semantic/vector retrieval readiness and metrics. |
| `gi stack`, `ги стек` | Find or build the current project's verified technology stack inventory. |
| `gi rebuild`, `ги ребилд` | Rebuild the current project/application only, such as producing a build artifact or exe. |
| `gi tools rebuild`, `gi rag rebuild`, `ги тулс ребилд`, `ги раг ребилд` | Rebuild the full configured GI/project-memory/RAG system after confirmation. |
| `gi tools rebuild sql`, `gi rag rebuild sql` | Rebuild only the SQL/FTS structured-memory node. |
| `gi tools rebuild chunks`, `gi rag rebuild chunks` | Rebuild only semantic chunk exports. |
| `gi tools rebuild vector`, `gi rag rebuild vector` | Rebuild only the vector retrieval node. |
| `gi tools rebuild manifest`, `gi rag rebuild manifest` | Rebuild only source manifest/inventory metadata. |
| `gi tools rebuild evals`, `gi rag rebuild evals` | Run configured RAG health and retrieval eval checks only. |
| `gi refactor`, `gi рефактор`, `ги рефактор` | Refactor the entire current project according to all applicable GI rules, in verified batches. |
| `gi config`, `gi config service` | Inspect config/discovery service settings. |
| `gi config service url=<url>` | Set the config-service URL after validation. |
| `gi config service on`, `gi config service off` | Toggle current app self-registration with config-service. |
| `gi prod`, `gi production`, `gi прод`, `ги прод` | Publish the current development version into the documented production service folder for a live online service. |
| `gi reboot`, `gi restart`, `ги ребут`, `ги рестарт` | Start or restart all documented project apps using local run instructions. |
| `gi first test`, `gi первый тест` | Reset documented first-run state and verify first-launch experience. |
| `gi default`, `gi defaults`, `ги дефолт` | Restore the current project to documented first-run/default state. |
| `gi install`, `gi инсталл`, `ги инсталл` | Build/package the current project and verify an installer artifact. |
| `gi ftp config`, `gi ftp service`, `gi ftp folder` | Inspect or configure FTP/SFTP deployment settings without uploading. |
| `gi ftp`, `gi ftp push`, `gi deploy ftp`, `gi upload ftp` | Upload configured build output to the configured FTP/SFTP target. |
| `gi tm`, `gi manager` | Inspect the configured task manager through config-service. |
| `gi manager test`, `gi tm test` | Test the configured task manager contract and operations. |
| `gi active task`, `gi next task`, `gi get task` | Get executable work from the configured task manager. |
| `gi add sprint`, `gi create sprint`, `gi добавить спринт` | Create a visible Sprint/Cycle through the configured task manager. |
| `gi plan`, `gi план`, `gi post plan` | Send the current plan to the configured task manager. |
| `gi start sprint`, `gi старт спринт` | Take the active Sprint/Cycle into work through the configured task manager. |
| `gi test plan`, `gi тест-план` | Build a verification plan from current project contracts. |
| `gi test task`, `ги тест таск` | Set the active release/full-system verification task for the current project. |
| `gi test`, `ги тест` | Run the documented full project verification flow against the active test task. |
| `gi git summary`, `gi гит-обзор` | Summarize the latest git commit without printing a full diff. |
| `gi commit`, `gi коммит` | Commit scoped changes. |
| `gi push`, `gi пуш` | Commit and push scoped changes. |
| `gi only push`, `gi только пуш` | Push the current branch without creating a commit. |
| `gi commit push`, `gi коммит пуш` | Commit and push scoped changes. |
| `gi pull`, `gi пул` | Fetch and pull the current branch. |

Если команда неполная, агент уточняет недостающий параметр.

Ответ на `gi` команду ограничен этой командой; агент не возвращается к
предыдущей задаче без явной просьбы.

Прогресс-апдейты должны быть по фазам, а не после каждого батча команд. Агент
не пишет счётчики вроде "выполнено 4 команды" и не ведёт live-blog каждой
промежуточной гипотезы. Сообщать стоит при смене фазы, значимом выводе,
блокере или долгой паузе.

Автоматические счётчики tool calls, которые показывает UI чата, не считаются
прогресс-апдейтами агента; агент не должен дублировать их текстом.

`gi` команда выполняется в текущем project root. Shared library читается
только как источник `VERSION.md`, `CHANGELOG.md`, `INDEX.md`, `migrations/` и
шаблонов. Отсутствие `.git` не блокирует проверку/применение GI-обновлений,
только commit/push.

`apps.txt`, планы, summary и записи task manager не дают разрешение читать
приватные локальные источники вне project root. Для анализаторов логов агент
использует mock/sample data или спрашивает явное разрешение на конкретный путь
и действие перед чтением `.codex`, `.cursor`, IDE logs, browser profiles, shell
history, SQLite databases или app logs.

Если нужный файл, skill, config, script, endpoint, task или другая сущность не
найдена, агент сначала перечитывает локальные инструкции, runbook, project
memory и принятые instruction-kit artifacts для текущей команды. Если после
этого сущность всё ещё отсутствует, агент задаёт один короткий вопрос
пользователю. Нельзя использовать другой проект или shared library как runtime
fallback без явного пути и действия от пользователя.

После успешного `gi обновить` / `gi обновись` агент коммитит и пушит только те
изменения instruction kit, которые создал сам update-flow, если это git
repository с настроенным remote и изменения касаются только instruction kit.
Команда не является просьбой пушить уже существующие локальные коммиты, синкать
feature branch, продолжать старый план или делать общее Git-обслуживание. Без
remote, при конфликте или unrelated changes — остановиться и объяснить блокер.

### Новый Проект

```text
Connect shared instructions: https://github.com/Dimosfil/general-instructions.git
```

Агент:
- читает общие правила и нужные шаблоны
- создаёт локальные `AGENTS.md`, `tools/AGENT_WORKING_AGREEMENTS.md`,
  `tools/AGENT_RUNBOOK.md`, `tools/agent-start.ps1` и project memory files
- не добавляет shared library как dependency, submodule или symlink
- не трактует `инит <path-to-general-instructions>` или
  `инит правила <path-to-general-instructions>` как `git init`; не создаёт
  папки, `.git`, `npm init` или `python -m venv` для этой формы
- не спрашивает про языки коммитов при bootstrap
- останавливается после setup и спрашивает, что делать дальше

### Восстановить Контекст Проекта

```text
gi старт
gi restore
```

Также: `gi start`, `gi восстанови`, `gi восстановить контекст`.

Агент восстанавливает контекст из `AGENTS.md`, последнего handoff summary и
`tools/agent-start.ps1`, затем кратко говорит статус и спрашивает, что делать
дальше. Не продолжает старую задачу автоматически.

Старые планы, фазы рефакторинга, заметки из памяти и локальные коммиты впереди
remote можно упомянуть только как компактный контекст. Нельзя превращать их в
предлагаемое следующее действие, если пользователь явно не попросил продолжить,
запустить, дописать или запушить именно это.

### Inspect Project Memory Retrieval

```text
gi sql
gi sqlite
gi vector
```

`gi sql` / `gi sqlite` asks the agent to inspect project-memory SQLite/FTS
readiness. The agent reads `tools/project-memory/rag-system.json`, runs local
stats helpers when available, counts memory/spec files, compares the numbers
with activation limits, and reports whether SQL indexing is absent, current,
stale, or recommended.

`gi vector` asks the agent to inspect semantic/vector readiness. The agent reads
embedding/vector metadata, checks semantic corpus size and chunk count, runs the
vector adapter status helper when available, and reports collection, records,
index path, freshness caveats, and readiness.

These are inspection commands by default. They do not deploy external services,
install heavy dependencies, upload data, or index private sources unless the
user explicitly asks and project-local rules allow it.

### Собрать Стек Технологий Проекта

```text
gi stack
ги стек
```

`gi stack` / `ги стек` asks the agent to find or build the current project's
technology stack inventory. The agent first looks for a visible project-local
stack source of truth: a top-level README/docs/runbook link near the beginning
of the file, `tools/project-memory/specs/technology-stack.md`, or an equivalent
linked architecture/stack note. If a current inventory exists, the agent reads
it, verifies the key facts against current manifests, lockfiles, config, run
instructions, and source entry points, then reports the stack and any gaps.

If no stack link or inventory exists, the agent creates or updates the canonical
inventory from current project evidence. Use
`tools/project-memory/specs/technology-stack.md` unless local instructions name
a different canonical docs path. Record languages, runtimes, frameworks,
package managers, build/test tools, storage, external services, commands,
evidence paths, and unknowns. For external agents starting outside the project,
the first pass should be able to find the stack pointer in the first relevant
project instructions or docs; when it is missing, add a concise link to the
canonical stack inventory in the appropriate top-level project doc if local
rules allow documentation edits.

This command is an inventory/documentation command. It must not install
dependencies, start services, rebuild indexes, call external APIs, read secrets,
or inspect private paths outside the project root unless the user explicitly
approves that scope.

### Rebuild Project

```text
gi rebuild
ги ребилд
```

`gi rebuild` asks the agent to rebuild the current project/application build
output, such as an executable, package, or other
documented artifact. The agent reads project-local build or rebuild
instructions, manifests, scripts, and packaging metadata before running the
documented command.

This command does not mean dependency restore, tests-only verification, a
RAG-only rebuild, or a combined project-plus-RAG rebuild. It does not rebuild
GI/RAG indexes or tools. If no project rebuild contract exists, the agent asks
one short clarification question instead of inventing a command. Use
`gi tools rebuild` or `gi rag rebuild` when the GI/RAG layer itself must be
rebuilt.

### Rebuild GI/RAG Tools

```text
gi tools rebuild
gi rag rebuild
ги тулс ребилд
ги раг ребилд

gi tools rebuild sql
gi rag rebuild sql
gi tools rebuild chunks
gi rag rebuild chunks
gi tools rebuild vector
gi rag rebuild vector
gi tools rebuild manifest
gi rag rebuild manifest
gi tools rebuild evals
gi rag rebuild evals
ги тулс ребилд sql
ги раг ребилд sql
ги тулс ребилд чанки
ги раг ребилд чанки
ги тулс ребилд вектор
ги раг ребилд вектор
ги тулс ребилд манифест
ги раг ребилд манифест
ги тулс ребилд тесты
ги раг ребилд тесты
```

`gi tools rebuild` / `gi rag rebuild` asks the agent to rebuild the whole
configured GI/project-memory/RAG retrieval system for the current project:
manifest/source inventory, SQLite/FTS or structured indexes, semantic chunk
exports, vector indexes, adapter metadata, and retrieval status/eval checks.

Full rebuild is heavy and requires explicit confirmation immediately before it
runs. Before asking, the agent reads `tools/project-memory/rag-system.json`,
lists configured rebuild nodes, generated paths that may be replaced, commands
or adapters that will run, and privacy exclusions. It does not index secrets,
private runtime data, ignored telemetry, or sources outside the project root.

Node forms such as `gi tools rebuild sql`, `gi rag rebuild chunks`,
`gi tools rebuild vector`, `gi rag rebuild manifest`, and
`gi tools rebuild evals` rebuild only that node through the command documented in
`rag-system.json` or the project-local runbook, then run the matching status
check. Retrieval evals should assert expected source evidence in top keyword,
semantic, or hybrid results rather than exact answer wording. If the node is
not configured, the agent asks one short clarification question instead of
inventing a command.

During `gi обновить`, the agent checks newly applied migrations. If a migration
changes RAG source rules, chunking, embedding metadata, SQLite/vector schemas,
retrieval adapters, or project-memory index scripts, the agent compares the
migration id with `rag-system.json` rebuild state. If affected nodes have not
been rebuilt for that migration, it reports the stale nodes and asks before the
full rebuild, or runs/offers the smallest documented node rebuild for narrow
migrations. Rebuild state is updated only after rebuild and readback/status
checks pass.

### Получить GI Config

```text
gi config
gi конфиг
ги конфиг
gi config service
ги конфиг сервис
gi config service url=http://127.0.0.1:4100
ги конфиг сервис url=http://127.0.0.1:4100
ги конфиг сервис урл=http://127.0.0.1:4100
```

Агент получает bootstrap-конфиг сервиса конфигов, а не ищет runtime-конфиги в
папках соседних проектов. Сначала читать project-local override, если он явно
задан локальными инструкциями, затем `config/gi-main.json` из checkout/cache
канонического source repo `https://github.com/Dimosfil/general-instructions.git`,
текущего checkout shared instructions или пути из `GENERAL_INSTRUCTIONS_HOME`.
Из GI main config взять `configServiceUrl` и проверить сам config-service через
его `/health` или документированный discovery endpoint.

`gi config service` / `ги конфиг сервис` — явное имя того же сценария. Для
runtime-адресов локальных приложений и task manager агент берёт из локального
проекта только имя или service id, затем запрашивает `GET /services/{serviceId}`
в config-service. После этого он использует `endpoints.availability` для
проверки доступности, `endpoints.guide` для агентского onboarding, когда этот
endpoint есть, `endpoints.contract` для актуального протокола и `endpoints.api`
для операций. Если guide и contract расходятся по endpoint, ownership или
permissions, агент останавливается и сообщает mismatch вместо догадок по
старой памяти, dashboard URL, filesystem paths или raw receipts.

`gi config service url=<url>` / `ги конфиг сервис url=<url>` /
`ги конфиг сервис урл=<url>` задаёт canonical URL config-service для текущего
окружения, например
`http://127.0.0.1:4100`. В shared instruction library агент обновляет
`config/gi-main.json`; в проекте с явным local override обновляет только этот
override. Все локальные сервисы используют этот URL, чтобы регистрироваться в
config-service и читать discovery. URL должен быть полным `http://` или
`https://` адресом без секретов, токенов, query string и fragment.

Если GI main config или config-service недоступен, остановиться с коротким
блокером. Не подбирать порты, не сканировать sibling workspace roots, не читать
другие project roots и не использовать старые task-manager записи как замену
config-service.

### Проверить Первый Запуск

```text
gi first test
gi default
gi defaults
ги дефолт
gi первый тест
ги первый тест
```

Агент проверяет сценарий первого запуска текущего приложения. Сначала он читает
project-local run, test, cleanup и cache reset инструкции, manifests и config
entry points, затем останавливает или перезапускает только процессы текущего
проекта, если это требуется для безопасного сброса.

Сброс включает только задокументированные project-owned кеши, временные профили,
локальные настройки приложения, generated state и другие rebuildable данные,
которые проект явно относит к first-run state. Не удалять пользовательские
документы, production данные, секреты, credentials, внешние сервисные данные,
общие системные кеши, sibling project folders или произвольные user-home
папки. Если локальные инструкции не называют точные paths, keys, commands или
reset script, агент задаёт один короткий вопрос вместо угадывания.

После сброса агент запускает приложение как при первом использовании,
проверяет documented smoke checks или onboarding/first-run workflow и сообщает,
что именно было очищено, какие проверки прошли и какие данные намеренно не
трогались.

### Restore Project Defaults

```text
gi default
gi defaults
ги дефолт
```

The agent restores the current project to its documented first-run/default
state. This is broader than `gi first test`: it may clear project-owned app
state, generated caches, local settings, onboarding flags, temporary profiles,
and other rebuildable state that local instructions explicitly define as safe to
reset.

Before clearing anything, the agent reads project-local reset, cleanup,
first-run, run, backup, and test instructions. If the project provides a reset
script or contract, use that documented flow. If reset targets are not
documented, ask one short clarification question instead of guessing paths.

Do not delete source files, project memory specifications, instruction-kit
files, user documents, production data, secrets, credentials, external service
data, shared system caches, sibling projects, or arbitrary user-home folders.
If a reset would be irreversible or could remove user-owned data, stop for
explicit confirmation and prefer a backup or rename step when local rules allow
it.

After reset, start the project through documented run instructions and verify
the default or first-launch success signals. Report what was reset, what was
left untouched, what verification passed, and any blocker that prevented a full
clean-slate restore.

### Собрать Билд И Инсталлятор

```text
gi install
gi инсталл
ги инсталл
gi install Inno Setup
gi инсталл Inno Setup
gi инсталл <программа>
```

Также распознавать очевидные опечатки вроде `gi иснтлл`, если намерение
собрать installer ясно из контекста.

Агент собирает production build и установочный файл для текущего проекта.
Если программа не указана, по умолчанию использовать Inno Setup: найти
project-local build/package инструкции, скрипты и `.iss` файл, затем собрать
приложение и installer. Если после команды указана программа, использовать её
как предпочитаемый packaging/installer tool вместо Inno Setup.

Перед packaging агент определяет версию приложения из project-local metadata:
manifests, package files, assembly attributes, release files или installer
configs. Агент обновляет версию в production build, installer metadata и имени
installer-файла или installer-артефакта, если локальные инструменты это
поддерживают. Если versioning contract отсутствует или неоднозначен, агент
задаёт один короткий уточняющий вопрос вместо изобретения версии.

Перед сборкой агент проверяет локальные инструкции, README, manifests и
существующие packaging scripts/configs. Если build или installer contract не
найден, агент задаёт короткий уточняющий вопрос вместо изобретения installer
конфига без опоры на проект. `restore`, dependency install, build и test
являются только предварительными проверками: они не завершают `gi install`,
пока packaging command не выполнена и текущий installer artifact не создан или
явно не проверен. Если агент выполнил только проверки, он сообщает именно это
и не называет проект установленным/восстановленным. После успешного packaging
агент кратко сообщает версию, путь к инсталлятору и выполненные проверки.

### Взять Активный Sprint В Работу

```text
gi старт спринт
```

Также: `gi start sprint`, `gi sprint start`, `gi активный спринт`,
`gi work sprint`.

Агент восстанавливает контекст, затем через настроенный task manager находит
активный sprint и выполняет задачи по порядку. Если sprint'ов 0 или >1 —
показать варианты и спросить.

Before starting sprint workflow, verify that the configured manager API endpoint
supports active sprint lookup, next-task lookup, and task completion for the
selected workflow. If only generic health works, stop before executing tasks.
This command is more specific than plain `gi start`; do not answer it with only
generic startup restore when a configured task-manager workflow is available.

### Проверить Обновления Инструкций

```text
Обновись из https://github.com/Dimosfil/general-instructions.git
```

Если локального kit ещё нет — bootstrap/init. Если уже есть — применить
только недостающие миграции. Использовать `VERSION.md`, `CHANGELOG.md` и
`migrations/`, не читать `updates/`.

`gi обновить` тихий по умолчанию: без прогресс-нарратива, без широких чтений,
без повторяющихся статусов. Только компактный результат: версии до/после,
количество миграций, ID применённых, изменённые файлы, проверки, commit/push.

`gi обновить` применяет принятые instruction-kit миграции. Не предлагать пушить
локальные коммиты, которые существовали до обновления, и не подменять команду
git-синхронизацией проекта.

Если после обновления впервые стал доступен task-manager plan sync, но
`tools/project-memory/task-managers.json` отсутствует или не содержит
включенных менеджеров, сразу предложить plain inline numbered checkbox marker checklist с
доступными адаптерами и `none`. Не подключать WorkNest или другой менеджер
автоматически.

Если локальный checkout/cache path недоступен — использовать `source_repo` из
metadata, URL из команды, текущий checkout/cache shared instructions или
`GENERAL_INSTRUCTIONS_HOME`. Локальный путь хранить только как cache/checkout,
а канонический источник брать из GitHub repo.

### Настроить Язык Проекта

```text
gi язык
ги язык
gi язык: 1 2
ги язык: 1 2
gi language: Russian English
gi проект язык: Russian
ги проект язык: Russian
gi project language: Russian
gi язык проекта: Russian
ги язык проекта: Russian
```

Это основной способ выбрать языки проекта. Команда задаёт три выбора с одним и
тем же списком языков:

1. Project working environment: общение, progress updates, финальные ответы,
   уточняющие вопросы, планы и checklists.
2. Commit messages.
3. Tasks: task titles, task descriptions и task-manager updates.

В каждом выборе можно указать один или несколько языков; порядок важен. Первый
выбранный язык становится основным для этой поверхности, второй — вторым
языком, и так далее. Агент обновляет
`tools/project-memory/system-preferences.json` и
`tools/project-memory/git-preferences.json`.

Если команда пришла без выбора, агент показывает три последовательных выбора.
Если у одной из трёх поверхностей ещё нет текущего выбора, агент использует
дефолт `1 2`: `English`, затем `Russian`.
Если язык указан сразу после команды, агент использует этот порядок для всех
трёх поверхностей, пока пользователь не задаст отдельные значения.

В чатовой форме каждый из трёх выборов показывается как короткий нумерованный
plain inline numbered checkbox marker checklist с одним и тем же списком языков и текущими отметками.
Пользователь может ответить номерами или названиями языков. Если пользователь
отвечает только числами, например `1 2`, агент применяет их к последнему
показанному списку и сохраняет этот порядок для текущего этапа, не уточняя
повторно, какие языки соответствуют числам.
Перед первым выбором агент показывает короткий блок текущих настроек для всех
трёх поверхностей. В каждый список добавляется вариант `Cancel / Отмена`; если
пользователь выбирает его или отвечает `cancel`/`отмена`, агент завершает
настройку без изменения файлов предпочтений.

Пример первого этапа:

```markdown
Current settings:
- Project working environment: English, Russian
- Commit messages: English, Russian
- Tasks: English, Russian

1/3. Project working environment language order

Reply with numbers or language names in priority order, or choose cancel.

[x] 1. English
[x] 2. Russian
[ ] 3. Spanish
[ ] 4. German
[ ] 5. French
[ ] 6. Cancel / Отмена
```

Настройка не переводит уже существующий текст задач, код, команды, логи,
цитаты или язык, который пользователь явно попросил для конкретного ответа.
Если пользователь не называет язык, агент показывает короткий Markdown
checklist с доступными языками и текущим выбором.

Если пользователь явно хочет настроить язык проекта вручную, можно запустить:

```powershell
.\tools\select-project-language.ps1
```

или:

```powershell
.\tools\agent-start.ps1 -ConfigureProjectLanguage
```

### Настроить Языки Коммитов

```text
gi коммит язык: Russian
ги коммит язык: Russian
gi commit language: Russian
gi язык коммита: Russian
gi язык коммита: English only
```

Это старая настройка языка commit-сообщений. По умолчанию `English` без
дополнительных языков. Агент обновляет
`tools/project-memory/git-preferences.json` сам и кратко подтверждает. Если
пользователь не называет языки, агент показывает plain inline numbered checkbox marker checklist с текущим
выбором и пояснением, что `English` обязателен.

### Настроить Системный Язык Агента

```text
gi систем язык: Russian
ги систем язык: Russian
gi system language: Russian
```

Это настройка языка работы агента в проекте: progress updates, финальные
ответы, уточняющие вопросы, пользовательские объяснения, task titles, task
descriptions, task-manager updates, планы и checklists. Агент обновляет
`tools/project-memory/system-preferences.json` сам и кратко подтверждает. Эта
настройка не меняет язык commit-сообщений, код, команды, логи, цитаты или язык,
который пользователь явно попросил для конкретного ответа.

### Git Finish Commands

```text
gi пуш            # commit + push
gi коммит          # commit только
gi только пуш      # push без commit
gi коммит пуш      # commit + push (алиас gi пуш)
gi пул            # fetch + pull текущей ветки
```

Перед любым commit/push агент проверяет `git status --short`, staged/unstaged
changes, remote и ветку. Коммитит только изменения текущей задачи или
явно указанного scope. `gi пуш` нельзя подменять сырым `git push`, повтором
предыдущего terminal push или push-only действием; если scoped изменений для
commit нет, агент сообщает это вместо push-only fallback. Push без нового
commit выполняется только по `gi только пуш`. При блокерах — кратко объясняет.

Для `gi пул` агент проверяет состояние рабочей копии, текущую ветку и upstream,
затем делает `git fetch` и подтягивает текущую ветку. Если появляются
конфликты, агент сначала оценивает их по затронутым файлам и решает только
очевидные, низкорисковые конфликты, сохраняя пользовательские изменения. Если
конфликт требует продуктового решения, затрагивает чужие или секретные файлы,
или его нельзя решить уверенно, агент останавливается и обращается к
пользователю с кратким описанием вариантов.

### Записать Handoff Summary

```text
gi саммари
```

Создаёт `tools/summary/YYYY-MM-DD_HH-mm-ss_AGENT_WORK_SUMMARY.md` по
структуре из `templates/SUMMARY.template.md`. Summary фиксирует смысл треда:
намерение пользователя, решения, изменения кода/архитектуры/бизнес-логики,
проверки, блокеры и следующий полезный контекст. Summary строится как
тематический handoff, а не короткий пересказ подряд: агент разбивает тред на
смысловые темы, выделяет тезисы внутри каждой темы, кратко описывает тезисы и
добавляет детали только там, где сложная тема потеряет контекст без них. Ссылки
на кодовые файлы, URL, медиа, картинки, логи, скриншоты или точные артефакты
оставляются только когда они нужны для понимания или проверки контекста.
Для архитектурных и research-тредов, особенно когда пользователь оценивает
внешний проект, статью, паттерн или инструмент как возможную цель интеграции,
summary явно сохраняет намерение пользователя, маппит внешние концепты на
текущие компоненты проекта и разделяет решения и гипотезы.
Рутинные успешные `gi push`,
`gi commit`, staging counts, git directives, branch/push metadata и commit hash
не записываются, если их можно восстановить из git logs или command history.
Если нужен подробный протокол, он пишется отдельно как `Thread Timeline`, а не
подмешивается в обычный handoff summary.

Когда пользователь спрашивает, на чём остановились в прошлом треде, агент
сверяет handoff summary с последним видимым выводом треда, скриншотами или
цитатами пользователя. Приоритет у последнего явного архитектурного/продуктового
решения, открытого вопроса или согласованного направления, а не у случайного
caveat из summary. Непроверенный env/config caveat, пропущенный check или
старый next-step bullet не становятся текущей задачей сами по себе.

### Собрать Обзор Последнего Git-Коммита

```text
gi гит-обзор
gi git summary
```

Агент показывает hash, дату, автора, тему, изменённые файлы (компактно),
предполагаемый смысл и заметные риски. Без полного diff, без создания
summary-файла, без commit/push.

### Составить План Тестирования

```text
gi тест-план
gi test plan
```

Агент изучает локальные инструкции, скрипты и тестовую структуру, выдаёт
компактную "лестницу проверок": syntax checks → unit → integration → smoke →
manual → regression. По умолчанию планирует без запуска, если пользователь не
просит запустить.

Перед рекомендацией или запуском smoke/API/CLI checks агент сверяет точные
commands, flags, ports, routes, methods, JSON payload fields и env vars с
текущими project-local instructions, README, manifests, config или source code.
Summary, screenshots и старый чат считаются evidence/status, а не
authoritative command contract.

Для новой фичи: expected behavior, failure paths, edge cases, rollback, что
проверено, что требует ручной проверки.

### Full Project Test

```text
gi test task <release/full-system test task>
ги тест таск <release/full-system test task>
gi test
ги тест
```

`gi test task` sets the active verification workload for the current project.
The task text is the selected scenario for the next `gi test`, not proof that
the scenario has already passed. Use the project-local test-task location when
local instructions define one; otherwise keep the task in current chat context
and say where it is tracked.

`gi test` runs the documented full verification flow against the active test
task. It is different from `gi test plan`: `gi test plan` plans by default,
while `gi test` runs. Before running, the agent rereads current local
instructions, README, manifests, runbooks, test configs, and source entry
points needed to verify exact commands, services, app set, ports, routes,
payloads, environment, storage, auth, queues, workers, and health checks.

For `gi test`, dry-run mode is not a valid result. Do not report `--dry-run`,
simulation mode, dispatcher-only execution, replayed logs, mock-only runs, or
compile/unit-only checks as a passed `gi test`, and do not run dry-run mode at
all unless the user explicitly asks for that diagnostic mode. A full test must
exercise the documented live runtime surface for the selected task: apps,
backend/API, storage, queues/workers, UI/auth, service discovery, orchestrator
or agent handoff loops, and health/contract endpoints when the project defines
them. If the live system cannot be started or reached, report the full test as
blocked or not checked.

Old summaries, screenshots, completed demo artifacts, previous task statuses,
and old chat snippets are evidence only. They do not satisfy a fresh `gi test`
request; rerun the current documented checks or report the exact blocker.

### Full Project Refactor

```text
gi refactor
gi рефактор
ги рефактор
gi full refactor
```

The agent treats this as approval to refactor the entire current project
according to all applicable GI rules, not as a proposal-only request. Before
editing, it reads project-local instructions, README, manifests, architecture or
runbooks, project-memory specifications, connected-project registers, and
relevant test/build contracts. It creates a concise refactor plan covering
architecture boundaries, configuration boundaries, hard-coded deploy/user/runtime
values, development-tool versus generated-product boundaries, SOLID/DRY/clean
code, duplicated business logic, oversized modules, dependency direction, typed
or validated contracts, tests, and project-memory updates.

The agent works in small verifiable batches and preserves user-visible behavior
unless the user explicitly changes it. It asks before destructive operations,
data migrations, public API or storage contract changes, dependency
replacements, broad formatting-only churn, or private/external paths. After
meaningful batches, it runs documented checks for affected areas, updates
durable project-memory specs for behavior or architecture changes, avoids
committing generated/rebuildable artifacts unless local rules require them, and
reports remaining risks or continuation batches.

### Настроить Task-Manager Plan Sync

```text
gi tm
```

Агент проверяет `tools/project-memory/task-managers.json`. Если менеджеры уже
есть — обновляет skill/config из shared kit. Если нет — показывает checklist
доступных адаптеров и `none`. После выбора создаёт конфиг и заполняет
обязательные поля. В конфиге task manager хранится имя или service id менеджера
и project-local preferences; runtime URL агент получает через config-service по
этому service id.

Task-manager commands are routine sync/execution commands once the user has
provided the sprint/task content or selected the workflow. They are suitable for
fast or weaker models only if the model still follows the manager guide and
contract exactly: resolve service id, verify capabilities, send the documented
payload, read back lifecycle identifiers, and stop with the exact blocker when
that cannot be done. Do not replace the manager operation with
`project-memory`, pending-task notes, raw intake receipts, guessed commands,
local checklists, or a request for the user to provide the exact manager
command.

### Test Current Task Manager

```text
gi manager test
gi tm test
gi манагер тест
gi менеджер тест
```

The agent tests the configured task manager end to end in the current project:
resolve the manager service id through config-service, read the manager contract,
create a disposable no-op task through the documented API entry point, load/read
it back, take it in work when the adapter supports that lifecycle step, complete
it as `done`, read the final status, and report the manager id, resolved service
endpoint, task id or URL, completed lifecycle steps, and any missing capability.
The test must not edit repository files, touch secrets, perform destructive
actions, or use another project folder.

### Get Active Task From Task Manager

```text
gi active task
gi next task
gi get task
```

The agent gets executable work from the configured task manager, not from raw
intake receipts or guessed UI routes. It resolves the manager through
config-service, reads the contract, requests the active task first when
supported, otherwise requests the next task through the documented operation,
marks it in progress when supported, executes the task, and sends progress,
blocker, or completion notes back to the manager.

For WorkNest, external agents use `/agent-intake/...` API operations. They do
not move Markdown files, edit internal statuses, archive tasks, or rely on an
old local URL instead of resolving `service_id: worknest` through config-service.

If the manager cannot return lifecycle identifiers, cannot update status, or
the requested object type is blocked by auth/permissions, the agent stops and
reports the exact blocker. It must not create a different object type, raw
intake record, or local checklist note as a substitute for the requested
manager object.

### Add Sprint To Task Manager

```text
gi add sprint
gi create sprint
gi добавить спринт
```

The agent creates a visible executable Sprint/Cycle in the configured task
manager. It resolves the manager through config-service, reads the contract, and
uses only the documented sprint/cycle creation operation or the adapter's
documented executable plan payload. After creation it reads the sprint/cycle
back and reports the lifecycle identifiers or URL.

If the manager only accepts raw intake, or the sprint/cycle endpoint returns an
auth, permission, schema, routing, or object-type error, the agent stops and
reports the blocker. It must not create a Work Item, raw receipt, local
checklist, or one-task plan as a substitute for the requested Sprint/Cycle.

### Отправить План В Task Manager

```text
gi план
gi post plan
```

Агент отправляет текущий план в подключенный task manager. Если менеджер не
настроен — сначала выполняет setup flow как `gi tm`. Если план не дан в
сообщении и не найден в контексте — спрашивает.

Для WorkNest: `POST /agent-intake/raw`. Ответ intake — квитанция, не
подтверждение создания карточки. Before sending, verify raw intake capability,
not only `/health`.

## PS PowerShell Commands

For when you want to run helpers yourself from a bootstrapped project root.
Only commands in this section are meant to be run literally in PowerShell.

### Startup

```text
.\tools\agent-start.ps1
.\tools\agent-start.ps1 -ConfigureGitCommitLanguages
.\tools\agent-start.ps1 -ConfigureSystemLanguage
```

### Configure Commit Languages

```text
.\tools\select-git-commit-languages.ps1
```

### Configure Agent System Language

```text
.\tools\select-system-language.ps1
```

### Check Instruction Updates

```text
.\tools\check-instruction-kit-updates.ps1
.\tools\check-instruction-kit-updates.ps1 -VerboseOutput
.\tools\check-instruction-kit-updates.ps1 -RecordApplied   # только после применения и верификации
```

`-Apply` не является metadata-only shortcut. Применяй файлы миграций до
записи metadata.

### Maintain This Library

```powershell
git diff --check
git diff --stat
git status --short
```

## Команды Для Чата С Агентом: Runtime

### Production Service And FTP Deploy

```text
gi prod
gi production
gi прод
ги прод
gi ftp config
gi ftp service
gi ftp folder
gi ftp push
gi ftp
ги фтп конфиг
ги фтп сервис
ги фтп папка
ги фтп пуш
ги фтп
gi upload ftp
gi deploy ftp
gi zaley na ftp
gi залей на фтп
```

`gi prod` / `gi production` / `gi прод` / `ги прод` publishes the current
development version into the documented production service folder for an online
service connected to real remote APIs. It is for continuously running services
such as bots, webhook workers, marketplace connectors, payment integrations, or
other live external integrations.

The agent first reads project-local production/deploy instructions, service
contracts, production folder config, secret-handling rules, ignore rules,
restart or switchover commands, health checks, and rollback requirements.
Normal development, refactoring, tests, cleanup, formatting, and `gi restart`
operate on the development checkout/service and must not edit, stop, reset, or
test inside the production service folder unless the user explicitly invokes
the production workflow or local instructions define a stricter command.

The production folder is a live runtime target, not the editable source of
truth. During `gi prod`, build or prepare the documented artifact from the
development checkout, sync only approved source/build files into the production
folder, preserve production-local `.env`, secrets, databases, sessions, logs,
caches, service-manager files, webhook/API state, and user data, and use a
backup, rollback, or atomic handoff when available. Never copy production
secrets or runtime data back into development. If the production folder,
include/exclude rules, restart/switchover command, health check, or rollback
path is undocumented, ask one concise clarification question instead of
guessing. Follow `patterns/PROJECT_DEV_PROD_SERVICES.md`.

`gi ftp config` / `ги фтп конфиг` creates, inspects, or updates the current
project's FTP/SFTP config without uploading. Use a separate project-local file:
`tools/deploy/ftp.local.json`. Prefer secrets through environment variables or
private keys; do not commit real hostnames, usernames, passwords, tokens,
private keys, or private remote paths unless project policy explicitly marks
them non-secret.

`gi ftp service` / `ги фтп сервис` manually registers, inspects, or selects an
FTP/FTPS/SFTP service record in config-service without uploading. When a project
needs FTP and no local `serviceId` is selected, agents query config-service for
FTP-capable services first. If one exists, they verify its contract and use it;
if several exist, they ask the user to choose with the same plain inline
numbered checkbox marker style used by language selection. Store only non-secret discovery
metadata and secret reference names in config-service, never raw credentials or
private remote paths.

`gi ftp folder` / `ги фтп папка` inspects, chooses, or updates the remote upload
folder (`remotePath`) without uploading. If credentials and a selected FTP
service are available, the agent may list remote directories and ask the user to
choose with plain inline numbered checkbox markers; otherwise it asks for the destination
path and saves it in `tools/deploy/ftp.local.json`.

`gi ftp push` / `ги фтп пуш` is the explicit upload command. `gi ftp` /
`ги фтп` remains a shorter alias. The agent first reads project-local deploy
instructions and
`tools/deploy/ftp.local.json`, builds the configured `localPath` when needed,
then uploads to `remotePath`. If the config is missing, use the redacted
template shape from `templates/ftp.local.template.json` or
`tools/deploy/ftp.local.example.json` and ask only for missing required values.
Do not print secrets or full credential-bearing commands.

`gi config service on` / `gi config service off` sets the current application's
project-local config-service self-registration flag in the same documented
local config area as its config-service URL. `on` is for web-facing apps that
expose a port, HTTP API, web UI, task-manager service, or local daemon endpoint:
on startup they must contact config-service and read their own `service_id`
startup/service record before binding any port. The port to bind and neighboring
service endpoints come from config-service. If config-service is missing,
unreachable, has no record for the app, or returns incomplete startup config,
startup reports the blocker and waits for config-service to be configured,
repaired, or started; it does not guess, scan, or use stale fallback ports.
`off` means the app must not publish or refresh its own service record. Desktop
apps, CLI tools, libraries, scripts, and other non-web apps should not query or
publish to config-service during normal startup unless local instructions
explicitly define a discoverable web/API runtime. If the flag is being set to
`on` and no config-service URL is configured, stop and tell the user to set
`gi config service url=<url>` first. Do not reinterpret `on`/`off` as starting
or stopping the config-service process.

`gi reboot` / `gi restart` starts or restarts all documented applications in the
current project using project-local run instructions. Before starting anything,
identify the full app set from local run instructions, manifests, service
records, desktop packaging metadata, or project memory; do not assume a
successful web/API start covers the project. For local web/API services,
resolve the service id, port, URL, and neighboring endpoints through
config-service before running a start command; fixed ports in local runbooks or
examples do not authorize a fallback bind. If a config-service record is
missing, use only the documented config-service registration workflow to create
or update it before startup, or stop with the exact missing contract. If local
instructions define a preferred start/restart command that launches the full
app set, use it only with the config-service-resolved local runtime values for
web/API apps. Otherwise enumerate every documented app or runtime, such as
desktop app, web/API app, and background workers, then restart each running app
and start each missing app in the background. After launch, wait briefly and
verify the documented startup success signal for each app: expected processes
are still running, visible desktop windows exist when applicable, web/API health
or discovery succeeds when applicable, and relevant startup or crash logs do not
show a new failure. The final report must account for each app by name or role
with started/restarted/skipped status and verification evidence. Do not report
reboot success from a PID alone, from a web health check alone, or while any
expected desktop app, web/API app, or worker is unlaunched or unverified. If a
documented desktop app lacks a launch command or window verification signal,
report that as a blocker or partial failure instead of success. Published
hosting environments follow their hosting or production deploy contract and are
not restarted by local `gi reboot` unless project-local production instructions
explicitly define that behavior.

`gi first test` / `gi первый тест` / `ги первый тест` resets only documented
project-owned application cache, generated state, temporary first-run profiles,
and rebuildable local app settings, then starts the app and verifies the
documented first-launch workflow. The agent first reads project-local run,
cleanup, cache reset, and test instructions. It must not delete user documents,
production data, secrets, credentials, external service data, shared system
caches, sibling projects, or arbitrary user-home folders. If exact reset paths,
keys, or commands are missing, ask one concise clarification question instead
of guessing.

`gi default` / `gi defaults` / `ги дефолт` restores the current project to its
documented first-run/default state. The agent first reads project-local reset,
cleanup, first-run, run, backup, and test instructions, then uses only
documented reset scripts, paths, keys, or contracts. It must not delete source
files, project-memory specifications, instruction-kit files, user documents,
production data, secrets, credentials, external service data, shared system
caches, sibling projects, or arbitrary user-home folders. If reset targets are
not documented, ask one concise clarification question instead of guessing. If
the reset could be irreversible or remove user-owned data, stop for explicit
confirmation and prefer a backup or rename step when local rules allow it.
After reset, start the project through documented run instructions, verify the
default or first-launch success signals, and report what was reset, what was
left untouched, what passed, and any blocker.
