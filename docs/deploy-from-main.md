# Deploying `main`

**Merging to `main` deploys.** [ADR-020](./ADR/020-deploy-main-on-every-commit.md) is the decision;
`.github/workflows/deploy-main.yml` is the mechanism. This file is the operator's half: what the
workflow signs in as, what it is allowed to do, and what to do when it goes red.

## What runs, and when

A push to `main` that touches an image's build context (`src/backend`, `src/mcp_server`,
`src/App`), what provisioning reads (`infra/**`, `azure.yaml`), or what `post_deploy.sh` seeds
(`content/sop/**`, `content_packs/**`, `tools/store_pack/**`) deploys `macae-flw-v1`. A
documentation-only commit does not.

The sequence is the one [deployed-surface.md](./preflight/deployed-surface.md#the-order-that-shipped-it)
records, in the same order and for the same reasons:

1. **Fill the registry.** `az acr build` builds all three images server-side, tagged with the
   12-character commit sha *and* `latest`. Before provisioning, never after.
2. **Restore the azd environment.** A runner has none. Every input is applied from
   `infra/environments/macae-flw-v1.env`, plus the commit-shaped `AZURE_ENV_IMAGE_TAG`, the
   `COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT` secret, and `MACAE_USE_CASE=none`.
3. **`azd provision`.** The commit-shaped tag changes all three container templates, so all three
   revisions roll.
4. **`post_deploy.sh`.** The store assistant's pack and its two knowledge bases. No stock pack.
5. **Two gates.** `check-deployed-surface.sh` asks the deployment a real procedure question;
   `check-deployed-environment.sh --no-probe` re-reads the infrastructure. `azd` exiting zero is
   not the demonstration working — that gap is the whole of ADR-018.

Pushes queue rather than race (`cancel-in-progress: false`): abandoning an `azd provision` midway
through an ARM deployment leaves the environment in a state no commit describes.

## The identity it signs in as

| | |
| --- | --- |
| App registration | `gha-macae-flw-v1-deploy` |
| Client id | `7fdce93d-379a-4fe3-a7c8-eed4d41a03f3` |
| Object id (service principal) | `cccafdbe-b3d9-4517-8e0c-04e0c8c2e4c2` |
| Credential | Federated (OIDC) — **no client secret exists** |
| Subject | `repo:bradcstevens/az-multi-agent-flw-demo:ref:refs/heads/main` |

The subject is why the job declares no GitHub Environment: declaring one changes the OIDC subject
to `...:environment:<name>` and the token exchange stops matching. Adding an approval gate means
adding a second federated credential as well as the `environment:` line.
`test_deploy_workflow.py` asserts the job has none, so the two cannot drift apart silently.

### What it is allowed to do

| Role | Scope | Why |
| --- | --- | --- |
| Contributor | `rg-macae-flw-v1` | `azd provision` |
| User Access Administrator | `rg-macae-flw-v1` | `post_deploy.sh` grants the Foundry User role for the KB MCP connection |
| AcrPush | `crmacaeflwv1flrpd` | `az acr build` |
| Storage Blob Data Contributor | `stmacaeflwv1flrpd` | content-pack blobs |
| Search Index Data Contributor | `srch-macaeflwv1flrpd` | index creation and upload |
| Search Service Contributor | `srch-macaeflwv1flrpd` | index creation |
| Cognitive Services OpenAI User | `aif-macaeflwv1flrpd` | embeddings during indexing |
| Foundry User | `aif-macaeflwv1flrpd` | knowledge-base MCP connection |

Nothing is granted at subscription scope, and the identity holds **no Dataverse access at all** —
see below.

### Repository secrets

| Secret | Note |
| --- | --- |
| `AZURE_CLIENT_ID` | |
| `AZURE_TENANT_ID` | |
| `AZURE_SUBSCRIPTION_ID` | |
| `COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT` | The one real secret. Absent, the workflow refuses to deploy. |

## Why the token endpoint is remembered rather than re-read

The manual sequence re-reads the Direct Line token endpoint from the live Copilot Studio agent, and
[deployed-surface.md](./preflight/deployed-surface.md) calls that load-bearing: "the endpoint is
re-read, not remembered". The workflow cannot do it, and the limit was measured rather than assumed.

`PvaGetDirectLineEndpoint` fails for a service principal:

```
400: {"code":4029,"message":"Error while fetching user license using Graph API."}
```

The deploy identity was registered as a Dataverse application user and given, in turn, `Microsoft
Copilot User`, `System Customizer`, and finally `System Administrator`. The `bot` row became
readable at `System Customizer`; the bound action failed identically at all three. It is a licence
check, and an application user has no licence to find. The application user and its roles were then
**removed** — an identity that cannot use an access should not hold it.

So the endpoint is a repository secret. Two things keep that honest: the workflow refuses to deploy
when it is empty, and `check-deployed-surface.sh` runs as a gate on every deploy and asks a real
procedure question, so a stale endpoint fails the very next push rather than a rehearsal.

If the environment is ever recreated or moves region, re-read it by hand and update the secret:

```bash
python3 -c "import sys; sys.path.insert(0, 'scripts')
from copilot_studio import sop_agent as s
env = s.resolve_environment(None); bot = s.read_bot(env)
print(env.call(f\"bots({bot['botid']})/Microsoft.Dynamics.CRM.PvaGetDirectLineEndpoint\", 'POST', {})['Endpoint'])"

gh secret set COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT --body '<what that printed>'
```

## When it goes red

Read which step failed before doing anything else — they fail for very different reasons.

| Step | What it means |
| --- | --- |
| **Log in to Azure / azd** | The federated credential no longer matches. Check the subject is still `ref:refs/heads/main`, and that nobody added `environment:` to the job. |
| **Fill the registry** | A Dockerfile or a build. Nothing has been deployed yet; the running environment is untouched. |
| **Restore the azd environment** | Usually the token endpoint secret is missing. Nothing has been deployed yet. |
| **Provision** | ARM. The environment is now *partly* changed — read the deployment in the portal before re-running. |
| **Seed the store assistant** | Cosmos, Storage or Search. The Container Apps are on the new build; the data behind them may not be. |
| **Prove the deployed surface** | The build deployed and the demonstration does not work. This is the gate doing its job: read its report, it names which of the four facts failed. |
| **Prove the deployed environment** | Infrastructure drifted from its record — a region, the model roster, a replica count, an image not from our registry. |

Re-running a failed run is safe: every step is idempotent, and ARM is declarative.

## Related

- [ADR-020](./ADR/020-deploy-main-on-every-commit.md) — the decision, and what was rejected.
- [ADR-018](./ADR/018-deployed-build-provenance-check.md) — why drift needed catching at all.
- [docs/preflight/deployed-surface.md](./preflight/deployed-surface.md) — the sequence this
  workflow automates, and what the gate proves.
- `src/tests/ci/test_deploy_workflow.py` — the invariants, asserted without a tenant.
