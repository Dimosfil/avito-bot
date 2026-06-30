# Service Discovery Config

Use the GI config service for local runtime discovery. Do not scan sibling
project folders, guess ports, or reuse stale task-manager memory as a substitute
for live service discovery.

## Bootstrap Flow

1. Read project-local overrides only when local project instructions explicitly
   define them.
2. Read GI main config from `config/gi-main.json` under the configured
   shared-instruction source repo checkout/cache, the current shared checkout,
   or the `GENERAL_INSTRUCTIONS_HOME` equivalent. The canonical source repo is
   `https://github.com/Dimosfil/general-instructions.git`.
3. Read `configServiceUrl`.
4. Query the GI config service.
5. Query `GET /services/{serviceId}` for the named target service.
6. Verify `endpoints.availability` and the expected identity.
7. Query `endpoints.guide` when present for agent-facing onboarding: allowed
   actions, forbidden actions, startup order, ownership boundaries, and safe
   payload examples.
8. Query `endpoints.contract` when the task needs the target service protocol,
   schemas, supported actions, or workflow-specific rules.
9. Use `endpoints.api` as the target service API entry point after reading the
   guide and contract.
10. Check required workflow capabilities before using a service.
11. Stop with a clear `service mismatch` blocker when identity, guide,
   contract, or required capabilities do not match.

## Config Service URL Command

Use `gi config service url=<url>`, `ги конфиг сервис url=<url>`, or
`ги конфиг сервис урл=<url>` to declare the canonical config-service URL for
the current environment.

Default:

```text
gi config service url=http://127.0.0.1:4100
```

When this command is used in the shared instruction library, update
`config/gi-main.json` so future agents and local services read the same
`configServiceUrl`. When it is used inside a project with an explicit
project-local override, update only that documented override.

All local services that publish discovery records should read this URL before
registering themselves. Do not hardcode another config-service address in
service startup scripts, task-manager config, summaries, or agent memory.

Only web-facing applications should use startup self-registration: HTTP APIs,
web apps, task-manager services, local daemons with a port, or other services
that expose a runtime URL another project may need to discover. Desktop apps,
CLI tools, libraries, scripts, and other non-web applications must not query or
publish to config-service during normal startup unless project-local
instructions explicitly say they expose a discoverable local service.

Web-facing applications must check the current config-service config on every
process startup before binding or reserving any port. The startup sequence is:

1. Read the configured config-service URL.
2. Verify config-service is reachable.
3. Query the app's own configured `service_id` service/startup record.
4. If the record exists, read the port the app should bind and the endpoints of
   neighboring services from config-service records.
5. Before starting a new process, check whether the recorded port is already
   occupied. If the owner is the same documented service instance, restart or
   reuse it only as the local run contract allows. If the owner is another
   service, unknown, or cannot be verified from documented identity signals such
   as service id, command, cwd, health endpoint, or process metadata, stop with
   a port-conflict blocker. Do not kill the owner without explicit user approval
   and verified ownership. Do not bind an alternate port just because the
   recorded port is busy; changing the port changes browser origin and can hide
   browser-owned state such as localStorage, cookies, and IndexedDB.
6. If the record is missing and the app's self-registration flag is `on`, read
   the config-service guide and contract, list existing service records, select
   or request a local development port only through the documented
   config-service registration operation, create or update the app's service
   record, start the app using the recorded value, and verify the app's local
   health endpoint.
7. If the record is missing and self-registration is `off`, stop startup and
   report that the service is not registered.
8. If documented endpoints changed, refresh the app's service record only after
   the live config-service check succeeds and through the documented
   registration/update operation.

If config-service is missing, unreachable, or does not expose a guide/contract
for service registration, stop startup, report the blocker, and wait for the
user or supervisor to configure, repair, or start config-service. Do not reuse
stale local runtime config or bind a fallback port while config-service is
unavailable. Do not invent a registration payload or write directly to the
config-service storage when the contract does not document the operation.

