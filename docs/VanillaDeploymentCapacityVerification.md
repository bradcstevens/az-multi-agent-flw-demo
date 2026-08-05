# Vanilla Deployment Capacity Verification

**Issue:** #28
**Date:** 2026-08-02, corrected 2026-08-05
**Subscription:** `3523b0e6-bb53-4e87-8340-25c416e26093`

> **Correction notice (2026-08-05).** The original version of this document concluded that no
> capacity-supported region existed and that East US 2 had failed on *two* counts. Both claims
> were wrong. Only one resource failed on capacity, and the region requirement it was measured
> against included a model this build never uses. The corrected findings are below; the
> superseded conclusion is preserved at the end so the citations to it remain intelligible.

## Result

**East US 2 is the correct primary location. Azure AI Search deploys separately to Central US.**

Exactly one resource cannot be provisioned in East US 2 — the Azure AI Search service — and the
accelerator's region allowlists do not apply to it. Decoupling its region resolves the blockage
without moving anything else. See
[ADR-008](./ADR/008-decouple-search-region-from-foundry-location.md).

## What Actually Failed

Both failures were read from the ARM deployment operations of `rg-macae-flw-v1`:

| Resource | Error | Diagnosis |
| --- | --- | --- |
| `Microsoft.Search/searchServices` | `InsufficientResourcesAvailable` — "The region 'eastus2' is currently out of the resources required to provision new services." | **Genuine regional capacity exhaustion.** Real, and published by Microsoft as an ongoing condition. |
| `Microsoft.App/containerApps` (`ca-mcp-...`) | `ContainerAppOperationError` — "Failed to provision revision … Error details: **Operation expired**." | **A timeout, not capacity.** Misread originally as a Consumption capacity limit. |

The Container Apps diagnosis is refuted by three independent observations:

- The app's `runningStatus` is **Running** — on the accelerator's `containerapps-helloworld`
  bootstrap placeholder.
- Resource group `rg-vislab-c8cfd5` runs `ca-frontend` and `ca-backend` on the Consumption
  profile **in East US 2**, concurrently.
- The Container Apps *environment* `cae-macaeflwv1flrpd` provisioned `Succeeded` in East US 2.

Azure AI Search quota was never the constraint. Basic-tier usage reads `currentValue: 0,
limit: 12` in all four candidate regions; the failure is physical capacity, which no
subscription-level quota API reports.

Separately, the container registry `crmacaeflwv1flrpd` holds **zero repositories**. No
application image was ever pushed, which is the actual reason no workload runs. That is a
post-provision step, not a capacity problem.

## Model Roster

The roster requirement was overstated. Spec #1 records that the stock template's image model is
one "this build never uses", to be removed if it constrains deployment. It has been dropped, so
the required GlobalStandard roster is:

- `gpt-5.4` (`2026-03-05`)
- `gpt-5.4-mini` (`2026-03-17`)
- `text-embedding-3-small` (`1`)

| Region | Required roster | `gpt-image-1.5` | Any image model |
| --- | --- | --- | --- |
| Australia East | ✅ all three | ❌ | ❌ **none of any kind** |
| East US 2 | ✅ all three | ✅ | ✅ `gpt-image-1`, `-1-mini`, `-1.5`, `-2` |
| Japan East | ✅ all three | ❌ | ❌ **none of any kind** |
| UK South | ✅ all three | ❌ | ❌ **none of any kind** |

Two corrections to the original table. First, all four regions satisfy the *actual* roster —
the original table's "No" verdicts turned entirely on the dropped image model. Second, the
original stated only that `gpt-image-1.5` was unavailable elsewhere; in fact those three regions
offer **no image-generation model at all**, so "substitute a different image model" was never an
available option. East US 2 quota showed `gpt-image-1.5` at 5/9 — headroom, not pressure.

## Why the Region Was Not Changed

The two accelerator allowlists intersect at Australia East, East US 2, Japan East and UK South,
and with the image model dropped all four are viable. A migration was still rejected: those
allowlists bind the **Foundry primary location**, not Azure AI Search, and Microsoft documents
no same-region requirement between a Foundry project and the Search service backing a
Foundry IQ Knowledge Base. Moving everything would discard a working environment — Foundry,
Cosmos DB, ACR, storage, App Insights, Log Analytics, managed identity and the Container Apps
environment had all provisioned `Succeeded` — in order to relocate one resource, while
permanently foreclosing image models. Full reasoning in
[ADR-008](./ADR/008-decouple-search-region-from-foundry-location.md).

## Search Region Selection

Central US, with fallback order **Central US → South Central US → Canada Central**. All three
offer agentic retrieval and none carry Microsoft's capacity-constraint footnote. Basic tier or
higher is mandatory because model access is managed-identity only
([ADR-007](./ADR/007-foundry-iq-knowledge-bases-require-azure-ai-search.md)).

Azure exposes **no pre-create capacity check**: `usages` returns quota, `checkNameAvailability`
checks names, and ARM `validate` checks only template schema. The region is therefore confirmed
by creating a single throwaway Basic service, verifying, and deleting it before provisioning.

## On the AZD Preview

```sh
azd provision --preview --no-prompt
```

The preview succeeded in 27 seconds for `macae-flw-v1` in East US 2. This remains true and
remains uninformative: an AZD preview is an ARM plan, not a capacity reservation, and it cannot
detect `InsufficientResourcesAvailable`. It is not evidence for or against any region.

## Superseded Conclusion (2026-08-02)

> No capacity-supported, single-region replacement is currently available for the vanilla
> deployment. […] Before provisioning, either select an image model available in another allowed
> region or approve a cross-region Foundry deployment.

Wrong on three counts: it treated a never-used image model as mandatory, attributed a timeout to
regional capacity, and offered an image-model substitution that no candidate region could
satisfy. The real choice was cross-region **Search**, not cross-region Foundry.
