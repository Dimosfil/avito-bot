## Config Service And Task Manager

- Treat `gi config`, `gi конфиг`, `ги конфиг`, `gi config service`,
  `ги конфиг сервис`, `ги конфиг сервис url=<url>`, and
  `ги конфиг сервис урл=<url>` as requests to get or set the bootstrap config
  for the config/discovery service. Read the
  project-local override only if local instructions define one, then read GI
  main config from the configured shared-instruction source repo checkout/cache,
  the current shared-instruction checkout, or `GENERAL_INSTRUCTIONS_HOME`. Use
  its `config/gi-main.json` `configServiceUrl` to query the config service.
  Resolve local app and task-manager runtime URLs by service id through
  config-service; project task-manager config should keep only the selected
  manager name/id and non-secret project preferences. For the `url=<url>` form,
  validate a full `http://` or `https://` URL with no secrets, update the shared
  `configServiceUrl` or the explicit project-local override, and tell services
  to use that URL for registration and discovery. Do not scan sibling project
  folders, guess ports, copy URLs from old task-manager memory, or use stale
  task-manager records as a runtime fallback.
- For agent-facing HTTP services, prefer a service-owned guide endpoint plus a
  strict contract endpoint. Resolve runtime URLs through config-service. Read
  `endpoints.guide` first when present, then `endpoints.contract` before
  sending state-changing requests. Treat the guide as onboarding and the
  contract as workflow validation. If they disagree, stop and report the
  mismatch. Do not infer permissions from filesystem paths, stale memory, old
  dashboard URLs, or raw task receipts.
- Treat `gi manager`, `gi tm`, `gi manager test`, `ги менеджер`,
  `ги манагер`, and equivalent task-manager status or test wording as requests
  to inspect the configured task manager through config-service. Read the
  enabled manager id or `service_id` from project-local task-manager config,
  resolve it through `GET /services/{serviceId}`, read `endpoints.guide` when
  present, read `endpoints.contract`, then use `endpoints.api` for documented
  manager operations. Stop with the exact blocker if the manager id is missing,
  config-service is unavailable, no matching service record exists, or the
  guide/contract lacks the requested capability. Do not fall back to `base_url`,
  stale task-manager memory, port scans, sibling projects, or guessed endpoints.
- Treat `gi config service on`, `gi config service off`, `ги конфиг сервис on`,
  and `ги конфиг сервис off` as requests to set the current application's
  project-local config-service self-registration flag. `on` means the app
  should publish or refresh its own service record during startup; `off` means
  it must not. Do not reinterpret this as starting or stopping config-service
  itself. When setting `on`, first confirm a config-service URL is already
  configured in the same local config area or documented GI bootstrap config; if
  no URL is configured, tell the user to set `gi config service url=<url>`
  before enabling self-registration. Ask one short question if no local config
  location is documented.
- Treat `gi active task`, `gi next task`, `gi get task`, and equivalent
  active-task wording as requests to get executable work from the configured
  task manager. Resolve the manager through config-service, read the manager
  contract, request the active or next task through the documented operation,
  update manager lifecycle state and notes, and stop with the exact blocker if
  the contract, auth, permissions, lifecycle IDs, or requested object type is
  missing or mismatched. Do not create raw intake receipts, local checklist
  notes, or a different manager object type as a substitute for the requested
  task, sprint, or cycle.
- Treat `gi start sprint`, `gi sprint start`, and equivalent active-sprint
  wording as requests to take the active Sprint/Cycle into work through the
  configured task manager. Resolve the manager through config-service, read the
  guide and contract, request the active sprint/cycle or next task through the
  documented operation, move work through the documented lifecycle states, and
  submit completion through the manager contract. Stop with the exact blocker
  instead of falling back to generic `gi start`, local task notes, raw intake,
  guessed endpoints, or filesystem task edits.
- Treat task-manager sync commands as routine execution steps, similar in
  certainty to `gi commit`, `gi push`, or FTP deploy commands after the user has
  supplied the content or selected workflow. A fast or weaker model may execute
  these commands, but it must still follow the manager contract exactly: do not
  replace manager API work with `project-memory`, pending-task notes, guessed
  commands, raw intake receipts, local checklists, or "tell me the exact
  command" fallback. If discovery, auth, contract, capability, payload shape, or
  readback is missing, stop with the exact blocker.
- Treat `gi add sprint`, `gi create sprint`, `gi добавить спринт`, and
  equivalent add-sprint wording as requests to create a visible executable
  Sprint/Cycle through the configured task manager. Resolve the manager through
  config-service, read the manager contract, use only the documented sprint or
  cycle creation operation, verify readback/lifecycle identifiers, and stop with
  the exact blocker if auth, permissions, schema, lifecycle, or object type
  support is missing. Do not downgrade the request to raw intake or a Work Item.
- For web-facing applications that expose a port, HTTP API, web UI, task-manager
  service, or local daemon endpoint, require a live config-service lookup before
  the process binds or reserves any port. On every startup, read the configured
  config-service URL, verify the config service is reachable, and query the
  app's own `service_id` startup/service record. If the record exists, bind only
  the recorded port and use config-service records for neighboring service
  endpoints. If the record is missing and project-local self-registration is
  `on`, read the config-service guide and contract, list existing records,
  choose a port that is free on the local host and absent from config-service,
  bind it, verify the app's local health endpoint, and create or update the
  service record through the documented config-service operation. If the record
  is missing and self-registration is `off`, or config-service lacks a
  documented registration contract, stop with a clear blocker; do not invent
  payloads, write storage directly, reuse stale local config, or bind a fallback
  port while config-service is unavailable. If the recorded endpoints changed,
  refresh the record only after the config-service check succeeds. Desktop apps,
  CLI tools, libraries, scripts, and other non-web applications must not query
  or publish to config-service during normal startup unless local instructions
  explicitly define a discoverable web/API runtime.