Validate the URL before saving it:

- It must be a full `http://` or `https://` URL.
- It must not include secrets, tokens, usernames, passwords, query strings, or
  fragments.
- After saving, verify `GET <url>/health` when the task allows contacting the
  running service.

## App Self-Registration Flag

Use `gi config service on`, `gi config service off`, `ги конфиг сервис on`, or
`ги конфиг сервис off` to set whether the current application should publish
itself to config-service during startup.

- `on` means a web-facing application is expected to self-register or refresh
  its own config-service record on startup.
- `off` means the application must not publish or refresh its own service
  record, even if config-service is available.
- For non-web applications, leave this flag off or absent unless local run
  instructions define a web/API runtime for the project.
- Store this flag alongside the project's documented config-service URL or run
  instructions. Do not store the flag in GI main config, and do not reinterpret
  it as starting or stopping the config-service process.
- When setting the flag to `on`, first confirm a config-service URL is already
  configured in that same local config path or in the documented GI bootstrap
  config. If no URL is configured, stop and tell the user to set
  `gi config service url=<url>` before enabling self-registration.
- If the project has no documented place for this flag, ask one short
  clarification question instead of inventing a hidden config file.

## GI Main Config

The GI main config is only a bootstrap pointer:

```json
{
  "version": 1,
  "configServiceUrl": "http://127.0.0.1:4100"
}
```

Do not store all service data in this file.

## Config Service Contract

The config service should expose:

```text
GET /health
GET /agent/guide
GET /agent/contract
GET /services
GET /services/{serviceId}
GET /services/{serviceId}/startup
GET /projects/{projectId}/services
POST /services
PUT /services/{serviceId}
PATCH /services/{serviceId}
```

The stable local URL is:

```text
http://127.0.0.1:4100
```

Service records are discovery records, not full API documentation. They should
store a service id, display name, `baseUrl`, and entry point paths:
`availability`, `guide`, `contract`, and `api` when available. Read responses
should include full `endpoints.availability`, `endpoints.guide`,
`endpoints.contract`, and `endpoints.api` URLs.

The config service must publish its own agent guide and strict contract using
the same guide/contract pattern expected from other agent-facing services. Its
guide should explain how services discover the config service, how startup
self-registration works, which write operations are allowed, and which fields
must never contain secrets. Its contract should define the exact schemas and
methods for listing records, reading records, creating records, updating
records, conflict handling, validation errors, and optimistic concurrency if
supported.

Service self-registration is allowed only through the documented config-service
contract. A self-registering service may select or request a new local
development port only through that contract, after reading current
config-service records and checking local host availability when the contract
requires the service to propose a value. It must start with the value recorded
by config-service. If startup cannot bind the recorded port, the service must
stop, reread config-service, verify the current port owner, and retry only
through the documented conflict policy or report a clear blocker. The service
must not silently select another free port, overwrite its record to escape the
conflict, or stop an unverified process.

Do not store endpoint catalogs, schemas, authentication details, workflow logic,
or secrets in config-service. After discovery, ask an agent-facing target
service for its onboarding guide through `endpoints.guide` when present, then
ask for its strict protocol through `endpoints.contract`.

## Agent-Facing Service Guides

Agent-facing HTTP services should expose both a compact service-owned guide and
a strict contract. Prefer generic routes such as `GET /agent/guide` and
`GET /agent/contract`, or adapter-specific equivalents such as
`GET /agent-intake/guide` and `GET /agent-intake/contract`.

The guide is onboarding for external agents. It should explain discovery,
startup steps, allowed actions, forbidden actions, ownership boundaries,
required capabilities, safe payload examples, error policy, privacy policy, and
guide/contract version fields. It must not include secrets, cookies, raw private
payload dumps, production data, or large logs.

The contract is workflow validation. It should define schemas, methods,
capabilities, lifecycle identifiers, error shapes, and state-changing operations
the service actually supports.

