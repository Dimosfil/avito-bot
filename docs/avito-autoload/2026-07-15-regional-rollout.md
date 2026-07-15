# Avito regional rollout — 2026-07-15

## Outcome

Avito accepted and activated all 10 records in upload `566472247`. Nine regional
listings were added and the previously tested Moscow listing was updated. No
`duplicate`, `linker`, rejection, or package-payment error appeared in the item
results. The post-rollout API inventory contained 11 active listings, including
the original Voronezh listing outside this feed.

| External ID | City | Result | Avito ID |
| --- | --- | --- | ---: |
| `ai-bots-moscow-001` | Moscow | `success_updated` | 8249789331 |
| `ai-bots-saint-petersburg-001` | Saint Petersburg | `success_added` | 8249434398 |
| `ai-bots-kazan-001` | Kazan | `success_added` | 8249832557 |
| `ai-bots-yekaterinburg-001` | Yekaterinburg | `success_added` | 8249187238 |
| `ai-bots-novosibirsk-001` | Novosibirsk | `success_added` | 8248964391 |
| `ai-bots-nizhny-novgorod-001` | Nizhny Novgorod | `success_added` | 8249035723 |
| `ai-bots-krasnodar-001` | Krasnodar | `success_added` | 8248874021 |
| `ai-bots-rostov-on-don-001` | Rostov-on-Don | `success_added` | 8249248848 |
| `ai-bots-samara-001` | Samara | `success_added` | 8249783897 |
| `ai-bots-ufa-001` | Ufa | `success_added` | 8249040144 |

## Configuration and verification

- The feed contained 10 unique stable IDs and truthful city locations.
- Every record used `ListingFee=Package`, `AdStatus=Free`, price 5,000 RUB, and
  10 source images.
- The profile processed the scheduled 17:00 Moscow upload on 2026-07-15.
- The upload API reported 10 successful items; the inventory API independently
  confirmed every mapped Avito ID as active.
- Avito emitted only the informational activation message and the expected
  warning that the account phone number was inserted automatically.

## Remaining operational work

The profile still depends on a disposable diagnostic feed host. Move the feed
to a stable operator-controlled HTTPS endpoint before treating the rollout as a
durable unattended process. Keep the local manifest and generated XML ignored;
credentials, access tokens, account metadata, and temporary feed URLs are not
stored in the repository.
