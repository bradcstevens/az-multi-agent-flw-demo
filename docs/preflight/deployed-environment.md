# Preflight: the deployed environment matches the vanilla flavour

**Verdict: `macae-flw-v1` is fully provisioned and every application host runs its own image.**
Observed 2026-08-12 (issue #12), in `rg-macae-flw-v1`, subscription
`3523b0e6-bb53-4e87-8340-25c416e26093`, primary region `eastus2`, **vanilla** (non-WAF) flavour.

Re-check with `scripts/preflight/check-deployed-environment.sh` — it exits non-zero the moment any
of the facts below stops being true. Unlike the tenant preflights, this one guards a *subscription*
assumption that every downstream ticket leans on: #13 and #14 need the embedding deployment to
answer, #20 needs Cosmos reachable without a key, and #15's Workflow cache is only deterministic
because there is exactly one replica.

## What the check proves, and why each fact needed proving

| Check | Why it is not assumable |
| --- | --- |
| `primary-location` | The accelerator enforces **two** region allowlists whose intersection is four regions, and `eastus2` is the only one carrying the whole model roster ([ADR-009](../ADR/009-eastus2-as-the-only-viable-primary-region.md)). |
| `model-roster` | The accelerator ships **no embedding model at all** — its search is keyword plus semantic reranking with no vectors — so `text-embedding-3-small` is ours, and the Identity boundary gate's similarity tier has nothing to score against without it. The check also requires `Succeeded`, not merely present: a deployment row appears well before the model answers a request. |
| `search-service` | Azure AI Search has its own region ([ADR-008](../ADR/008-decouple-search-region-from-foundry-location.md)) because East US 2 could not allocate it. A Search service that came back in `eastus2` means the decoupling was lost, not that capacity appeared. Region names are compared folded, because ARM answers `Central US` here and `centralus` elsewhere. The **tier** is checked too: the free tier carries no semantic reranking and a hard index cap. |
| `application-hosts` | Kept separate from the image check because they fail differently. An app can carry the right image and the right scale and still have **no revision** — the state the MCP app sat in for nine days — and an app that was never created cannot fail any per-app check at all, so it has to be missed by name. |
| `single-replica` | Orchestrations are held in a **process-local dictionary** and checkpoint storage is in-memory, so a second replica is non-deterministic behaviour mid-demo. |
| `keyless` | The accelerator already disables local auth on Cognitive Services, Cosmos and Search, and the registry admin user, so the MCAPS local-auth policies are a no-op and the standard tag exemption would be a pure security downgrade ([ADR-010](../ADR/010-keyless-by-default-over-mcaps-tag-exemption.md)). Reported as **one** check because the claim is a single one — nothing authenticates with a key — and a per-resource split would let a partial pass read as progress. |
| `application-images` | Every Container App boots on the Placeholder image. An app still serving it is a workload that never deployed. |
| `own-foundry-project` | The reuse-an-existing-Foundry-project path's deployer role grants are commented out upstream, so a deployment that took it is silently short of role assignments. |
| `foundry-tags` | The AI Foundry project module deployed completely untagged upstream. |
| `model-reachability` | `Succeeded` is a **control-plane** fact. Whether the deployment answers a request is a different one, and it is the one #13 and #14 actually need. One real request goes to each deployment — chat or embeddings, chosen by name — and the roster is probed **by default**. `--no-probe` does not quietly omit the check: it reports the roster as unproven and exits non-zero, because a run that asked nothing must not claim feature work is ready. |

Observed 2026-08-12, all ten green, with `text-embedding-3-small` returning 1536 dimensions.

## The MCP Container App is the head of the chain, and the placeholder image cannot satisfy it

This is the finding worth carrying forward, because it is what left the environment stuck from
2026-08-03 to 2026-08-12 and it is **not** an RBAC-propagation flake.

The three Container Apps are declared with the ports their own images listen on — backend `8000`,
MCP `9000`, frontend `3000` — while `MCPContainerImageName` and its two siblings default to
`azuredocs/containerapps-helloworld`, which listens on `80`. Container Apps therefore never gets a
ready revision, and after twenty minutes the module fails:

```
ContainerAppOperationError: Failed to provision revision for container app
'ca-mcp-macaeflwv1flrpd'. Error details: Operation expired.
```

The app is left with `provisioningState: Failed` and `latestRevisionName: null` — **no revision at
all**, which is why there was nothing in `az containerapp revision list` to diagnose.

The failure is not contained to the MCP app. The backend's `MCP_SERVER_ENDPOINT` reads
`mcp_container_app.outputs.fqdn`, and the frontend reads the backend's, so ARM serialises the three
into `mcp → backend → frontend`. The head of that chain failing means the backend and frontend
Container Apps were **never attempted** — they did not fail, they did not exist. Retrying the
deployment reproduces it exactly, because ARM is declarative and the inputs had not changed.

### The fix: fill the registry first, then provision

The accelerator's documented order is provision, *then*
`infra/scripts/post-provision/build_and_push_images.sh`. That order cannot work here, because the
script updates Container Apps that provisioning never created. The order is inverted instead:

1. Build the three images straight into ACR with `az acr build` (a server-side build — no local
   Docker daemon, and it authenticates with the signed-in principal rather than the admin user the
   template keeps disabled):

   ```bash
   az acr build --registry crmacaeflwv1flrpd --image macaemcp:latest      --file src/mcp_server/Dockerfile src/mcp_server
   az acr build --registry crmacaeflwv1flrpd --image macaebackend:latest  --file src/backend/Dockerfile   src/backend
   az acr build --registry crmacaeflwv1flrpd --image macaefrontend:latest --file src/App/Dockerfile       src/App
   ```

2. Point the environment at them and provision. The three image *names* were bicep parameters that
   `infra/main.parameters.json` never bound to anything, so `azd` could set the registry hostname
   and the tag but not the repository — the placeholder was unreachable from the environment file.
   They are now bound, keeping the accelerator's defaults:

   ```bash
   azd env set AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT crmacaeflwv1flrpd.azurecr.io
   azd env set AZURE_ENV_BACKEND_IMAGE_NAME  macaebackend
   azd env set AZURE_ENV_FRONTEND_IMAGE_NAME macaefrontend
   azd env set AZURE_ENV_MCP_IMAGE_NAME      macaemcp
   azd provision
   ```

## RBAC propagation was not the cause

The first-pull failure the issue anticipated did not occur, and it is worth recording the negative
so a future run does not spend twenty minutes waiting for it. `AcrPull` was already held by
`id-macaeflwv1flrpd` on `crmacaeflwv1flrpd` before any Container App was attempted — the
`module.role-assignments` module reached `Succeeded` while `module.mcp-container-app` was still
running — and every image pull after the registry was filled succeeded on the first pass.

## `SecurityControl=Ignore` comes from the subscription, not from the templates

Every resource in the group carries `SecurityControl=Ignore`, and the templates never ask for it.
It is applied by two subscription-scope policy assignments, *"Add SecurityControl=Ignore tag to
resources"* and *"…to resource groups"*. ADR-010's decision — do not take the MCAPS tag exemption —
is about what the templates request, so an appended tag is not a breach of it and the check
deliberately does not fail on its presence. What the check does assert is that the **common tag
set** (`azd-env-name`) reached the Foundry account, which is the tag the templates own.

## Scope

Verified: the primary region, the model roster and that every deployment **answers**, Search's region
and tier, that all three application hosts are provisioned with ingress on one replica, keyless
configuration across Foundry, Cosmos, Search, storage and the registry, that each Container App runs
an image from our own registry, that the Foundry project is ours, and that it is tagged. **Not**
verified here: that an agent answers end to end (#19), that a knowledge base resolves against Search
(#30), or anything in the Copilot Studio tenant (#2, #3, #5, #6, recorded separately).
