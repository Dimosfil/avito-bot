## Project Operation Commands

- Treat `gi prod`, `gi production`, `gi прод`, and `ги прод` as requests to
  publish the current development version of an online service into its
  documented production service folder. Use this only for services that run
  continuously against real remote APIs, webhooks, chats, marketplaces,
  payment providers, or other live external systems. Normal development,
  refactoring, tests, formatting, cleanup, and `gi restart` operate on the
  development checkout/service and must not edit, stop, reset, or test against
  the production service folder unless the user explicitly invokes the
  production command or local instructions define a stricter production
  workflow. Before `gi prod`, read project-local run/deploy instructions,
  service contracts, production folder config, secret-handling rules, ignore
  rules, and verification requirements. The production folder is a live runtime
  target, not the editable source of truth: never copy production secrets,
  databases, logs, caches, user data, or remote API state back into development.
  Build or prepare the documented artifact from the development checkout,
  exclude dev caches and generated noise, sync only approved source/build files
  into the production folder, preserve production-local config and secrets, and
  use an atomic or backup/rollback-friendly handoff when local tooling supports
  it. If the production folder, include/exclude rules, restart/switchover
  command, health check, or rollback path is undocumented, ask one short
  clarification question instead of guessing. After publishing, verify the
  production service with the documented health signal or harmless remote-API
  check and report exactly what was synced, what production-local state was
  preserved, whether the live service was restarted or left running, and any
  unverified risk. Follow `patterns/PROJECT_DEV_PROD_SERVICES.md`.
- Treat `gi ftp`, `ги фтп`, `gi ftp push`, `ги фтп пуш`, `gi upload ftp`,
  `gi deploy ftp`, and `gi залей на фтп` as requests to upload the current
  project's configured build output to FTP, FTPS, or SFTP. Treat
  `gi ftp config`, `gi ftp конфиг`, and `ги фтп конфиг` as requests to create,
  inspect, or update the project-local FTP/SFTP config without uploading. Treat
  `gi ftp folder`, `gi ftp папка`, and `ги фтп папка` as requests to inspect,
  choose, or update the remote upload folder (`remotePath`) without uploading.
  Treat `gi ftp service`, `gi ftp сервис`, and `ги фтп сервис` as requests to
  manually register, inspect, or select an FTP/FTPS/SFTP service record in
  config-service without uploading. Read project-local deploy instructions and
  `tools/deploy/ftp.local.json` first; when a project needs FTP and local config
  does not name a target service, query config-service for FTP-capable services.
  If exactly one matching service exists, use it after verifying its contract;
  if several exist, ask the user to choose with the same plain inline numbered
  checkbox marker style used by language selection. Keep secrets out of
  config-service:
  store only discovery metadata and secret references such as environment
  variable names. Keep project-specific deploy settings in the separate
  project-local config file rather than shared instructions or chat history.
  Prefer `tools/deploy/ftp.local.example.json` only as a redacted shape. Do not
  commit hostnames, usernames, passwords, tokens, private keys, or private
  remote paths unless project policy explicitly marks them non-secret. Follow
  `patterns/PROJECT_FTP_DEPLOY.md`.
- Treat `gi reboot`, `ги ребут`, `gi restart`, and `ги рестарт` as requests to
  start or restart all documented applications in the current project using
  project-local run instructions. Before starting anything, identify the full
  app set from local run instructions, manifests, service records, desktop
  packaging metadata, or project memory; do not assume a successful web/API
  start covers the project. For local web/API services, resolve the service id,
  port, URL, and neighboring endpoints through config-service before running a
  start command; fixed ports in local runbooks or examples do not authorize a
  fallback bind. If a config-service record is missing, use only the documented
  config-service registration workflow from `08-config-service-and-task-manager`
  to create or update it before startup, or stop with the exact missing
  contract. If local instructions define a preferred start/restart command that
  launches the full app set, use it only with the config-service-resolved local
  runtime values for web/API apps. Otherwise enumerate every documented app or
  runtime, such as desktop app, web/API app, and background workers, then
  restart each running app and start each missing app. Launch in the background
  so focus does not jump away from the user's current window. After launch, wait
  briefly and verify the documented startup success signal for each app:
  still-running expected processes, visible desktop windows when applicable,
  health/discovery endpoints for web/API apps, and relevant startup or crash
  logs when documented. The final report must account for each app by name or
  role with started/restarted/skipped status and verification evidence. Do not
  report reboot success from a PID alone, from a web health check alone, or
  while any expected desktop app, web/API app, or worker is unlaunched or
  unverified. If a documented desktop app lacks a launch command or window
  verification signal, report that as a blocker or partial failure instead of
  success. If any app exits, no expected window or health signal appears, or a
  new startup traceback is present, report the reboot as failed or partially
  unverified with the concrete evidence. Published hosting environments follow
  their hosting or production deploy contract and are not restarted by local
  `gi reboot` unless project-local production instructions explicitly define
  that behavior.
