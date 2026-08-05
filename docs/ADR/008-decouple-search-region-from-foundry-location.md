# ADR-008: Azure AI Search Deploys to a Region Decoupled From the Foundry Primary Location

## Status

Accepted

## Date

2026-08-05

## Context

[ADR-007](./007-foundry-iq-knowledge-bases-require-azure-ai-search.md) establishes that Azure
AI Search must be provisioned. It cannot be provisioned in East US 2, which is where the rest
of this solution lives.

The first provisioning attempt of `macae-flw-v1` failed with:

```
Microsoft.Search/searchServices — InsufficientResourcesAvailable
The region 'eastus2' is currently out of the resources required to provision new services.
Try creating the service in another region.
```

This is not a subscription quota problem. Basic-tier Search quota in East US 2 reads
`currentValue: 0, limit: 12`. It is physical regional capacity exhaustion, and Microsoft
publishes it as an ongoing condition rather than a transient one: the Azure AI Search region
table carries a standing footnote against East US 2 (and East US, West US, West US 2, North
Europe) reading "This region is experiencing capacity constraints that prevent the creation of
new search services and scaling operations. Please choose a different region." Microsoft's
guidance offers exactly two remediations — deploy to an alternative region (recommended), or
retry off-peak over a window of several days — and **no** capacity-request or quota-increase
path.

The obvious response was to move the whole solution to another region. That was rejected once
the constraint was located precisely. The accelerator enforces two region allowlists whose
intersection is only Australia East, East US 2, Japan East and UK South — but **those
allowlists bind the Foundry primary location, not Azure AI Search.** Nothing required Search to
sit in the same region.

Microsoft documents no same-region requirement between a Foundry project and its backing Search
service. The Foundry IQ connect article contains no regional language at all; the connection is
a `RemoteTool` / `ProjectManagedIdentity` project connection whose `target` is a public
`*.search.windows.net` HTTPS endpoint authenticated by an Entra token for the global
`https://search.azure.com/` audience. The same-region rules that *do* exist bind the Foundry
resource to its virtual network, and Azure OpenAI to its Foundry account — neither involves
Search. Co-location is documented as a latency optimisation, with US-to-US round trips of
26–50 ms and the note that "under 50 ms RTT isn't perceptible" for search workloads.

At the point of this decision, everything except Search had already provisioned successfully in
East US 2: the Foundry account and project, Cosmos DB, the container registry, storage, App
Insights, Log Analytics, the managed identity and the Container Apps environment.

## Decision

**Azure AI Search deploys to its own region, independent of the solution's primary location.**

The `ai_search` module takes a dedicated `searchServiceLocation` parameter that defaults to the
solution location, so the decoupling costs nothing when the primary region has capacity.

For this deployment the primary location stays **East US 2** and Search deploys to
**Central US**.

Because Azure exposes no way to check Search capacity before attempting a create — `usages`
returns quota only, `checkNameAvailability` checks names, and ARM `validate` checks only
template schema — the region is confirmed by **probing**: create a single throwaway Basic
service in the candidate region, confirm, delete it, then provision. On capacity failure the
agreed fallback order is **Central US → South Central US → Canada Central**, all of which offer
agentic retrieval and none of which Microsoft currently flags as capacity-constrained.

## Verification

On 2026-08-05, a one-replica, one-partition Basic service named
`srch-macae-capacity-probe-cus` was created in Central US. Its provisioning state reached
`succeeded` with a system-assigned identity. The service and its isolated, tagged resource
group (`rg-macae-search-capacity-probe-centralus`) were then deleted. Central US is therefore
the verified first choice; the fallback order remains **Central US → South Central US → Canada
Central**.

## Considered Options

- **Migrate the whole solution to UK South, Japan East or Australia East.** All three are
  viable on the model roster once `gpt-image-1.5` is dropped, and all three avoid the capacity
  problem. Rejected because it discards a working environment to relocate one resource, and
  because those three regions offer *no* image-generation model of any kind, permanently
  foreclosing an option East US 2 keeps open.
- **Retry East US 2 off-peak.** Rejected as the primary plan: Microsoft frames the retry window
  as several days, describes constraints as only "sometimes" temporary, and explicitly says
  retrying "isn't a substitute for evaluating an alternative region." Unsuitable for work with
  a demo date.
- **Downgrade to the Free tier in East US 2.** Impossible. ADR-007 records that managed-identity
  access to deployed models requires Basic or higher, and Microsoft additionally reclaims idle
  Free services in capacity-constrained regions.

## Consequences

- **Positive:** The already-provisioned East US 2 environment is preserved. The change is one
  Bicep parameter rather than a full re-provision. Foundry and the model deployments stay in
  the only allowlisted region carrying the full model catalogue.
- **Negative:** Search calls cross a region boundary, adding a documented 26–50 ms round trip,
  and cross-region traffic carries egress cost. Both are immaterial at demo scale.
- **Operational:** The solution is no longer single-region. Anything that assumes one location
  — diagnostics, cost attribution, data-residency review — must account for the split.
- **Reversible:** If East US 2 Search capacity recovers, set `searchServiceLocation` back to the
  solution location and re-provision. Microsoft documents tooling for moving Search indexes
  across regions in either direction.

## References

- [ADR-007: Foundry IQ Knowledge Bases Keep Azure AI Search as a Deployment Dependency](./007-foundry-iq-knowledge-bases-require-azure-ai-search.md)
- [Azure AI Search regional capacity constraints](https://learn.microsoft.com/en-us/azure/search/search-region-capacity)
- [Azure AI Search region support (agentic retrieval availability)](https://learn.microsoft.com/en-us/azure/search/search-region-support)
- [Connect Foundry IQ knowledge bases to a Foundry project](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/foundry-iq-connect)
- Issue [#28](https://github.com/bradcstevens/az-multi-agent-flw-demo/issues/28)
