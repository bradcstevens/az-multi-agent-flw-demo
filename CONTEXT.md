# CONTEXT.md

Glossary and ubiquitous language for the **Circle K Frontline Store Assistant** — built on the
**MACAE baseline**, the Microsoft Multi-Agent Custom Automation Engine (MACAE) solution accelerator
taken at commit `c5a7a4d1f0bfb6930b4c7b7f6356f28e7e03c309` and diverged from (see
[ADR-004](docs/ADR/004-fork-macae-at-pinned-upstream-commit.md) and
[ADR-006](docs/ADR/006-macae-is-a-one-way-baseline.md)).

ADRs live in `docs/ADR/` — the directory upstream already uses, with its three-digit `NNN-`
numbering continued rather than the four-digit example in `docs/agents/domain.md`. The index is
[docs/ADR/README.md](docs/ADR/README.md); every ADR appears in it.

The reference material this build started from is superseded and untracked — see **Superseded
requirements document** below, and
[docs/superseded-requirements-corrections.md](docs/superseded-requirements-corrections.md) for the
ten things it gets wrong.

Use these terms in issue titles, commit messages, test names, and module names. Where a term has a
concrete home in the code, the file is named.

## Orchestration

**Workflow** — the Magentic workflow object built by
`OrchestrationManager.init_orchestration` (`src/backend/orchestration/orchestration_manager.py`). It
holds the participant agents and the manager chat client. Built per user and cached; it is *not* a
per-request object. At build time it is tagged with `_team_config` and `_manager_chat_client`, and
nothing else.

**Workflow cache** — `orchestration_config.orchestrations`, a process-local dictionary keyed by
**user identifier alone**. Because it is process-local and in-memory, the application must run as a
single replica.

**Team tag** — the notional `_team_id` attribute on a Workflow, read in two places to decide whether
the cached Workflow belongs to the currently selected team:
`orchestration_manager.get_current_or_new_orchestration` and `api/router.py`.
**It is never assigned.** See *Confirmed findings* below.

**Full workflow rebuild** — the `needs_full_rebuild` branch of
`get_current_or_new_orchestration`: closes every cached agent, then runs `AgentFactory.get_agents`
and `init_orchestration` from scratch. This is the expensive path and, today, the *only* path.

**Lightweight workflow reset** — the `needs_workflow_reset` branch: rebuilds only the workflow shell
and reuses the existing agent pool. Currently unreachable in production.

**Team configuration** — a `TeamConfiguration` (`src/backend/common/models/messages.py`): the set of
agents, their models, and their prompts. `team_id` is a required non-optional `str`.

**Plan review** — the approval gate the Magentic builder is configured with at Workflow build time.
Upstream hardcodes it as a literal; the two-lane design makes it a per-request value. See
[ADR-013](docs/ADR/013-per-request-plan-review-over-orchestrator-bypass.md).

## Request path

**Fast lane** — the request path taken by an SOP lookup, a troubleshooting turn or a task query:
the orchestration builder runs with **Plan review** off, so no plan is generated and nothing is
approved. Target sub-10s. It is *not* a bypass of the orchestrator — no single-agent invocation
path exists (ADR-013).
_Avoid_: bypass, direct agent call, single-agent path

**Deliberate lane** — the request path taken by escalation and ticket creation: the full
orchestration with **Plan review** on, where the approval step *is* the associate confirming the
ticket before it is raised.

**Lane** — which of the two a request takes. Declared as metadata on a **Quick Task**, with a
keyword fallback for free-typed input, and **surfaced in the UI as a feature**. Selection **fails
open to the Deliberate lane**.

**Identity boundary gate** — the deterministic code gate in the request path that refuses
personal, individual-identity questions from a shared store device, executed **before the lane
router and before orchestration**. Keyword fast path plus an embedding-similarity tier; **fails
closed**; on a match the request short-circuits with no agent invoked and no tokens spent. It is
not the accelerator's prompt-based team-scope evaluation, which fails open in two places. See
[ADR-014](docs/ADR/014-deterministic-identity-boundary-gate.md).
_Avoid_: guardrail prompt, scope prompt, content filter

