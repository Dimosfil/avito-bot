# Avito Autoload Tools

These scripts preserve the verified workflow for publishing regional service
listings through the official Avito Autoload API.

## Safety Contract

- Keep `AVITO_CLIENT_ID` and `AVITO_CLIENT_SECRET` in environment variables.
- Never pass secrets as command-line parameters or write them to manifests.
- Generate and inspect XML before changing the Avito profile.
- Use a stable, controlled public HTTPS URL for production feeds.
- Treat `StartUpload` as a real publication action that can consume a package
  placement.
- Prefer `ListingFee=Package` for guarded trials. It does not fall back to a
  one-time wallet charge when no matching package exists.
- Do not create fictional locations or misleading regional availability.
- Keep a stable unique `Id` for every service-and-city pair.

## 1. Build A Regional Feed

Copy the example manifest and replace its placeholder image URL, descriptions,
and truthful addresses:

```powershell
Copy-Item `
  .\tools\avito-autoload\examples\regional-services.example.json `
  .\tools\avito-autoload\regional-services.local.json
```

`*.local.json` files are ignored by git. Generate XML:

```powershell
.\tools\avito-autoload\New-AvitoRegionalFeed.ps1 `
  -ManifestPath .\tools\avito-autoload\regional-services.local.json `
  -OutputPath .\tools\avito-autoload\regional-services.local.xml
```

The generator supports either explicit `ads`, or a shared `template` expanded
over `cities`. Template values may contain `{City}` and `{CitySlug}`.

## 2. Check API Access

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 -Action CheckAccess
```

If the account has no Autoload profile yet, initialize a disabled one:

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action InitializeProfile `
  -ConfirmChange
```

## 3. Inspect Category Fields

Find the current category slug when it is not already known:

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action GetCategoryTree
```

For the verified AI-services category:

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action GetCategoryFields `
  -NodeSlug ii_resheniya_neiroseti
```

Always retrieve the current field schema before introducing a new category.

## 4. Publish The Feed At A Stable HTTPS URL

The API accepts a URL, not a local file upload. Host the generated XML at a
stable public HTTPS URL controlled by the operator. Temporary paste services
are suitable only for a short diagnostic and must not be the production source
of truth.

Configure the profile in a disabled state first:

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action SetProfile `
  -FeedUrl "https://example.com/feeds/avito-services.xml" `
  -FeedName "Regional services" `
  -AutoloadState Disabled `
  -Rate 1 `
  -TimeSlot 12 `
  -ConfirmChange
```

After reviewing the profile, enable it with the same command and
`-AutoloadState Enabled`.

## 5. Start And Monitor A Real Upload

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action StartUpload `
  -ConfirmPublish

.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action WatchCurrentUpload `
  -PollSeconds 5 `
  -MaxPolls 24
```

Useful item section slugs include:

- `success_added`: a new listing was activated;
- `success_skipped`: the stable feed item was already synchronized;
- `need_sync`: Avito accepted the item and is synchronizing it;
- `publish_later`: Avito queued publication for a later stage;
- `duplicate`: Avito detected matching descriptions;
- `linker`: Avito needs a decision about linking to an existing listing.

Do not report success until the upload reaches a terminal successful state and
the returned public URL opens in the intended city.

## 6. Inventory Current Listings

Record the current active inventory before and after every rollout:

```powershell
.\tools\avito-autoload\Invoke-AvitoAutoload.ps1 `
  -Action GetItems `
  -ItemStatus active
```

Store compact rollout evidence under `docs/avito-autoload/`; do not put raw API
responses, credentials, tokens, or customer data in project memory.