- Treat `gi first test`, `gi первый тест`, and `ги первый тест` as requests to
  verify the current application's first-launch experience by resetting only
  documented project-owned app cache, generated state, temporary first-run
  profiles, and rebuildable local app settings. Read project-local run, cleanup,
  cache reset, and test instructions first. Do not delete user documents,
  production data, secrets, credentials, external service data, shared system
  caches, sibling projects, or arbitrary user-home folders. If exact reset
  paths, keys, scripts, or commands are missing, ask one short clarification
  question instead of guessing. After reset, start the app, run the documented
  first-launch smoke/onboarding checks, and report what was cleared, what
  passed, and what was intentionally left untouched.
- Treat `gi test task`, `gi testing task`, `gi тест таск`, `ги тест таск`,
  `gi задача теста`, and equivalent wording as requests to set the active
  release/full-system verification workload for the current project. The
  supplied task text is the user-selected scenario for the next `gi test`; it is
  not evidence that the scenario already passed. Record it in the
  project-local test task location when local instructions define one,
  otherwise keep it as current chat context and report where it is tracked.
  Do not replace this with a generic `gi test plan`, old task status, demo
  artifact, or stale handoff summary.
- Treat `gi test`, `ги тест`, `gi full test`, `gi release test`,
  `gi system test`, and equivalent full-project test wording as requests to
  run the current project's documented full verification flow against the
  active test task. Do not confuse this with `gi test plan`, which remains a
  plan-only command by default. First load the active test task from the current
  message or project-local memory; if none exists, ask one short question for
  the test task before running. Then read project-local instructions, README,
  manifests, runbooks, test configs, and source entry points needed to identify
  exact current commands, services, app set, ports, routes, payloads,
  environment variables, storage, auth, queues, workers, and health checks.
  Start or restart documented apps when needed, run the verification ladder
  through the broadest documented suite justified by the command, and report
  the task used, commands run, results, blockers, and unverified areas. For
  `gi test`, dry-run mode is retired as a validity path: do not use `--dry-run`,
  simulation mode, dispatcher-only execution, replayed logs, mock-only runs, or
  compile/unit-only checks as the test result, and do not run dry-run mode at
  all unless the user explicitly asks for that diagnostic mode. If explicitly
  requested, label it as diagnostic and never report it as a passed `gi test`.
  A full-system `gi test` must exercise the documented live runtime surface for
  the selected task, including application processes, API/backend, storage,
  queues or workers, UI/auth flows, service discovery, orchestrator or agent
  handoff loops, and health/contract endpoints when the project defines them.
  If the live services/apps/workers/UI cannot be started or reached, report
  `gi test` as blocked or not checked instead of substituting a dry-run. Old
  summaries, screenshots, completed demo artifacts, previous task statuses, and
  old chat snippets are evidence only; they do not satisfy a fresh `gi test`
  request. Rerun the current documented checks or report the exact blocker that
  prevents a rerun.
- Treat `gi default`, `gi defaults`, and `ги дефолт` as requests to restore the
  current project to its documented first-run/default state. Read project-local
  reset, cleanup, first-run, run, backup, and test instructions first. Use only
  documented reset scripts, paths, keys, or contracts for project-owned app
  state, generated caches, local settings, onboarding flags, temporary profiles,
  and other rebuildable state. Do not delete source files, project-memory
  specifications, instruction-kit files, user documents, production data,
  secrets, credentials, external service data, shared system caches, sibling
  projects, or arbitrary user-home folders. If reset targets are not documented,
  ask one short clarification question instead of guessing. If a reset could be
  irreversible or remove user-owned data, stop for explicit confirmation and
  prefer a backup or rename step when local rules allow it. After reset, start
  the project through documented run instructions, verify the default or
  first-launch success signals, and report what was reset, what was left
  untouched, what passed, and any blocker.
- Treat `gi install`, `gi инсталл`, `ги инсталл`, and obvious typo variants
  such as `gi иснтлл` as requests to build the current project and produce an
  installer. Use Inno Setup by default when no installer tool is named. If the
  user writes a program after `gi install` / `gi инсталл`, use that program as
  the preferred packaging tool. Read project-local build and packaging
  instructions, scripts, manifests, and installer configs first. Resolve the
  application version from project-local metadata such as manifests, package
  files, assembly attributes, release files, or installer configs before
  packaging; update the version in build output, installer metadata, and the
  installer filename or artifact name when the local tooling supports it.
  `restore`, dependency install, build, and test checks are prerequisites only:
  they do not complete `gi install` unless the packaging command also runs and
  a current installer artifact is produced or explicitly verified. Do not report
  the project as installed/restored when only verification ran; report the
  installer artifact path, version, and checks after successful packaging. Ask a
  short clarification question if the build, installer, or versioning contract
  is missing instead of inventing one.
