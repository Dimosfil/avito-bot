## Content And Authoring

- Keep instructions reusable across projects.
- Do not add secrets, credentials, private project data, or local machine paths
  unless the file is explicitly a local example.
- If a rule applies only to one specific project, do not put it here.
- If a feature workflow applies only to one project, keep it in that project's
  local docs or project memory. Use shared instructions only for the reusable
  rule that such contracts should exist and be respected.
- When explaining, documenting, or adding a shared GI rule, keep the explanation
  project-agnostic. Do not anchor the rule in the current project, a recent bug,
  one demo, one product name, or one repository unless the user explicitly asks
  for that concrete comparison. Use neutral terms such as "a development tool",
  "a generated product", "a selected run", or "a service"; if an example is
  necessary, mark it as illustrative and keep it replaceable.
- When deriving a reusable rule from a concrete request, bug, screenshot, demo,
  or implementation detail, extract the portable principle before writing the
  rule. Do not promote incidental entities, object types, years, filenames,
  local paths, data partitions, model names, UI labels, query text, or one
  selected workflow into shared defaults, policies, architecture, or examples.
  Treat the concrete case as evidence, then restate it in neutral terms and map
  the principle to configuration, contracts, adapters, manifests,
  user-selected state, or project-local memory as appropriate.
- Prefer small, focused documents over one giant policy file.
- When adding a new instruction file, also add it to `INDEX.md`.
- Write instruction documents in imperative voice, with one rule per bullet when
  practical.
- Avoid long nested conditionals, filler, narration, and non-actionable prose.
- Use clear Markdown headings and copy-pasteable examples.
- Keep developer tools, orchestrators, task managers, agent harnesses, and code
  generators separate from the products they build. Never hard-code one demo,
  customer, project type, workflow run, product name, UI label, folder slug,
  stack, or task contract as if it were part of the development runtime.
  Generated applications, sites, bots, dashboards, libraries, and other
  artifacts are input/output of the tool, not the tool's identity. Model
  selected or active workflow state as data, show debug/progress logs only for
  the selected run, and keep completed runs compact. Follow
  `patterns/DEVELOPMENT_TOOL_PRODUCT_BOUNDARIES.md`.
- Do not hard-code values that can change by deployment, user choice, runtime
  environment, host machine, service discovery, credentials, filesystem layout,
  feature flags, product names, demo data, workflow labels, generated artifact
  names, UI copy that names a specific project, language translation maps,
  synonym dictionaries, intent-interpretation rules, query-normalization rules,
  model-specific prompt expansions, ranking thresholds, or operational policy.
  Keep application code focused on logic, constants, and internal defaults; move
  deploy/user/environment/system/product-selection/model-behavior values into
  documented project-local configuration, environment variables, service
  discovery records, manifests, task payloads, resource files, adapters,
  interpretation/translation modules, or user-selected state. Such modules may
  be deterministic resources, local algorithms, retrieval-backed components, or
  provider-swappable LLM adapters. Avoid embedding machine-specific absolute
  paths in source or shared instructions; when paths are accepted from config,
  resolve and validate them as absolute paths at the application boundary. When
  applying this rule to existing projects, audit and refactor relevant
  hard-coded values instead of only adding the rule text. Follow
  `patterns/CONFIGURATION_BOUNDARIES.md`.
- Build applications with clear architecture and code-quality boundaries. Apply
  OOP, SOLID, DRY, clean-code, maintainability, and extensibility principles
  where they fit the stack. Keep domain/product logic, orchestration, UI,
  persistence, filesystem, external services, and configuration in separate
  layers with explicit contracts. Follow
  `patterns/ARCHITECTURE_AND_CODE_QUALITY.md`.
- Keep the current technology stack visible in durable project memory. For
  GI-enabled projects, maintain `tools/project-memory/specs/technology-stack.md`
  or an equivalent linked stack inventory with verified languages, runtimes,
  frameworks, package managers, build/test tools, storage, external services,
  commands, evidence paths, and open verification gaps. Update it when stack
  components are added, removed, upgraded, replaced, or materially
  reconfigured. Follow `patterns/TECHNOLOGY_STACK_INVENTORY.md`.
- After any meaningful implementation, refactor, migration, or configuration
  cleanup batch, verify the batch at the right abstraction level. Check all
  touched layers for duplicated defaults, policies, workflows, contracts, or
  interpretation rules; keep one authoritative source where possible; update
  durable project-memory specs when behavior or architecture changes; inspect
  the changed-file list for unrelated edits or generated noise; and separate
  harmless line-ending warnings from real whitespace errors in `git diff
  --check`. Follow `patterns/COHERENT_BATCH_VERIFICATION.md`.
