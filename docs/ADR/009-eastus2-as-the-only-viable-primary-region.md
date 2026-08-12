# ADR-009: East US 2 is the primary region, and `swedencentral` and `eastus` are invalid

## Status

Accepted

## Date

2026-08-12

## Issue

#11 (spec #1)

## Context

The superseded requirements document told the build to "use a documented region — East US2,
Sweden Central, UK South." Two of those three are wrong for the primary `location` parameter,
and the reason is not obvious from reading the template casually: `infra/main.bicep` enforces
**two different region allowlists**, and a region has to satisfy **both**.

| Parameter | Allowlist (`infra/main.bicep`) |
| --- | --- |
| `location` — app, data and monitoring resources | `australiaeast`, `centralus`, `eastasia`, `eastus2`, `japaneast`, `northeurope`, `southeastasia`, `uksouth` |
| `azureAiServiceLocation` — AI Services and Foundry | `australiaeast`, `eastus2`, `francecentral`, `japaneast`, `norwayeast`, `swedencentral`, `uksouth`, `westus`, `westus3`, `polandcentral`, `uaenorth` |

The intersection is **`australiaeast`, `eastus2`, `japaneast`, `uksouth`** — four regions.

- **`swedencentral` is invalid**: it is in the `azureAiServiceLocation` list only. That is
  exactly why the claim looks right at a glance — the region genuinely is allowed for Foundry,
  just not for the resources the same deployment has to place alongside it.
- **`eastus` is invalid**: it appears in **neither** list.

At the time of the original survey a third constraint narrowed the four further: the stock
model roster included `gpt-image-1.5`, whose regional availability left only one region able to
carry the full roster. That model has since been removed from every deployment profile because
this build never calls it, which restores the other three as genuine fallbacks.

## Decision

**The primary location is `eastus2`, with `azureAiServiceLocation` also `eastus2`.**

The deployable set is `australiaeast`, `eastus2`, `japaneast`, `uksouth`. Any of the other
three is a valid fallback for a fresh environment; `eastus2` is the choice for this one because
the environment is already provisioned there and it carries the widest model catalogue of the
four, keeping options open that the others foreclose.

**`swedencentral` and `eastus` are not fallbacks. They are invalid inputs** and will fail
template validation, not deployment — so an operator who tries either gets a parameter error
rather than a partially-created environment.

Azure AI Search is explicitly **not** bound by this decision: it deploys to its own region via
`searchServiceLocation`, for capacity reasons recorded in
[ADR-008](./008-decouple-search-region-from-foundry-location.md).

## Scope: the vanilla flavour

`infra/main.bicep` dispatches to one of three deployment flavours — `bicep` (vanilla), `avm` and
`avm-waf` — and **this build deploys vanilla**. The region allowlists above are enforced by the
dispatcher and therefore bind **all three**, but the Search decoupling does not:
`searchServiceLocation` is passed to the vanilla module only, and `infra/avm/main.bicep` deploys
Search into `location`. **An AVM deployment would put Search back in the primary region and hit
the capacity failure ADR-008 records.** Anyone switching flavours must carry that parameter
across first.

## Considered Options

- **Follow the superseded document and use `swedencentral`.** Rejected: it fails the `location`
  allowlist. This is the correction, not an option.
- **Deploy to `uksouth`, `japaneast` or `australiaeast`.** All three are valid and remain the
  documented fallback set. Rejected for this environment only because everything is already
  provisioned in `eastus2` and relocating buys nothing.
- **Relax the allowlists in the template.** Rejected: the allowlists encode real model and
  service availability. Widening them moves the failure from template validation — where it is
  a clear parameter error — to a half-finished deployment.

## Consequences

- **Positive:** Region selection is a checked constraint, failing at validation time.
- **Negative:** The deployable set is four regions wide, none of them in the EU. Any future
  data-residency requirement forces `uksouth` and a re-provision.
- **Operational:** The solution is not single-region — Search sits elsewhere (ADR-008). Anything
  that assumes one location must account for the split.

## References

- [ADR-008: Azure AI Search Deploys to a Region Decoupled From the Foundry Primary Location](./008-decouple-search-region-from-foundry-location.md)
- [Correction 5](../superseded-requirements-corrections.md#5-swedencentral-and-eastus-are-invalid-primary-regions)
- `infra/main.bicep` — both `@allowed` lists
