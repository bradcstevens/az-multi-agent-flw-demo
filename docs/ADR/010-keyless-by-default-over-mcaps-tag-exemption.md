# ADR-010: Keyless by default — do not apply the standard MCAPS local-auth tag exemption

## Status

Accepted

## Date

2026-08-12

## Issue

#11 (spec #1)

## Context

Deployments into an MCAPS subscription routinely hit Azure Policy denials for resources with
local (key-based) authentication enabled. The standard, widely-circulated remedy is to tag the
resource group `SecurityControl=Ignore`, which exempts it from those policies, and then deploy
whatever the template produces.

Applying that remedy here would be **cargo cult**. The MACAE baseline is **already keyless by
design**, without any change from us:

- local auth disabled on Cognitive Services, Cosmos DB and Azure AI Search;
- the container registry admin user disabled;
- every service-to-service call authenticated by **managed identity**.

So the local-auth policies have nothing to deny. They are a no-op against this template. The
exemption tag would not unblock anything — it would only remove a guardrail that is currently
free, and it would do so on a subscription that is not ours.

## Decision

**Do not apply the `SecurityControl=Ignore` tag, and do not set local auth to enabled anywhere
in the templates.** Keyless-by-default is treated as a property of this build to be preserved,
not an accelerator default to be worked around.

Two cheap hardening additions are made while in the templates, in the same spirit:

1. **Disable shared-key access on the storage account.**
2. **Pass the common tag set to the AI Foundry project module**, which currently deploys
   completely untagged.

The **"reuse an existing Foundry project" deployment path is avoided** — the deployer role
grants on that path are commented out upstream, so it produces an environment whose access is
not what the template appears to say.

**Scope: the vanilla flavour.** Keyless-by-default is inherited from the accelerator and holds
across flavours, but the two hardening additions are made in the vanilla module only —
`allowSharedKeyAccess: false` is set at `infra/bicep/main.bicep:377`, while the AVM path does
not override it and the underlying module defaults it to `true`. **An AVM deployment is
therefore not shared-key-free.** This build deploys vanilla; a flavour switch must carry that
property across.

If a policy denial ever does occur, the response is to find which resource is asking for a key
and remove that need — not to reach for the tag.

## Considered Options

- **Apply the tag pre-emptively, as most MCAPS deployment guides advise.** Rejected: a pure
  security downgrade in exchange for unblocking nothing. It also makes a later, real denial
  invisible.
- **Leave storage shared-key access as shipped.** Rejected: it is the one remaining key-based
  door in an otherwise keyless deployment, and closing it is a single template property.

## Consequences

- **Positive:** The demo is defensible on governance — the identity story R5 tells at the
  application layer is matched by the infrastructure underneath it, rather than contradicted.
- **Negative:** A future component that genuinely needs a key (an SDK without managed-identity
  support, say) will hit a policy denial and need real work rather than a tag.
- **Operational:** RBAC propagation delay is the expected first-deploy failure mode instead of
  an auth failure — expect a possible first-pull failure from the container registry and plan a
  two-pass deploy or a restart rather than treating it as a defect.

## References

- [ADR-004: Fork MACAE by merging the pinned upstream commit into this repository](./004-fork-macae-at-pinned-upstream-commit.md)
- `infra/` — local-auth properties on Cognitive Services, Cosmos DB, AI Search and the registry