**Policy block** — a refusal by the Identity boundary gate. Rendered distinctly from a
**retrieval miss** — an honest "that procedure is not in the library" — because conflating the two
makes a governed refusal look like a bug.

**Mocked unlock** — the post-"sign-in" state in which the Identity boundary gate admits the
previously refused question and answers it from mocked data. A parameter of the gate, not a
second gate. No real identity provider is involved.

## Retrieval

**Foundry IQ** — ambiguous on its own. This repository has used the name for two different
mechanisms with **opposite infrastructure requirements**, and conflating them once nearly caused a
required resource to be deleted. Always qualify it with one of the two terms below.
_Avoid_: bare "Foundry IQ", "the search path", "RAG"

**Foundry IQ vector store** — retrieval via `FileSearchTool` over vector stores managed by the
Foundry project. Files are uploaded and chunked by the service; there is no index schema and **no
Azure AI Search resource**. This is the architecture [ADR-002](docs/ADR/002-foundry-iq-file-search-over-azure-ai-search.md)
described. It is a legitimate future option but is **not** what the code does today.

**Foundry IQ Knowledge Base** — retrieval via a knowledge base that is an **MCP endpoint served by
an Azure AI Search service**. This *is* what the code does: `KnowledgeBaseConfig`
(`src/backend/config/mcp_config.py`) requires `AZURE_AI_SEARCH_ENDPOINT` and fails construction
without it, and reaches the knowledge base through a per-KB `RemoteTool` /
`ProjectManagedIdentity` project connection named `{kb_name}-mcp`. Selected per agent by
`use_knowledge_base` + `knowledge_base_name` in a team configuration. **Azure AI Search is therefore
a hard deployment dependency** — see [ADR-007](docs/ADR/007-foundry-iq-knowledge-bases-require-azure-ai-search.md).

**SOP corpus** — the store-procedure knowledge owned by the Copilot Studio agent and grounded in
**Dataverse documents**, reached over Direct Line. It is deliberately *not* held in Azure AI Search,
and no local copy is kept as a fallback. Distinct from, and never merged with, any Foundry-side
knowledge base — the demo's whole claim rests on the two provenances being visibly separate.
Grounding **Option A only**; the SharePoint-via-service-account option is deleted, not deferred —
see [ADR-012](docs/ADR/012-grounding-option-a-dataverse-documents-only.md).
_Avoid_: SharePoint SOP library, the SharePoint source

**Copilot Studio SOP agent** — the single low-code agent and the entire cross-platform proof.
Published to **Direct Line** and reached from the orchestrator through an MCP tool like any other
tool. See [ADR-011](docs/ADR/011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md).

**Direct Line** — the GA transport between the orchestrator and the Copilot Studio SOP agent.
Tokens live **3600 seconds**. Chosen over A2A on fit, **not** on availability — A2A reached GA in
April 2026, and repeating the "A2A is Preview" line is repeating a known error (ADR-011).

## Surfaces

**Grounding panel** — the R6 surface showing where an answer came from. Driven by **two signals
combined**: a "source used" event emitted server-side over the existing WebSocket, which proves
*which platform* answered, and citation data parsed from the SOP agent's response, which supplies
the document detail. Neither alone satisfies the requirement.

**Token meter** — the R7 per-agent call and token counter. Net-new: the accelerator emits no token
telemetry. Its emission point is the executor-completed branch of the event stream.

**Presenter alert** — the R8 proactive shift-task message, triggered by a hidden backend route plus
a keyboard chord and pushed over the existing WebSocket. No wall-clock timer.

**Quick Task** — a starting task the presenter taps instead of typing. Six of them, including one
that deliberately routes to the **Deliberate lane** and one rehearsed out-of-corpus probe. Carries
**Lane** metadata, which the upstream starting-task model has no field for.

**Simulated ticket** — the R4 service ticket. Labelled as simulated in the UI, persisted to Cosmos,
and it **must carry the attempted steps** pulled from the troubleshooting record — if the associate
has to re-type what they tried, the requirement has failed.

**Attempted steps** — what the associate has already tried, persisted explicitly to the Cosmos
memory container. Framework checkpoint state is in-memory and must not be relied on for this.

