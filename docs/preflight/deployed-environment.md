# Preflight: the deployed environment matches the vanilla flavour

**Verdict: `macae-flw-v1` is fully provisioned, every application host runs its own image, and an
agent resolves a knowledge base across the region boundary.** Observed 2026-08-12 (issue #12) and
extended 2026-08-13 (issue #30), in `rg-macae-flw-v1`, subscription
`3523b0e6-bb53-4e87-8340-25c416e26093`, primary region `eastus2`, **vanilla** (non-WAF) flavour.

Re-check with `scripts/preflight/check-deployed-environment.sh` — it exits non-zero the moment any
of the facts below stops being true. Unlike the tenant preflights, this one guards a *subscription*
assumption that every downstream ticket leans on: #13 and #14 need the embedding deployment to
answer, #20 needs Cosmos reachable without a key, #15's Workflow cache is only deterministic
because there is exactly one replica, and #19's store assistant is grounded in nothing at all
unless the knowledge bases resolve.

## What the check proves, and why each fact needed proving

| Check | Why it is not assumable |
| --- | --- |
| `primary-location` | The accelerator enforces **two** region allowlists whose intersection is four regions, and `eastus2` is the only one carrying the whole model roster ([ADR-009](../ADR/009-eastus2-as-the-only-viable-primary-region.md)). |
| `model-roster` | The accelerator ships **no embedding model at all** — its search is keyword plus semantic reranking with no vectors — so `text-embedding-3-small` is ours, and the Identity boundary gate's similarity tier has nothing to score against without it. The check also requires `Succeeded`, not merely present: a deployment row appears well before the model answers a request. |
| `search-service` | Azure AI Search has its own region ([ADR-008](../ADR/008-decouple-search-region-from-foundry-location.md)) because East US 2 could not allocate it. A Search service that came back in `eastus2` means the decoupling was lost, not that capacity appeared. Region names are compared folded, because ARM answers `Central US` here and `centralus` elsewhere. The **tier** is checked too: the free tier carries no semantic reranking and a hard index cap. |
| `application-hosts` | Kept separate from the image check because they fail differently. An app can carry the right image and the right scale and still have **no revision** — the state the MCP app sat in for nine days — and an app that was never created cannot fail any per-app check at all, so it has to be missed by name. |
| `single-replica` | Orchestrations are held in a **process-local dictionary** and checkpoint storage is in-memory, so a second replica is non-deterministic behaviour mid-demo. **It is now load-bearing for correctness, not only determinism**: [ADR-047](../ADR/047-a-turn-nobody-is-running-is-settled-at-startup.md) has a starting process settle the turns it inherited, which is honest reporting only while one process is all there is. A second replica may be mid-turn on a Chat this one knows nothing about, and settling it would stamp a terminal status onto a live answer's record. If this check ever goes red, the **Startup reconciliation** must be turned off before the app is scaled, not merely re-measured. |
| `keyless` | The accelerator already disables local auth on Cognitive Services, Cosmos and Search, and the registry admin user, so the MCAPS local-auth policies are a no-op and the standard tag exemption would be a pure security downgrade ([ADR-010](../ADR/010-keyless-by-default-over-mcaps-tag-exemption.md)). Reported as **one** check because the claim is a single one — nothing authenticates with a key — and a per-resource split would let a partial pass read as progress. |
| `application-images` | Every Container App boots on the Placeholder image. An app still serving it is a workload that never deployed. |
| `own-foundry-project` | The reuse-an-existing-Foundry-project path's deployer role grants are commented out upstream, so a deployment that took it is silently short of role assignments. |
| `foundry-tags` | The AI Foundry project module deployed completely untagged upstream. |
| `knowledge-bases` | `search-service` proves the service is in the right region on the right tier and keyless. It does not prove anything is *on* it — and for the first day of this environment's life, **nothing was**. See below. |
| `knowledge-base-connections` | The knowledge base can be perfect and the agent still unable to reach it: the per-KB `RemoteTool` connection is the only thing that gives the agent an identity to present at the MCP endpoint. It needs its own check for a second reason — the ARM call that creates these connections **reports failure and succeeds**, so the seeding script's exit code is not evidence either way. See below. |
| `model-reachability` | `Succeeded` is a **control-plane** fact. Whether the deployment answers a request is a different one, and it is the one #13 and #14 actually need. One real request goes to each deployment — chat or embeddings, chosen by name — and the roster is probed **by default**. `--no-probe` does not quietly omit the check: it reports the roster as unproven and exits non-zero, because a run that asked nothing must not claim feature work is ready. |
| `knowledge-base-retrieval` | The same argument, one layer up, and the only check that exercises ADR-008's split-region topology end to end. A knowledge base that *exists* is a control-plane fact; whether an agent in `eastus2` resolves it against a Search service in `centralus` is the fact the topology actually claims. Probed by default, and unprobed is reported as unproven. |

Observed 2026-08-13, all thirteen green, with `text-embedding-3-small` returning 1536 dimensions and
both store knowledge bases returning grounded, cited documents.

The consequence line the check prints — `feature work (#13, #14, #19, #20)` — names the tickets
whose **preconditions** these checks prove, not tickets this check finishes. #19 is on that list
because its store assistant is grounded in the two knowledge bases above and had nothing to retrieve
until they were seeded; whether its orchestration answers end to end through the deployed surface is
a different fact, and is **not** verified here. See *Scope*.

## Ten checks passed against an empty Search service

This is the finding that justifies the three checks #30 added, and it is uncomfortable: on
2026-08-12 every check in this record was green, and the Search service held **zero indexes, zero
knowledge sources and zero knowledge bases**. Nothing was wrong with the service. Nothing had ever
been put on it.

That state is invisible from the control plane. `search-service` asks where the service is, what
tier it is on and whether local auth is off — all true of an empty service. Foundry IQ knowledge
bases are an ADR-007 *hard dependency*, so an agent with `use_knowledge_base: true` starts happily,
retrieves nothing, and answers from the model without saying so. The demonstration's whole claim is
that an answer's provenance is visible; a silent fallback to model knowledge is the one failure it
cannot afford.

So the chain is walked rather than sampled — knowledge base → knowledge source → index →
**documents** — because every link breaks quietly:

- `PUT /knowledgebases/{kb}` accepts an empty `knowledgeSources` list.
- A knowledge source names its index by string, so it survives that index not existing.
- An index that exists holds nothing until `index_datasets.py` has run against it.

An empty index is therefore a **failed** check here, not a warning.

### The seeding order that fills it

The store assistant's two knowledge bases are seeded on every deployment whichever stock content
pack was chosen, so they are what the check expects by default (`--knowledge-base` overrides it).
`post_deploy.sh` does this as part of a much larger run; the four steps on their own are:

```bash
az storage container create --account-name stmacaeflwv1flrpd --name store-troubleshooting-dataset --auth-mode login
az storage blob upload-batch --account-name stmacaeflwv1flrpd --destination store-troubleshooting-dataset \
  --source content_packs/store_assistant/datasets/troubleshooting --auth-mode login --pattern '*.md' --overwrite

python infra/scripts/post-provision/index_datasets.py \
  stmacaeflwv1flrpd store-troubleshooting-dataset srch-macaeflwv1flrpd store-troubleshooting-index

AZURE_AI_SEARCH_ENDPOINT=https://srch-macaeflwv1flrpd.search.windows.net \
AZURE_OPENAI_ENDPOINT=https://aif-macaeflwv1flrpd.openai.azure.com/ \
python infra/scripts/post-provision/seed_knowledge_bases.py --only store-troubleshooting-kb,store-operations-kb

AZURE_AI_SEARCH_ENDPOINT=https://srch-macaeflwv1flrpd.search.windows.net \
AZURE_AI_PROJECT_ENDPOINT=https://aif-macaeflwv1flrpd.services.ai.azure.com/api/projects/proj-macaeflwv1flrpd \
PYTHONPATH=infra/scripts/post-provision \
python infra/scripts/post-provision/seed_kb_connections.py --only store-troubleshooting-kb,store-operations-kb
```

The RBAC this needs was already in place and did not have to be granted: the project's managed
identity holds `Search Index Data Reader` and `Search Service Contributor` on the Search service,
and the **Search service's** own identity holds `Cognitive Services OpenAI User` on the Foundry
account, which is what lets the knowledge base call `gpt-5.4-mini` for reranking.

## The connection PUT reports failure and succeeds anyway

`seed_kb_connections.py` answered `Done — 0/2 connections provisioned.` and exited non-zero. Both
connections existed. ARM answers every `PUT` of a `RemoteTool` connection with

```
500 InternalServerError  code: ServiceError  componentName: account-rp
```

and writes the connection regardless. It is not a first-write race: a re-`PUT` of a connection that
demonstrably exists answers `500` identically, with `isSharedToAll` true or false. In
`post_deploy.sh` that lands as `has_errors=true` plus an instruction to re-run a script that will
"fail" the same way forever, over an environment that is completely healthy.

`_create_connection_via_arm` now resolves a non-success code by **reading the connection back** and
comparing its target, and prints `~ ARM answered 500; the connection is present and correct.` A
status code that is known to lie is not evidence, and neither is the script's exit code — which is
why `knowledge-base-connections` reads the connections from ARM rather than trusting that the
seeding step said it worked.

## The cross-region hop, proven with one agent run

`knowledge-base-retrieval` is the acceptance criterion of #30 and the only check that touches every
part of ADR-008's topology at once. One request does all of it: an agent runs in the Foundry project
in `eastus2`, holding an `mcp` tool whose `server_url` is a knowledge base on the Search service in
`centralus` and whose `project_connection_id` is the `ProjectManagedIdentity` connection above.
Nothing but the project's managed identity is presented anywhere, because Search local auth is off.

The probe deliberately does not grade the prose. A fluent answer is exactly what an ungrounded run
produces, so what is read off the run is the `mcp_call` output item — whether
`knowledge_base_retrieve` was called at all, whether it errored, and how many documents came back.
An agent that answered without calling the tool **fails** this check, even though its response is a
`completed` `200`.

Observed 2026-08-13, `store-troubleshooting-kb`, asked which brew-basket fault stops a cycle
starting:

```
mcp_call  knowledge_base_retrieve  error=None
  queries: ["RB-201 coffee brewer display lit cycle will not start brew basket", ...]
  output : Retrieved 1 documents. 【4:0†source】 RB-201 Coffee Brewer Not Brewing
message : "Check that the brew basket is seated all the way into its rails; if it sits a
           few millimetres proud, it holds the interlock open and the machine will not
           start. Remove the basket, refit it firmly, and try again.【4:0†source】"
```

That is RB-201's Branch B, quoted from the indexed document with a citation — knowledge that exists
in this deployment only because it was indexed into Central US, reached from East US 2. The split
region topology works.

The probe's question is **derived from the corpus that is there**, not hard-coded and not open-ended.
The first version asked openly — *name one document in this knowledge base and quote a line from
it* — and failed intermittently against a completely healthy deployment, because an open question
leaves the model to invent the search terms and an invented term (`"runbook document sample line"`)
sometimes matches nothing. A probe that fails when nothing is wrong is worse than no probe. So the
read that counts an index also returns one document **title** from it, and the question names that
title. That stays independent of which content pack is installed — `--knowledge-base` points the
check at another pack's knowledge bases without rewriting the question — while asking about
something that certainly exists.

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
an image from our own registry, that the Foundry project is ours, that it is tagged, that the store
assistant's knowledge bases resolve to populated indexes behind `ProjectManagedIdentity` connections,
and that an agent **retrieves grounded documents from them across the region boundary** (#30).
**Not** verified here: that the multi-agent orchestration answers end to end through the deployed
surface (#19), or anything in the Copilot Studio tenant (#2, #3, #5, #6, recorded separately).
Whether what the deployment *serves* is this demonstration — the page title, the Quick Tasks, the
SOP agent's token endpoint and one grounded procedure question — is the sibling record,
[deployed-surface.md](deployed-surface.md) (#44).
