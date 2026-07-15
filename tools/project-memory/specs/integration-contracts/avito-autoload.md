# Avito Regional Autoload Contract

## Purpose

Preserve the verified workflow for creating regional copies of a truthful
service offer through the official Avito Autoload API. This workflow supports
one-city trials and later service-by-city matrices without browser automation.

This is an operator tool and integration contract. It is not part of the
Module 2 incoming-conversation runtime.

## Verified Outcome

On 2026-07-15, the workflow was verified against a real Avito professional
account and the `ИИ-решения, нейросети` service category:

1. OAuth client-credentials authentication succeeded.
2. `GET /autoload/v2/profile` initially returned `403` while category docs were
   readable.
3. `POST /autoload/v2/profile` successfully created a disabled Autoload profile.
4. A one-item XML feed for Moscow was configured and enabled.
5. `POST /autoload/v1/upload` started processing.
6. The item progressed through `publish_later`, `need_sync`, and
   `success_added`.
7. Avito assigned a public item ID and activated the listing in Moscow.
8. The approved 10-city feed was processed: Moscow was updated and nine new
   regional items were added; all 10 feed items were verified active.
9. The account inventory after rollout contained 11 active listings: the 10
   Autoload-managed cities plus the original Voronezh listing.

Keep this as compact integration evidence. Do not store the credentials,
access token, account metadata, temporary diagnostic feed URL, or full remote
responses.

## Official API Flow

```text
environment credentials
        |
        v
POST /token
        |
        +--> GET /autoload/v1/user-docs/tree
        +--> GET /autoload/v1/user-docs/node/{node_slug}/fields
        |
reviewed manifest --> generated XML --> controlled public HTTPS URL
                                             |
                                             v
                              POST /autoload/v2/profile
                                             |
                                             v
                               POST /autoload/v1/upload
                                             |
                                             v
                         GET /autoload/v4/uploads/current[/items]
```

The upload endpoint does not accept the XML body directly. It starts processing
the feed URLs already stored in the Autoload profile.

## Configuration Boundary

- Read `AVITO_CLIENT_ID` and `AVITO_CLIENT_SECRET` from environment variables.
- Never accept the client secret as a script parameter.
- Never log bearer tokens or authorization headers.
- Keep local manifests and generated XML in ignored `*.local.json` and
  `*.local.xml` files.
- Host production feeds at a stable HTTPS URL controlled by the operator.
- Treat a temporary public paste URL as disposable diagnostic infrastructure,
  never as the durable feed source of truth.

## Feed Model

Each listing is a deterministic service-and-city record. Its `Id` is immutable
for the lifetime of that logical listing. Recommended form:

```text
{service-slug}-{city-slug}-{variant}
```

Changing the city while reusing the same `Id` mutates the existing logical
listing. Creating a new city requires a new stable `Id`.

The feed generator accepts:

- shared category and commercial defaults;
- a listing template;
- a city list with truthful display addresses or coordinates;
- city-specific title, description, and image overrides;
- explicit ads when template expansion is insufficient.

Do not vary copy or images solely to bypass duplicate detection. Regional
listings must represent real service availability and comply with current
Avito category rules.

## Verified Category Schema

For node slug `ii_resheniya_neiroseti`, the verified hierarchy is:

- `Category`: `Предложение услуг`
- `ServiceType`: `Деловые услуги`
- `ServiceSubtype`: `IT, дизайн, тексты`
- `ServiceSubspecies`: `ИИ-решения, нейросети`

Required business fields observed on 2026-07-15 include:

- `Id`, `Images`, `Title`, `Description`, and location;
- `Consultations`: `Есть` or `Нет`;
- `WorkWithContract`: `Да` or `Нет`;
- `Prepayment`: `Нужна` or `Нет`;
- `Place`: `Удалённо`, `У клиента`, or `У себя`.

Retrieve the live schema before every new category rollout. Do not treat this
snapshot as permanent because Avito can change fields and dependencies.

## Commercial Safety

`ListingFee` controls how publication is funded:

- `Package`: publish only when a matching package placement is available;
- `PackageBBL`: use a package, then fall back to a one-time wallet charge;
- `BBL`: force a one-time wallet charge and ignore a package.

Use `Package` for guarded trials. Require explicit user approval before using
`PackageBBL` or `BBL`.

`AdStatus=Free` means no paid promotion service is added. Promotion values can
also consume wallet funds and require separate approval.

## State And Success Rules

- Profile initialization must start with `autoload_enabled=false`.
- Configure and inspect a feed in the disabled state before enabling it.
- Treat `POST /autoload/v1/upload` as external state change and possible package
  consumption.
- A successful HTTP response means processing started, not that publication
  succeeded.
- Poll the current upload and item results until a terminal outcome.
- `success_added` is evidence that Avito activated a new item.
- `success_skipped` means the stable item was already synchronized.
- `need_sync` and `publish_later` are intermediate states.
- `duplicate` and `linker` require review; do not silently mutate IDs or copy to
  evade the decision.
- Verify the returned public URL, city, title, and intended commercial mode
  before reporting completion.

## Tooling

- Feed generator: `tools/avito-autoload/New-AvitoRegionalFeed.ps1`
- API operator: `tools/avito-autoload/Invoke-AvitoAutoload.ps1`
- Human runbook: `tools/avito-autoload/README.md`
- Example manifest:
  `tools/avito-autoload/examples/regional-services.example.json`

The scripts use PowerShell-native HTTP commands and contain no credentials or
account-specific defaults.