## Licensing and capacity

**Pay-as-you-go billing plan** — a Power Platform *billing policy* (`PowerPlatformPayGo`, id
`d94c286b…`) that bills one or more environments' metered usage to an Azure subscription instead of
prepaid capacity. Read it with `GET https://api.powerplatform.com/licensing/billingPolicies`. The
Power Platform admin center calls it a "billing plan"; the API calls it a billing *policy*. Chosen
over licence-based publishing because a Microsoft 365 Copilot licence does not entitle publishing to
Direct Line — that zero-rating requires the agent to run under an authenticated Microsoft 365 Copilot
user's identity, and a no-auth Direct Line session has none.
_Avoid_: billing attachment, Azure subscription link

**Copilot Studio meter** — the `MCSMessages` entitlement (product category `PowerVirtualAgent`) on a
Pay-as-you-go billing plan. A plan can be active and attached to an Azure subscription without
carrying it, and carrying it is not the same as *covering an environment*: both the meter and the
environment link must hold before Copilot Studio bills pay-as-you-go. Recorded in
`docs/preflight/copilot-studio-payg-meter.md`; checked by
`scripts/preflight/check-copilot-studio-meter.sh`.
_Avoid_: message meter, Copilot Studio billing

**Dataverse System Administrator** — the Dataverse security role, held *inside* an environment, that
lets environment-level settings (notably Dataverse search, #3) be changed. Distinct from Power
Platform admin centre membership: a Global Administrator is not automatically granted it in the
Default environment, and Dataverse refuses to let an account assign it to itself (`prvAssignRole`).
Granted instead by a **Bootstrap application user**. Recorded in
`docs/preflight/dataverse-admin-role.md`; checked by
`scripts/preflight/check-dataverse-admin-role.sh`.
_Avoid_: environment admin, Power Platform admin (a different, tenant-level thing)

**Bootstrap application user** — a throwaway Entra app registration that the BAP admin API's
`addAppUser` registers as a Dataverse **application user**, which that endpoint grants System
Administrator outright. Because it *has* `prvAssignRole`, it can assign the role to the build
account; because it authenticates by client credentials, the whole sequence runs with no user, no
MFA and no browser. It is deleted afterwards, and its Dataverse user disabled — deleting the app
registration alone leaves an enabled System Administrator with no credential behind it. This is the
elevation route for #2, in place of Microsoft's documented `applyAdminRole`, which the Azure CLI
cannot reach at all.
_Avoid_: service principal admin, app user (ambiguous — Dataverse also calls ordinary users "users")

## Build and test

**Durable record** — the tracked documentation that outlives the **superseded requirements
document**: this glossary, [`docs/ADR/`](docs/ADR/README.md) and
[the corrections record](docs/superseded-requirements-corrections.md). Its invariants are enforced
by `src/tests/ci/test_durable_record.py` in the CI-tooling tests loop — every ADR reachable from the
index, ten numbered corrections each stating a wrong claim and the correct one, and every relative
documentation link resolving **case-sensitively** (the macOS filesystem hides case drift that the
Linux CI runner would surface).

**Superseded requirements document** —
`.reference/Circle-K-Frontline-Store-Assistant-Demo-Build-Requirements-v1.md`, the v2.1 reference
material this build started from. **Untracked** — `.reference/` is `.gitignore`d — so it is not the
record of anything and does not survive a fresh clone. Ten of its statements are factually wrong; a
reader who still has a copy should read it only alongside the corrections record.
_Avoid_: the requirements doc, the build requirements, the spec (the spec is issue #1)

**Correction** — one numbered entry in the corrections record, stating the superseded document's
**claim** and the **correct** position. The ten are a historical record and are append-only: a new
finding becomes correction 11, it does not rewrite an existing one.

**Guardrail corpus** — 10 positive and 10 negative probes that are simultaneously R5's acceptance
test and the tuning harness for the Identity boundary gate's similarity threshold. Runs against the
**real** embedding deployment under the `integration` marker and is deselected in CI, because a
mocked embedder would only prove plumbing. It must exist **before** the threshold is chosen.

**Deployment flavour** — which of the three infrastructure paths `infra/main.bicep` dispatches to:
`bicep` (**vanilla**, what this build deploys), `avm`, or `avm-waf`. Not cosmetic — several
decisions bind the vanilla module only. Search's own region ([ADR-008](docs/ADR/008-decouple-search-region-from-foundry-location.md),
[ADR-009](docs/ADR/009-eastus2-as-the-only-viable-primary-region.md)), the disabled storage
shared key ([ADR-010](docs/ADR/010-keyless-by-default-over-mcaps-tag-exemption.md)) and the
embedding deployment the Identity boundary gate needs
([ADR-014](docs/ADR/014-deterministic-identity-boundary-gate.md)) are all absent from the AVM
paths. **Switching flavours is not a like-for-like swap.**

**MACAE baseline** — the Microsoft accelerator as it stood at commit
`c5a7a4d1f0bfb6930b4c7b7f6356f28e7e03c309`, merged into this repository once and never re-synced. It
is a frozen starting point, not a sibling kept in step: there is no `upstream` remote, no
cherry-pick path and no contribution back, so fixes to accelerator code are made here as our own
commits. (A one-off upstream fix can be fetched by URL without persisting a remote — see
[ADR-006](docs/ADR/006-macae-is-a-one-way-baseline.md), which also explains why a remote pointing at
a SAML-enforced organisation breaks every `gh` command in this clone.)
_Avoid_: fork, upstream fork, pinned upstream commit

**Two-phase test invocation** — `src/tests/backend/test_app.py` runs first in its own pytest
process, then the rest of `src/tests/backend` runs with `--cov-append` and `--ignore` on that file.
Required because the suite mutates `sys.modules` and the environment at import time. Preserve it.
Encoded in `scripts/backend-tests.sh`.

**Feedback loop** — a `(name, command)` row of the `## Feedback loops` table in `AGENTS.md`. Four
today: **Backend lint** (`scripts/backend-lint.sh`), **Backend tests** (`scripts/backend-tests.sh`),
**MCP server tests** (`scripts/mcp-tests.sh`) and **CI-tooling tests** (`scripts/ci-tests.sh`, which
covers the repo's own tooling — the Advisory coverage report and the `scripts/preflight/` checks). The
table is the single source of truth: agents run these before committing and the runner re-runs them
after each merge as the integration gate, so a missing or unrunnable table makes every merge red.
See [ADR-005](docs/ADR/005-declare-feedback-loops-in-agents-md.md).

**Advisory coverage report** — `scripts/coverage_report.py`, the one implementation of the 80%
line-coverage threshold, called by both the Backend tests loop and `.github/workflows/test.yml`. It
prints the overall line rate and warns below the threshold but **always exits zero**; only a missing
or unreadable `coverage.xml` is an error, because that means the test run produced no number at all.
It is deliberately not a gate: this build adds substantial demo scaffolding to the two largest
backend files and the coverage configuration counts test files toward the total, so a blocking gate
would buy noise rather than confidence on a demo with this lifespan.
_Avoid_: coverage gate, coverage threshold gate

**Data policy** — the Power Platform tenant policy that classifies connectors into Business,
Non-business or Blocked. Formerly, and still colloquially, "DLP". Three Copilot Studio connectors
have to stay unblocked for this demo — `Direct Line channels in Copilot Studio`,
`Chat without Microsoft Entra ID authentication in Copilot Studio` and
`Knowledge source with documents in Copilot Studio` — and there has been no exemption route since
early 2025, so a block is fatal rather than negotiable. Verified in
[docs/preflight/copilot-studio-data-policy-and-egress.md](docs/preflight/copilot-studio-data-policy-and-egress.md).
_Avoid_: DLP policy, connector policy

**Preflight record** — a `docs/preflight/*.md` file recording a precondition that was verified
before the build, each backed by a re-runnable check in `scripts/preflight/`. Distinct from a
Feedback loop: a loop guards a change, a preflight guards an assumption about the tenant or
subscription, and its verdict is point-in-time. Read the record rather than re-deriving it, and
re-run the check rather than trusting the date on it. Four today: three about the Copilot Studio
tenant (#2, #5, #6) and one about the **deployed environment** (#12) — the model roster, Search's
region, single-replica scale, keyless configuration and the application images in
[docs/preflight/deployed-environment.md](docs/preflight/deployed-environment.md).

**Placeholder image** — `mcr.microsoft.com/azuredocs/containerapps-helloworld`, the image all three
Container Apps are declared with until real ones exist. It listens on `80` while the apps declare
the ports their own images use (backend `8000`, MCP `9000`, frontend `3000`), so Container Apps
never gets a ready revision and the module fails after twenty minutes with `Operation expired` and
**no revision at all** to diagnose. Not a flake and not an RBAC-propagation first-pull failure — the
accelerator's documented "provision, then `build_and_push_images.sh`" order simply cannot work,
because the script updates Container Apps that provisioning never created. The registry is filled
first with `az acr build`, then `azd provision` creates the apps on real images. See
_The MCP Container App is the head of the chain_ in the deployed-environment preflight record.
_Avoid_: bootstrap failure, ACR propagation failure

**Runner state** — `.git-loopy/` at the repo root holds the runner's event log, run summaries and
diagnostics. The runner appends `.git-loopy/` to `.gitignore` itself when the entry is missing, and
never commits that edit — which dirties the base worktree and makes the integration publish
(`git merge --no-ff`) refuse to overwrite `.gitignore`. The entry is therefore **tracked** in
`.gitignore`, which keeps the runner's append a permanent no-op. Do not remove it. Its diagnostic
log (`.git-loopy/logs/<iso>-<run_id>.log`) is the first place to look when the gate reports red —
it distinguishes "gate could not run" and "publish failed" from an actually-failing loop.

## Confirmed findings

### Tenant admin does not imply Dataverse System Administrator (confirmed 2026-08-12, issue #2)

The build account is a **Global Administrator** and still held only `Basic User` and
`Environment Maker` in the Default environment's Dataverse. Power Platform admins are no longer
automatically granted System Administrator there, so admin centre membership is not evidence — the
environment's own security-role list is, and it is a different API. Assigning the role to yourself
from the Dataverse side is refused outright (`0x80040220`, missing `prvAssignRole`).

Microsoft's documented route — the `applyAdminRole` self-elevation POST — is **unreachable from the
Azure CLI, and consent is not the obstacle**. It needs a user token carrying
`UserManagement.Users.Apply`, and consent between two Microsoft first-party applications is
configured by the API owner, not by a tenant admin: admin consent was granted as Global
Administrator and the token request still fails with `AADSTS65002`. (The `az` CLI reports a stale-MFA
error instead, which masks it; `azd`, sharing the same client id, surfaces the real one.) No
sign-in obtains that scope, so **an earlier reading of this finding — "one interactive consent
remains" — was wrong.**

The role is instead granted by a **Bootstrap application user**, which needs nothing beyond the
tenant-admin access the Azure CLI already has on the BAP admin API, and therefore runs unattended.
The build account now holds System Administrator, observed in the environment's security roles.

Consequence: **#3 (Dataverse search) is unblocked**, and with it the #3 → #17 → #18 chain. Verified
by revoking the role and letting `scripts/preflight/check-dataverse-admin-role.sh --elevate` grant it
back in 27 seconds; see `docs/preflight/dataverse-admin-role.md`.

### Pay-as-you-go works on a Default environment, and the meter now covers it (confirmed 2026-08-12, issue #6)

Microsoft documents pay-as-you-go for **production and sandbox** environments only, and this tenant
has exactly one environment — `Default-0f87abfb…`, `environmentSku: Default`. Linking it to the
Pay-as-you-go billing plan nevertheless returned **200**, so the undocumented case works and no
second environment is needed.

The plan already carried the Copilot Studio meter, but its only linked environment was
`39bc9cf5-323a-e466-a0b6-8797aaeadf1e`, which the admin API reports as `EnvironmentNotFound` — a
dangling reference to a deleted environment. A meter on a plan the Default environment is not linked
to bills nothing and raises no rate limit, so **"a plan carries the meter" is not sufficient**; the
environment link is a separate condition and is checked separately. The Default environment is now
linked and the dangling reference removed.

Consequence for the rehearsal: the generative-AI-message quota is **100 RPM / 2,000 RPH**. Before the
link, pay-as-you-go was not in effect and that quota did not apply; which one did is not recorded,
because prepaid message packs and Microsoft 365 Copilot entitlement each set their own and neither
was read. 100 RPM is the documented entitlement, not a measured ceiling — measuring it needs a
published Direct Line agent (#17).

### The Placeholder image, not RBAC propagation, is what stalls the first deploy (confirmed 2026-08-12, issue #12)

The environment had been half-provisioned since 2026-08-03 and re-running the deployment reproduced
the same failure exactly, because ARM is declarative and the inputs had not changed. The MCP
Container App is the **head of a serialised chain** — the backend's `MCP_SERVER_ENDPOINT` reads
`mcp_container_app.outputs.fqdn` and the frontend reads the backend's — so its twenty-minute
`Operation expired` meant the backend and frontend Container Apps were never *attempted*. They had
not failed; they did not exist.

The cause is the Placeholder image against a declared ingress port it does not listen on, **not**
the first-pull RBAC-propagation failure the issue anticipated. `AcrPull` was already held by
`id-macaeflwv1flrpd` before any Container App was tried, and every pull after the registry was
filled succeeded first time. Filling the registry with `az acr build` and *then* provisioning took
**3m06s** end to end, against 20m08s to fail. The three image *names* had to become bindable first:
they were bicep parameters `infra/main.parameters.json` never bound, so `azd` could set the registry
hostname and the tag but not the repository.

Also confirmed: `SecurityControl=Ignore` on every resource comes from two **subscription-scope
policy assignments**, not from the templates. ADR-010's decision is about what the templates
request, so the appended tag does not breach it.

### The Workflow is *not* tagged with a team identifier at build time (confirmed 2026-08-01, issue #9)

The comment at `orchestration_manager.py:236-238` claims "The team_id tag is set on every workflow we
build/reset below". **That claim is false.** A static scan of `src/backend` finds:

- **Assignments of `_team_id` on a Workflow: none.**
- Reads of `_team_id` on a Workflow: two —
  - `src/backend/orchestration/orchestration_manager.py:239` (`current_team_id`)
  - `src/backend/api/router.py:380` (`cached_team_id`)

`init_orchestration` assigns only `workflow._team_config` and `workflow._manager_chat_client`
(`orchestration_manager.py:206-207`). The only place `_team_id` is ever set on a workflow object in
the entire repository is `src/tests/backend/orchestration/test_orchestration_manager.py:441`, where
a test hand-sets it on a mock.

**Consequence — yes, every request currently performs a Full workflow rebuild.**
`getattr(current, "_team_id", None)` always returns `None`, while `team_config.team_id` is a
required non-empty `str`. So `team_changed` is `True` whenever a cached Workflow exists, and
`needs_full_rebuild = current is None or team_switched or team_changed` is therefore **always**
`True`. Two consequences follow:

1. Every call closes and recreates all agents. There is no warm path, so the latency baseline for
   the fast lane must be measured against a full agent-pool rebuild, not against a cache hit.
2. `needs_workflow_reset` (`not needs_full_rebuild and workflow_terminated`) can never be `True` —
   the Lightweight workflow reset branch is dead code in production.

The same defect appears independently at `router.py:380`, where `team_mismatch` is always `True`, so
`workflow_unusable` is always `True` on the request path too.

Confirmed empirically with a throwaway probe: replaying the existing reuse test
(`test_given_existing_workflow_when_no_switch_then_returns_it`) against a Workflow shaped as
production builds it — i.e. with `_team_config` set and `_team_id` absent — takes the rebuild branch
and calls `init_orchestration` exactly once, where the committed test (which hand-sets `_team_id`)
returns the cached Workflow untouched.

**Implication for the workflow-cache fix:** deleting line 441 of
`test_orchestration_manager.py` converts that passing test into a regression test for the fix. Do
that as part of the cache change, not before — it fails until `_team_id` is genuinely assigned at
build time.
