# ADR-020: Deploy `main` on every commit, and make the deploy prove its own result

## Status

Accepted

## Date

2026-08-14

## Issue

#1 (spec #1), following [ADR-018](./018-deployed-build-provenance-check.md)

## Context

[ADR-018](./018-deployed-build-provenance-check.md) considered deploying automatically from `main`
and **rejected** it, in these words:

> Rejected for this build: `azure-dev.yml` is `workflow_dispatch` on purpose, the deploy path
> involves a manual `az acr build` ordering that commit `6a7199a5` established for good reasons,
> and `post_deploy.sh` re-seeds content packs — an automatic deploy would re-seed the six stock
> packs #25 suppressed unless `MACAE_USE_CASE=none` is pinned. Automating a path with that many
> live edges, the day before a demonstration, is the wrong order of operations. Worth revisiting
> afterwards.

Every clause of that is still true. What has changed is that the objections are now *enumerated*,
and an enumerated objection is a thing a workflow can encode. ADR-018 rejected automating a path
nobody had written down; `docs/preflight/deployed-surface.md` has since written it down, step by
step, with the three load-bearing details named and argued.

The cost of the rejection is also now known, and it is not small. The failure that produced
ADR-018 was a deployment **42 commits behind `main`** while all thirteen preflight checks were
green. ADR-018's own first-listed alternative was *"rely on discipline — always redeploy after
merging"*, rejected because "the failure mode is silent, so discipline has nothing to fail
against". But rejecting auto-deploy left discipline as the mechanism anyway: the provenance check
(#48) makes drift *loud*, and something still has to *close* it. A check that reports drift on the
morning of a demonstration has converted a silent failure into a legible one, which is progress and
is not a deployment.

There is one further thing the manual path was quietly load-bearing for, and it is worse than the
drift. The environment's provisioning inputs — the model roster, the capacities, the regions, the
registry hostname and the three image names — existed in exactly one place: `.azure/macae-flw-v1/`,
which is **gitignored, on one laptop**. `infra/main.parameters.json` reads twenty-four values from
the azd environment, and three of them (`AZURE_ENV_BACKEND_IMAGE_NAME` and its two siblings) default
to `azuredocs/containerapps-helloworld` — the Placeholder image whose ingress port stalls the whole
`mcp -> backend -> frontend` chain. The inputs of the environment a demonstration runs on were
one disk failure from unrecoverable, and nothing in the repository would have reported it.

## Decision

**Deploy `main` to `macae-flw-v1` on every commit that can change what is deployed, reproducing the
recorded sequence exactly, and refuse to call the deploy finished until the running surface has been
observed.**

`.github/workflows/deploy-main.yml` performs the sequence
[deployed-surface.md](../preflight/deployed-surface.md#the-order-that-shipped-it) records:
`az acr build` fills the registry first, `azd provision` puts all three Container Apps on images
tagged with the commit, then `post_deploy.sh` runs with `MACAE_USE_CASE=none`. It then runs
`check-deployed-surface.sh` and `check-deployed-environment.sh` as gates, because `azd` exiting zero
is not the same as the demonstration working — that gap is the whole of ADR-018.

Three supporting decisions make it possible:

- **The environment's inputs move into the repository**, as `infra/environments/macae-flw-v1.env`.
  A runner starts with an empty azd environment, so this was forced; that it also rescues the
  inputs from a gitignored directory on one laptop is the larger benefit.
- **The Direct Line token endpoint is a repository secret**, not a checked-in value and not a
  re-read. See *Considered Options*.
- **`post_deploy.sh` learns to resolve a principal id without a signed-in user.** `az ad
  signed-in-user show` is a Graph `/me` call and fails outright under a service principal, so the
  script reached `fatal` before it seeded anything. It now falls back to the service principal's own
  object id.

`azure-dev.yml` is **not** touched. It provisions a fresh timestamped environment to prove the
template deploys — inherited baseline ([ADR-006](./006-macae-is-a-one-way-baseline.md)) — and
wiring it to `push` would create a new environment, and a new bill, on every commit.

## Considered Options

- **Keep the manual deploy and rely on #48 to report drift.** Rejected, above: it makes the failure
  legible without making it go away, and ADR-018 had already rejected discipline as a mechanism.
- **Re-read the Direct Line token endpoint from Dataverse, as the manual sequence does.** Rejected
  because it is **impossible**, not because it is undesirable — and the impossibility was measured,
  not assumed. `PvaGetDirectLineEndpoint` fails for a service principal with
  `{"code":4029,"message":"Error while fetching user license using Graph API."}`. The deploy
  identity was registered as a Dataverse application user and given, in turn, `Microsoft Copilot
  User`, `System Customizer` and finally `System Administrator`: the bot row became readable at
  `System Customizer`, and the bound action failed identically at all three. It is a licence check,
  and an application user has no licence to find. The application user and its roles were then
  removed, because an identity that cannot use an access should not hold it. The endpoint is a
  repository secret instead, and the workflow **refuses to deploy** when it is absent rather than
  deploying an environment whose centrepiece beat cannot work.
- **Hold the deploy for approval on a GitHub Environment.** Not chosen now; the deploy is
  unattended. Note that this is not a one-line change: the federated credential's subject is
  `repo:<owner>/<repo>:ref:refs/heads/main`, and declaring an environment changes the OIDC subject
  to `...:environment:<name>`, so a second federated credential is required. A test asserts the job
  declares no environment, so the two cannot drift apart silently.
- **Deploy on every push regardless of path.** Rejected. A documentation commit would spend twenty
  minutes and a full ARM deployment. The filter names what is inside an image's build context, what
  provisioning reads, and what `post_deploy.sh` seeds — the last of which matters because a corpus
  or content-pack edit changes the deployed demonstration without changing a line of application
  code.

## Consequences

- **Positive:** The class of failure that produced ADR-018 cannot recur silently. Merging is
  deploying, and a deploy that does not end with the surface answering a real procedure question is
  a red build.
- **Positive:** The environment's provisioning inputs are in version control, reviewable, and no
  longer one laptop away from lost. `test_deploy_workflow.py` asserts they stay complete, so a new
  parameter cannot be added without either a default or a value.
- **Positive:** The three load-bearing details of the deploy order — registry first, commit-shaped
  tag, `MACAE_USE_CASE=none` — are now asserted by a test that runs without a tenant, rather than
  living only in a record somebody has to read.
- **Negative:** A commit to `main` now spends real money and real time, and can break the
  demonstration environment. `cancel-in-progress: false` means pushes queue rather than race, but a
  bad commit is deployed before anyone reads it. The mitigation is that the gates fail loudly, not
  that the deploy is prevented.
- **Negative:** The deploy identity holds `Contributor` and `User Access Administrator` on
  `rg-macae-flw-v1`. `User Access Administrator` is not gratuitous — `post_deploy.sh` grants the
  Foundry User role needed for the knowledge-base MCP connection — but it is the broadest right
  here and it is worth revisiting if that grant ever moves into Bicep.
- **Negative:** The federated credential's subject is not the shape every guide documents. GitHub
  presents `repo:<owner>@<owner_id>/<repo>@<repo_id>:ref:refs/heads/main`, and a credential built to
  the documented `repo:<owner>/<repo>:...` form is rejected with `AADSTS700213` at the first real
  push and at no point earlier. A rename or transfer of the repository changes the ids and breaks
  authentication. [docs/deploy-from-main.md](../deploy-from-main.md) records the presented subject
  and how to re-read it.
- **Negative:** The Direct Line token endpoint is now remembered in a secret rather than re-read,
  which is a step down from the manual sequence. If the environment ever moves region the secret
  goes stale, and the failure would be an unreachable SOP agent. `check-deployed-surface.sh` runs as
  a gate on every deploy and asks a real procedure question, so the staleness would be caught by the
  very next push rather than by a rehearsal.

## References

- [ADR-018: Check that the deployed build is the build we think it is](./018-deployed-build-provenance-check.md)
- [ADR-006: MACAE is a one-way baseline](./006-macae-is-a-one-way-baseline.md)
- [ADR-011: Reach the Copilot Studio SOP agent over Direct Line, not A2A](./011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md)
- [docs/preflight/deployed-surface.md](../preflight/deployed-surface.md)
- [docs/deploy-from-main.md](../deploy-from-main.md)
