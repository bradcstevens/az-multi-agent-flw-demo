# ADR-007: Foundry IQ Knowledge Bases Keep Azure AI Search as a Deployment Dependency

## Status

Accepted — supersedes [ADR-002](./002-foundry-iq-file-search-over-azure-ai-search.md)

## Date

2026-08-05

## Context

ADR-002 decided to replace `AzureAISearchTool` with Foundry IQ and recorded, under
Consequences, that this "eliminates Azure AI Search as a deployment dependency."

Half of that held and half of it did not.

The migration off `AzureAISearchTool` completed: there are **zero** references to it left
anywhere in `src/backend`. But ADR-002 described the replacement as `FileSearchTool` over
**managed vector stores**, which genuinely needs no Search resource. The implementation
landed somewhere else — on Foundry IQ **Knowledge Bases**, which are *backed by* Azure AI
Search:

- `src/backend/config/mcp_config.py:135` documents `KnowledgeBaseConfig` as
  "Configuration for Foundry IQ Knowledge Base (**MCP endpoint on Azure AI Search**)".
- `KnowledgeBaseConfig.from_env` raises `ValueError` when `AZURE_AI_SEARCH_ENDPOINT` is
  absent, so an agent with `use_knowledge_base: true` cannot start without a Search service.
- The connection it builds — a `RemoteTool` / `ProjectManagedIdentity` project connection
  named `{kb_name}-mcp` — is exactly the shape Microsoft documents for Foundry IQ, whose
  `target` is `{search_endpoint}/knowledgebases/{kb}/mcp`.
- `content_packs/content_gen/agent_teams/content_gen.json` sets `use_knowledge_base: true`
  with `knowledge_base_name: "macae-content-gen-products-kb"`, so this is a live path.
- `infra/bicep/main.bicep:893` wires `AZURE_AI_SEARCH_ENDPOINT` from
  `ai_search.outputs.endpoint` into the backend container.

The stale consequence was not harmless. While diagnosing a blocked deployment, ADR-002 was
read as authority for deleting the Search service from the infrastructure — which would have
broken every knowledge-base-backed agent at startup, in a way no Bicep validation would have
caught.

The root cause is vocabulary: this repository has used "Foundry IQ" for two different
retrieval mechanisms with opposite infrastructure requirements.

## Decision

**Azure AI Search is a hard deployment dependency of this solution and must be provisioned.**

Foundry IQ Knowledge Bases are MCP endpoints served *by* an Azure AI Search service. Removing
Search removes agentic retrieval.

Two supporting constraints follow from Microsoft's documentation and are recorded here so they
are not rediscovered the hard way:

- The service must be **Basic tier or higher**. Microsoft requires this when a managed
  identity is used for role-based access to deployed models, which is the only auth mode this
  deployment uses. The Free tier cannot serve this architecture.
- The region must offer **agentic retrieval**, which is a narrower list than Azure AI Search
  availability generally.

`CONTEXT.md` now distinguishes the two "Foundry IQ" mechanisms by name. Use those terms.

## Consequences

- **Positive:** The deployment topology now matches the code. The dependency is explicit, so
  region and tier constraints on Search are correctly treated as constraints on the whole
  solution — which is what surfaced the East US 2 capacity problem recorded in ADR-008.
- **Negative:** Search is a billed resource for the life of the demo, and its regional
  capacity is a live deployment risk. ADR-008 addresses that.
- **Reversible only by migrating retrieval:** Moving to `FileSearchTool` over managed vector
  stores — the architecture ADR-002 actually described — would genuinely remove the
  dependency. That remains a legitimate future option, but it is a code change to
  `agent_factory.py` and the content packs, not a template change.

## References

- [ADR-002: Foundry IQ (FileSearchTool + Vector Stores) Over Azure AI Search](./002-foundry-iq-file-search-over-azure-ai-search.md) (superseded by this ADR)
- [ADR-008: Azure AI Search Deploys to a Region Decoupled From the Foundry Primary Location](./008-decouple-search-region-from-foundry-location.md)
- [Connect Foundry IQ knowledge bases to a Foundry project](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/foundry-iq-connect)
- [Create a knowledge base for agentic retrieval](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-knowledge-base)