- Treat `gi sql`, `gi sqlite`, `ги sql`, `ги sqlite`, `gi vector`,
  `gi вектор`, and `ги вектор` as requests to inspect project-memory retrieval
  readiness and current metrics. For SQL, read `tools/project-memory/rag-system.json`
  when present, run the local index stats command when available, count
  reviewable project-memory/spec files, compare the numbers with the configured
  or default SQLite activation limits, and report whether SQLite/FTS is absent,
  current, stale, or recommended. For vector, read vector and embedding metadata,
  check semantic corpus size and chunk count, run the vector adapter status
  command when available, compare the numbers with vector activation limits, and
  report collection, record count, index path, freshness caveats, and readiness.
  These are inspection commands by default; do not create external services,
  install heavy dependencies, upload data, or index private sources unless the
  user explicitly asks and project-local rules allow it.
- Treat `gi rebuild` and `ги ребилд` as requests to rebuild the current project
  or application only, producing the documented build output such as an
  executable, package, or other artifact. Read project-local build or rebuild
  instructions, manifests, scripts, and packaging metadata before running the
  documented command.
  Do not treat `gi rebuild` as dependency restore, tests-only verification, or
  any RAG/GI tooling rebuild, and do not combine it with a RAG rebuild unless
  the user explicitly asks for both. If no project rebuild contract exists, ask
  one short clarification question instead of inventing a command. Use
  `gi tools rebuild` or `gi rag rebuild` when the GI/RAG layer itself must be
  rebuilt.
- Treat `gi tools rebuild`, `gi rag rebuild`, `ги тулс ребилд`,
  `ги раг ребилд`, and equivalent full GI/RAG rebuild wording as requests to
  rebuild the current project's entire configured GI/RAG project-memory
  retrieval system from approved sources: source manifest, SQLite/FTS or
  structured memory indexes, chunk exports, vector indexes, adapter metadata,
  and retrieval eval/status checks. This is a heavy command and requires an
  explicit user confirmation immediately before running the full rebuild, even
  if the user requested the command by name. Before asking for confirmation,
  read `tools/project-memory/rag-system.json`, list the configured rebuild
  nodes, generated paths that may be replaced, expected local scripts or
  adapters, and privacy exclusions. Do not include secrets, private runtime
  data, ignored telemetry, or sources outside the current project root. After a
  successful rebuild, run the configured stats/status/eval checks, update local
  rebuild state such as `last_full_rebuild_migration` or per-node markers when
  present, and report changed generated artifacts without committing
  rebuildable indexes.
- Treat `gi tools rebuild sql`, `gi rag rebuild sql`,
  `gi tools rebuild vector`, `gi rag rebuild vector`,
  `gi tools rebuild chunks`, `gi rag rebuild chunks`,
  `gi tools rebuild manifest`, `gi rag rebuild manifest`,
  `gi tools rebuild evals`, `gi rag rebuild evals`, and Russian equivalents
  such as `ги тулс ребилд sql`, `ги раг ребилд sql`,
  `ги тулс ребилд вектор`, `ги раг ребилд вектор`,
  `ги тулс ребилд чанки`, `ги раг ребилд чанки`,
  `ги тулс ребилд манифест`, `ги раг ребилд манифест`,
  `ги тулс ребилд тесты`, and `ги раг ребилд тесты` as requests to rebuild only
  the named GI/RAG node. Read `rag-system.json`, run only the documented node
  command or local helper, then verify that node's status. Ask one short
  clarification question if the node is not configured instead of guessing a
  command. For an `evals` node, prefer machine-checkable retrieval checks that
  verify index health, count consistency, and expected source paths in top
  keyword, semantic, or hybrid results; do not treat an answer's wording as the
  primary eval target.
- During `gi обновить`, inspect each newly applied migration. If a migration
  changes RAG source rules, chunking, embedding metadata, SQLite/vector schemas,
  retrieval adapters, or project-memory index scripts, check the project's
  `rag-system.json` rebuild state. If the project has not rebuilt the affected
  RAG nodes for that migration, tell the user exactly which nodes are stale and
  ask for confirmation before running the full `gi tools rebuild`; for narrow
  migrations, run or offer the smallest documented node rebuild that satisfies
  the migration. Do not mark RAG rebuild state current until the rebuild and
  readback/status checks succeed.
