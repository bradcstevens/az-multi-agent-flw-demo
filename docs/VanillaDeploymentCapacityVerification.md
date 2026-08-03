# Vanilla Deployment Capacity Verification

**Issue:** #28
**Date:** 2026-08-02
**Subscription:** `3523b0e6-bb53-4e87-8340-25c416e26093`

## Result

No capacity-supported, single-region replacement is currently available for
the vanilla deployment. Do not deploy the current profile outside East US 2,
and do not treat its successful preview as proof that Basic Azure AI Search or
Consumption Container Apps capacity can be allocated.

## Candidate Evaluation

The intersection of the Bicep `location` and `azureAiServiceLocation` allowlists
is Australia East, East US 2, Japan East, and UK South. Each candidate was
queried with `az cognitiveservices model list` for the required GlobalStandard
model versions:

- `gpt-5.4` (`2026-03-05`)
- `gpt-5.4-mini` (`2026-03-17`)
- `gpt-image-1.5` (`2025-12-16`)
- `text-embedding-3-small` (`1`)

| Region | Full roster available | Result |
| --- | --- | --- |
| Australia East | No | `gpt-image-1.5` is unavailable. |
| East US 2 | Yes | The only allowed region with all four models; known Basic Search and Consumption Container Apps allocation failures still block deployment. |
| Japan East | No | `gpt-image-1.5` is unavailable. |
| UK South | No | `gpt-image-1.5` is unavailable. |

The East US 2 quota snapshot reported the configured model usage and limits:
`gpt-5.4` 680/3,000, `gpt-5.4-mini` 250/3,000,
`gpt-image-1.5` 5/9, and `text-embedding-3-small` 120/1,000.

## AZD Preview Evidence

```sh
azd provision --preview --no-prompt
```

The preview succeeded in 27 seconds for environment `macae-flw-v1` in East US
2. It planned a new Search service, new Container Apps, and changes to the
existing Container Apps environment, Foundry resources, and four model
deployments. The command applied no changes.

An AZD preview is an ARM plan, not a capacity reservation. It cannot validate
the Basic Search allocation or a new Consumption Container Apps revision, so
this success does not overturn the reported East US 2 allocation failures.

## Unblock Condition

Before provisioning, either select an image model available in another allowed
region or approve a cross-region Foundry deployment. Re-run the model catalog,
quota check, and AZD preview after that decision.