Agents should read `endpoints.guide` first when present, then
`endpoints.contract` before sending tasks, plans, or state-changing requests. If
the guide and contract disagree about required endpoints, lifecycle ownership,
or permissions, stop and report the mismatch. Do not infer permissions from
filesystem paths, stale memory, old dashboard URLs, or raw intake receipts.

## Task Managers

Project task-manager config should store the selected manager name or service id
only, plus non-secret project preferences such as workspace, project, and intake
mode. Do not store or copy task-manager runtime URLs in project memory when the
manager is registered in config-service.

Task-manager commands are routine service-integration commands once the user
has supplied the sprint/task content or selected the workflow. Treat them like
other deterministic `gi` operations: resolve the service, verify the contract,
send the documented payload, read back the result, and report blockers. Do not
replace manager API work with project-memory notes, raw receipts, guessed
commands, local checklists, or a request for the user to provide the exact
manager command.

For `gi manager`, `gi tm`, `gi manager test`, `ги менеджер`, `ги манагер`,
`gi active task`, `gi next task`, `gi add sprint`, `gi create sprint`,
`gi plan`, `gi start sprint`, `gi sprint start`, and sprint workflows:

1. Read the enabled manager id or `service_id` from project-local task-manager
   config.
2. Resolve that id through config-service with `GET /services/{serviceId}`.
3. Read `endpoints.guide` when present for manager onboarding and forbidden
   actions.
4. Read `endpoints.contract` to learn the current task-manager API.
5. Use `endpoints.api` for manager operations.
6. Report a concise blocker if the manager id is missing or config-service has
   no matching service record.
7. Stop instead of guessing alternate endpoints when the guide or contract lacks
   active-task lookup, sprint/cycle creation, lifecycle update, completion, or
   requested object type.
8. Ignore legacy `base_url` values in project memory unless a project-local
   migration rule explicitly says to convert them into a config-service record.

`gi start sprint`, `gi sprint start`, and equivalent active-sprint wording are
task-manager workflows. They must not be reduced to generic `gi start` context
restore when a configured manager exists.

`gi local sprint`, `gi sprint local`, `gi локальный спринт`,
`gi спринт локально`, and equivalent explicitly local sprint wording are the
local alternative. They do not use config-service, do not create or update
task-manager objects, and must clearly report that no visible manager-backed
Sprint/Cycle was created or synchronized.

## FTP Services

Projects that need FTP, FTPS, or SFTP should resolve shared FTP services through
config-service before asking the user for host details or creating a purely
project-local deploy config.

Use `gi ftp service`, `gi ftp сервис`, or `ги фтп сервис` to manually register,
inspect, or select an FTP/FTPS/SFTP service record. This command must not upload
files.

FTP-capable service records should expose non-secret discovery metadata only:
service id, display name, protocol, base URL or host/port when policy allows it,
endpoint paths, capability tags, and secret reference names such as
`passwordEnv`. Do not store raw passwords, tokens, private keys, or private
remote paths in config-service.

When resolving FTP for a project:

1. Read the project-local FTP config and selected `serviceId`, if present.
2. If no `serviceId` is selected, query config-service for FTP-capable services.
3. If exactly one matching service exists, read and verify its contract, then
   use it.
4. If several matching services exist, ask the user to choose with the plain
   inline numbered checkbox marker style used by language selection, such as
   `[ ] 1. Display name (service-id)`, and accept numeric replies against the
   latest checklist.
5. If no matching service exists, offer `gi ftp service` as the command to
   register one manually, then fall back to project-local FTP config only when
   the user provides project-specific details.

## Project-Local Overrides

Use project-local overrides only for explicit project needs, such as selecting a
non-default config service during local development. Keep those overrides small
and documented in project-local instructions.

Do not put secrets, API tokens, cookies, passwords, or private production data
in registry JSON.
