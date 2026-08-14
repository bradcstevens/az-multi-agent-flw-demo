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
per-request object. At build time it is tagged with `_team_config`, `_manager_chat_client`,
`_team_id` and `_plan_review`.

**Workflow cache** — `orchestration_config.orchestrations`, a process-local dictionary keyed by
**user identifier alone**. Because it is process-local and in-memory, the application must run as a
single replica.

**Team tag** — the `_team_id` attribute on a Workflow, read in two places to decide whether
the cached Workflow belongs to the currently selected team:
`orchestration_manager.get_current_or_new_orchestration` and `api/router.py`. Assigned at build
time since #15; before that it was never assigned, which made every request a Full workflow
rebuild. See *Confirmed findings* below.

**Plan review tag** — the `_plan_review` attribute on a Workflow, recording which **Lane** it was
built for. Read alongside the **Team tag** by the same two predicates, because a Workflow built for
one lane must not serve a request for the other.

**Full workflow rebuild** — the `needs_full_rebuild` branch of
`get_current_or_new_orchestration`: closes every cached agent, then runs `AgentFactory.get_agents`
and `init_orchestration` from scratch. Taken when no Workflow is cached, on an explicit team switch,
on a **Team tag** mismatch or on a **Plan review tag** mismatch — so a lane change costs a rebuild.

**Lightweight workflow reset** — the `needs_workflow_reset` branch: rebuilds only the workflow shell
and reuses the existing agent pool. Reachable in production since #15 assigned the **Team tag**;
before that it was dead code.

**Team configuration** — a `TeamConfiguration` (`src/backend/common/models/messages.py`): the set of
agents, their models, and their prompts. `team_id` is a required non-optional `str`.

**Plan review** — the approval gate the Magentic builder is configured with at Workflow build time.
Upstream hardcoded it as a literal; since #15 it is a per-request value, and since #16 it is not
declared by the client at all — the **Lane router** derives it from the request's **Lane**, and
`Lane.plan_review` is the one place "fast means no approval gate" is written down. See
[ADR-013](docs/ADR/013-per-request-plan-review-over-orchestrator-bypass.md).

## Request path

**Fast lane** — the request path taken by an SOP lookup, a troubleshooting turn or a task query:
the orchestration builder runs with **Plan review** off, so no plan is generated and nothing is
approved. Target sub-10s. It is *not* a bypass of the orchestrator — no single-agent invocation
path exists (ADR-013).
_Avoid_: bypass, direct agent call, single-agent path

**Deliberate lane** — the request path taken by escalation and ticket creation: the full
orchestration with **Plan review** on, where the approval step *is* the associate confirming the
ticket before it is raised. Not instructed — `_handle_plan_reviews`' **approved** branch submits the
draft and pushes the card, and the rejected branch does not (#22). The seam runs on every approved
plan, which is why `TicketStore.read` is **not** total: see **Simulated ticket**.

**Lane** — which of the two a request takes (`src/backend/lane/lane.py`). Declared as metadata on a
**Quick Task** and carried on the wire as `InputTask.lane` — the **only** lane declaration on a
request, because two ways to say the same thing on one message is how a request ends up in a lane
nobody chose. A Lane decides exactly one thing: **Plan review**. The lane *taken* comes back on the
`/process_request` response, is recorded into **Session state** so it survives a reload, and is
**surfaced in the UI as a feature** (`LaneBadge`) — on a Quick Task as the lane declared, on a plan
as the lane taken.

**Lane router** — `lane.router.select_lane`: declared Lane wins, no declaration falls back to the
**Lane keyword fallback**, and an **unparseable declaration goes straight to the Deliberate lane**
without consulting the keywords, because guessing from a request whose metadata is corrupt is how a
router failure becomes a policy failure on stage. Fail open covers an unreadable *lane*; a `lane`
that is not a string at all is a malformed request and the schema refuses it before the router is
reached, which routes nothing and so cannot lose the gate. Deliberately a **separate component from
the Identity boundary gate** and below it in the request path: the gate fails **closed**, the router
fails **open to the Deliberate lane**, and merging them would force one failure mode onto both
(ADR-013 §4).
_Avoid_: lane classifier, intent router

**Lane keyword fallback** — `lane.keywords.keyword_lane`, the router's second choice, for free-typed
input that declares nothing. Pure, no I/O, and its requirement runs **one way only**, like the
guardrail's **Keyword fast path**: it may miss a Fast lane request — the miss costs an approval step
— but it may never claim an escalation or a ticket for the Fast lane, because the approval step *is*
the associate confirming the ticket before it is raised. Hence the Deliberate vocabulary is matched
first, wins outright, and is the broader list; the default when nothing matches is Deliberate.

**Fast-lane latency** — the measured end-to-end cost of a Fast lane request, against the sub-10s
target. **Not yet measured.** ADR-013 makes the measurement the sole trigger for reopening the
orchestrator-bypass question, so until there is a number, no bypass is built. The probe is
`scripts/measure_fast_lane_latency.py`; the roster it needs is the **store assistant roster**,
authored in #19.

**Identity boundary gate** — the deterministic code gate in the request path that refuses
personal, individual-identity questions from a shared store device, executed **before the lane
router and before orchestration**. Keyword fast path plus an embedding-similarity tier; **fails
closed**; on a match the request short-circuits with no agent invoked and no tokens spent. It is
not the accelerator's prompt-based team-scope evaluation, which fails open in two places. The
similarity tier scores a **Two-class margin**, not a bare similarity. Lives in
`src/backend/guardrail/gate.py` and runs from `process_request` as the **first** thing after the
caller is known — above the team lookup, above `rai_success` and above the orchestration manager,
because the content-safety check instantiates an agent and a refusal that paid for one would
falsify the cost claim. See [ADR-014](docs/ADR/014-deterministic-identity-boundary-gate.md) and
[ADR-015](docs/ADR/015-two-class-margin-for-the-identity-boundary-gate.md).
_Avoid_: guardrail prompt, scope prompt, content filter

**Keyword fast path** — the gate's first tier (`src/backend/guardrail/keywords.py`): pure HR and
payroll vocabulary, no I/O, matched on word boundaries. Chosen for **what the vocabulary is**, not
tuned until it swept the Guardrail corpus — a list fitted to the corpus would stop the corpus being
evidence, the failure mode ADR-015 rejected for the anchors. Its hard requirement runs one way
only: it may miss a personal question (the similarity tier is behind it), but it may **never** trip
on a store-level one.

**Session identity** — who, if anyone, is signed in on the shared device
(`src/backend/guardrail/identity.py`). Defaults to **anonymous**, and anonymous is the *refusing*
state, so absent, empty, half-written and malformed records all resolve to it. The gate checks it
first and admits a named identity outright — the **Mocked unlock** is a parameter of the gate, not
a second gate. It is read out of **Session state**; #27 writes a name into it.

**Session state** — one session's server-side state (`src/backend/session/store.py`, route
`/api/v4/session_state/{session_id}`). Held in the Cosmos memory container rather than in browser
storage so a mid-demo reload does not lose it, and it carries exactly the two things the client
cannot re-derive: the **Session identity** the gate reads, and the **Lane** taken — re-deriving a
lane in the browser would be a second **Lane router** with its own opinion. An ordinary record in
the schemaless container: partitioned by session, discriminated by `data_type`, reached through the
generic CRUD, so it cost one `DataType` member and one model and **no migration**. Like the
container's other records it carries its `user_id` and reads are scoped by it, so one user's
session record cannot unlock another user's gate. Two invariants carry the design: a read is
**total** (a session nobody has written to reads back as the state the demo opens in, never `None`)
and a write is a **merge** (the sign-in beat owns the identity, the
request path owns the lane taken, and neither may erase the other; a field present and null is an
explicit clear, which is what signing out is). Acquiring it is the one thing above the Identity
boundary gate in `process_request`, because the gate's identity is its *input* — a Cosmos read
instantiates no agent — and a container that cannot be reached leaves the identity anonymous, so an
infrastructure failure refuses rather than admits.
_Avoid_: session storage, browser state, conversation state

**Policy block** — a refusal by the Identity boundary gate. Rendered distinctly from a
**retrieval miss** — an honest "that procedure is not in the library" — because conflating the two
makes a governed refusal look like a bug. On the wire it is HTTP **403** with
`detail.kind == "policy_block"` (`src/backend/guardrail/refusal.py`), which is what lets the
frontend give it its own neutral surface instead of the error toast
(`src/App/src/api/policyBlock.ts`). A retrieval miss is not a failed request at all — it arrives
as an answer.

**Mocked unlock** — the post-"sign-in" state in which the Identity boundary gate admits the
previously refused question and answers it from mocked data (#27). A parameter of the gate, not a
second gate. Mechanically it is a name written into **Session state**; the gate reads it back on
the next request. No real identity provider is involved — no Entra, no Okta, nothing.

The gate reports **which** admitted question it saw (`GateVerdict.personal`) rather than letting the
request path classify it again: a second classifier could disagree with the first, and the
disagreement would be invisible. `personal` is a classification, **not** a synonym for `refused` —
a request refused because the embedding tier was unreachable is `refused, not personal`, because
*could not tell* is a different fact from *decided it was personal*. The answer inherits the
**Keyword fast path**'s one-way requirement whole: it may miss a personal question, which then
reaches the ordinary agents and is honestly declined, but it may never claim a store question as
personal — that answers "how do I close the store?" out of somebody's PTO balance.

It short-circuits where the refusal does, with **no agent invoked and no plan persisted**, so the
answer costs what the refusal cost. It arrives on a *successful* request carrying a null `plan_id`,
which the surface must not read as a failure to create a plan.

**Associate record** — the mocked personal record the unlock answers from
(`src/backend/associate/records.py`). Authored demo content, and the demo's most sensitive: every
other invented thing here is about a store, this is about a person's pay. Looked up by **whole
name** or whole first name, never by substring — a loose match answers one associate's question out
of another's record, which is the identity form of the claim the gate exists to refuse. **No record
is a true answer**: a name nobody authored a record for falls through to the ordinary agents, which
hold nothing about an individual, rather than inventing a balance. The **Personal answer** shows the
record **whole** rather than picking out the field the question asked about — that would be a third
classifier behind the gate's two, and a third classifier can report the wrong number.

**Signed-in device** — the browser's memory that the presenter tapped sign in
(`src/App/src/models/signedInDevice.ts`). **Not** the identity: the identity is the record in
**Session state** that the gate reads, and the gate reads nothing else. `sessionStorage`, so a fresh
tab is an anonymous shared device and there is nothing to reset between rehearsals; **signing out is
forgetting**, because there was never an identity provider to revoke anything with. A **Policy
block** forgets it too — the gate refusing *is* the statement that nobody is signed in, and a header
that went on naming an associate the gate has just declined to answer for would be the surface
saying something that is not so. A session is one conversation (one **Simulated ticket**, one
**Lane** taken), so the tab does not re-use the session it signed in on: `TaskService.createPlan`
writes the identity into each new session as it creates it, and a sign-in that could not be written
leaves the request anonymous, which refuses.

The browser **never authors the associate's name**; it stores what the sign-in route returned. Two
strings in two languages are free to drift, and the drift's symptom is a header confidently naming
somebody the gate will not answer for. The header therefore also ignores the EasyAuth principal
entirely — on this deployment EasyAuth is off, so a header driven by it would have claimed a
signed-in user while every personal question was refused.

Recorded in [docs/mocked-unlock.md](docs/mocked-unlock.md).

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
see [ADR-012](docs/ADR/012-grounding-option-a-dataverse-documents-only.md). Branded **Circle K** by
[ADR-019](docs/ADR/019-rebrand-the-sop-corpus-to-circle-k.md), which reversed the fictional banner it
carried before so the **Grounding panel**'s snippet reads coherently under the Circle K header; the
procedures under that banner are still 100% invented. The banner lives once, in
`content/sop/corpus.toml`, and `check-sop-agent.sh --probe` reads it back out of a live conversation
because the rebrand rewrote every document without renaming one — the check that counts uploaded
documents by name passes either way.
_Avoid_: SharePoint SOP library, the SharePoint source

**Copilot Studio SOP agent** — the single low-code agent and the entire cross-platform proof.
**Store SOP Assistant** (`cr48b_StoreSopAssistant`) in the tenant's Default environment, grounded on
the **SOP corpus** uploaded as Dataverse documents, published with **no authentication** and reached
from the orchestrator through an MCP tool like any other tool. See
[ADR-011](docs/ADR/011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md) and
[docs/copilot-studio/sop-agent.md](docs/copilot-studio/sop-agent.md).

**Authored here** — the rule that the agent's every component is written in
`scripts/copilot_studio/sop_agent.py` and pushed through the Dataverse Web API, never edited in the
Copilot Studio portal. `pac` cannot authenticate unattended, so the Web API is the seam; the
consequence is that the repository is the source of truth for what the agent says, and the
`authored-here` check fails on any component it did not write. The thirteen system topics a portal
template copies are **not** among them — generative orchestration answers from the uploaded
documents without any of them, measured live.

**Honest miss** — the rehearsed out-of-corpus beat: a question whose procedure is not in the SOP
corpus is refused plainly and told where to go instead, rather than answered plausibly. Two
mechanisms together, and neither alone is enough: `useModelKnowledge: false` in the agent's
configuration is what stops the model answering from its own knowledge, and the **Fallback topic**
supplies the wording the check looks for.

**Publish propagation** — the gap between publishing the Copilot Studio SOP agent and a
conversation seeing the change. A **new** conversation gets published content immediately; a
conversation **already open** across the publish keeps the old content indefinitely. The publish
itself took 11.6–85 s across five measurements. Rehearsal rule: open a fresh conversation after
every publish, and freeze the agent before the demo.

**Direct Line** — the GA transport between the orchestrator and the Copilot Studio SOP agent.
Chosen over A2A on fit, **not** on availability — A2A reached GA in April 2026, and repeating the
"A2A is Preview" line is repeating a known error (ADR-011). The token endpoint is resolved per
environment from `PvaGetDirectLineEndpoint`, never assembled from the default hostname. The client
lives in the **backend** (`src/backend/sop/`), not the MCP container, which ships `httpx` and only
its own directory; the SOP tool relays to `POST /api/v4/sop/ask`.

**Direct Line base URL** — resolved, never assembled, in two steps then a refusal: the regional
channel settings service first, then the **`aud`/`iss` claim of the token the environment issued**,
then an error that becomes the fixed failure message. The second step exists because this
environment serves *no* channel settings — `PvaGetDirectLineEndpoint` returns a legacy
`powervamg…gateway.prod.island.powerapps.com` host that 404s on every settings path, and the
`<envid>.environment.api.powerplatform.com` host is NXDOMAIN. The resolution is cached only when it
is a **verdict** — settings that answered, a 404 or 501, or a name that does not exist. A 408, 429,
5xx, timeout or `EAI_AGAIN` resolves that one conversation from the token claim and leaves the
preferred source to be asked again.

**Conversation-scoped token** — a Copilot Studio Direct Line token carries a `conv` claim, so it
belongs to one conversation. Reusing it for a second `POST /conversations` **rejoins the first** and
replays its transcript, which made the demo's honest miss answer with SOP-102's closing steps. A
token is fetched per conversation and never cached across them; the **3600 seconds** it lives bound
that one conversation, and the client refuses an answer timeout that would outlive it.

**SOP tool** — `search_store_procedures`, the MCP tool on its own `sop` domain that puts the
Copilot Studio agent in the orchestrator's hands. An agent is given it by declaring
`use_toolbox: true` and `toolbox_filter: "sop"`, which points it at the `/sop/mcp` domain server and
allows that one tool. One fast retry, then a fixed failure message with
no citations — never a fallback to model knowledge and never a local copy of the SOP corpus, because
an answer arriving when the Direct Line path is broken is evidence against the cross-platform claim,
not for it.

**Settle polls** — the drain returns after **two** consecutive polls that add *nothing*, not on the
first activity that arrives. A generative answer is delivered as however many activities the agent
chose to send, and a single quiet poll can land between two of them, so returning early hands back a
preamble and drops the citations with it. The answer timeout stays a failure even once the agent has
spoken: a preamble returned because the clock ran out is a timeout dressed as an answer.

**Store content pack** — `content_packs/store_assistant/`, the demo's own content, authored in #19.
Two blob indexes: `store-troubleshooting-index` (the runbooks) and `store-operations-index` (the
store profile and the ticket template), seeded as `store-troubleshooting-kb` and
`store-operations-kb`. **Not** one of the six stock content packs #25 suppressed, which is why the
use-case selection does not gate it — `none` means no *stock* pack. The documents are authored as
the indexed artefact: `index_datasets.py` decodes anything that is not `.pdf`/`.docx` as UTF-8 and
indexes it whole, so the markdown *is* the document and there is no build step. Deliberately unlike
the **SOP corpus**, which must be built to `.docx` for Copilot Studio.
_Avoid_: sample data, seed data

**Troubleshooting runbook** — `RB-201` and up, the store's own equipment knowledge, indexed into
Azure AI Search and reached through a **Foundry IQ Knowledge Base**. Each one branches, names what
an associate has usually already tried, and says where to stop. Never merged with the **SOP
corpus**: the two provenances have to be visibly separate for the **Grounding panel** to be able to
say which platform answered. The runbooks are a different corpus reached by a different tool, so
`content/sop/corpus.toml`'s `absent_terms` are asserted against them too — a car-wash runbook would
answer the rehearsed **honest miss** and the SOP corpus' own verifier could not see it.

**Store assistant roster** — the three Foundry participants in
`content_packs/store_assistant/agent_teams/store_assistant.json`, uploaded under
`00000000-0000-0000-0000-000000000223`, which is the identifier `selectStoreAssistant` looks for.
`TroubleshootingAgent` (`gpt-5.4`, the runbook knowledge base, `user_responses: true`),
`ShiftTasksAgent` (`gpt-5.4-mini`, the `sop` toolbox) and `EscalationAgent` (`gpt-5.4`, the
operations knowledge base). The manager runs on `ORCHESTRATOR_MODEL_NAME` (ADR-003).

**Workforce agent** — `WorkforceAgent`, a fourth participant, decided 2026-08-13 and not yet built.
It answers an **HR process question** and never an individual's record. Named for its function
rather than for Workday because the surface would otherwise claim an integration that does not
exist, which is the rule every other simulated thing here is held to.
_Avoid_: WorkdayAgent, HR agent

**HR process question** — a question about how an employment task is performed ("how do I swap a
shift with another associate?"), as against a **personal question**, which is about an individual's
own record ("how much PTO do I have?"). Only the second is the **Identity boundary gate**'s
business. The first has to clear both of the gate's tiers, which is why the wording of the beat that
asks one is a design decision and not copy: the **Keyword fast path** is deterministic and
inspectable, but the similarity tier is a live model call that can refuse a process question on
stage.

**The SOP tool has one holder, and it has nothing else** — `ShiftTasksAgent` declares
`toolbox_filter: "sop"` and **no** `knowledge_base_name`. An agent holding both a Foundry knowledge
base and `search_store_procedures` chooses between them turn by turn, and the branch it does not
take is the cross-platform hop the demonstration rests on. A hop that happens four runs in five is
not a claim anybody can make on stage.

**Silent agent skip** — `AgentFactory.get_agents` catches `UnsupportedModelError`, logs a warning
and continues, so an agent whose `deployment_name` is not in the `SUPPORTED_MODELS` allowlist — or
absent entirely — is dropped. The upload returned 200, the team is in Cosmos, the surface shows the
assistant, and one member of the cast never speaks. There are **two** allowlists and they do not
agree: `validate_team_models` at upload time hard-bypasses `gpt-5.4-mini`, `gpt-5.4`, `gpt-5` and
`o3` by name and fails open on any exception, while `create_agent_from_config` at run time reads the
environment variable. `python -m store_pack roster` closes the gap by reading the team back out of
the deployment after upload; both post-deploy entry points run it.

The pack, the roster and that check are recorded in
[docs/store-content-pack.md](docs/store-content-pack.md).

## Memory of one shift

**Attempted step** — something an associate has reported already trying on the fault in front of
them. Read out of what they typed by `troubleshooting.steps`, which is pure and no I/O like
`lane.keywords`, because *never walk them through the same failed step twice* is only mechanical if
"the same step" is something code can decide. Its requirement runs **one way only**, like the **Lane
keyword fallback**'s: it may miss and offer a step already tried — the associate says so again and
the record grows — but it may never claim a step was attempted that was not, because that step is
then silently skipped and the equipment stays broken. Hence containment on a single shared word is
refused, a denial records nothing, and the words the clarification path substitutes on a timeout
record nothing either.
_Avoid_: tried step, history, checkpoint state

**Troubleshooting record** — one session's attempted steps, and what broke, held in the Cosmos
memory container (`src/backend/troubleshooting/store.py`). Framework checkpoint state is in-memory
and must not be relied on, so this is persisted **explicitly**. An ordinary document like the
**Session state** beside it: partitioned by session, discriminated by `data_type`, reached through
the generic CRUD, so it cost one `DataType` member and one model and **no migration**. Two
invariants, both inherited from that sibling: a read is **total** (a session nobody has written to
reads back as *nothing tried*, which offers the whole runbook) and a write is a **merge** (the steps
a first turn recorded are exactly the ones a later turn must not repeat). Every method swallows
failure — the record is memory of one shift and the answer is the associate's, so an unreachable
container costs a repeated step where raising would cost the turn.

**The clarification seam** — `OrchestrationManager._handle_tool_approvals`, where the manager already
intercepts the associate's answer before approving `request_user_clarification`. Both halves of the
memory ride it: the **write**, because that is where the report actually arrives, so it happens on
every clarification turn rather than whenever a model remembers; and the **read**, because the tool
body returns exactly what was stored, so an agent cannot proceed without having been told what it
must not repeat. Fetching would have been a tool call the model could skip.

**Current turn** — the process-local note of which session a user's request in flight belongs to
(`troubleshooting.turn`), left by `process_request` and read by the troubleshooting bridge. Nothing
on the wire between the MCP container and the backend names a session or a user: `ask_user`'s pattern
has a model copying a UUID out of its instructions, and a mis-copy here writes one associate's
attempted steps onto another's fault. `sole_turn()` applies **the same rule as `sole_user()`** —
exactly one, or nothing, never a choice between two — which is the third of #21's three named
constraints, stated out loud rather than engineered around. A note expires after
`TURN_TTL_SECONDS`, longer than the 300-second clarification wait a turn can contain, because
without an expiry one stray second user would leave `sole_turn` refusing for the rest of the
process's life.

**Troubleshooting tools** — `list_attempted_steps` and `record_attempted_steps`, on their own
`troubleshooting` MCP domain, held by `TroubleshootingAgent` alone. The MCP container has **no Cosmos
access at all** — no connection configuration and no dependency — so they reach the record over HTTP
through `BackendClient`, the pattern the **SOP tool** and the clarification bridge already use.
`TroubleshootingAgent` therefore holds a Foundry knowledge base **and** a toolbox, which the SOP
tool's holder deliberately does not: that rule is about two *grounding* sources competing to answer
one question, and these tools ground nothing — they answer *what has this associate already tried*,
which the runbook knowledge base cannot answer and which cannot answer an equipment question. There
is no branch to take.

**Escalation due** — three or more distinct attempted steps, at which point the note the agent reads
asks it to offer a service ticket. A property of the record rather than of the model's mood; below
the threshold, offering a ticket reads as the assistant giving up after one try. #22 picks the
record up from there — `TKT-001`'s attempted-steps field is this list, in the associate's own words,
**never re-typed**, and that runs one way in three places rather than being asked for: the tool has
no such parameter, the route discards a supplied value, and the draft overwrites it from the record
even when correcting.

Recorded in [docs/troubleshooting-memory.md](docs/troubleshooting-memory.md).

## Surfaces

**Store surface** — the branded chat surface the presenter opens: the **Circle K Frontline Store
Assistant**, scoped to **Store 223**, with **no user identity** (#25). One module,
`src/App/src/models/storeSurface.ts`, holds every string the surface says about itself, because the
left panel's toolbar, the conversation's header, the browser tab and the identity chip are four
places to disagree about which assistant this is.

**Store identity** — the header's two claims: the store the shared device belongs to, and who is
signed in on it. The anonymous state is **stated out loud** ("No user signed in") rather than left
as blank space — blank space reads as a component that failed to load, and the audience has to be
able to see the "before" of the before-and-after that #27's sign-in completes. `anonymous` is the
literal principal the backend returns with EasyAuth off, so it is *nobody*, not somebody called
anonymous. It lives in the conversation's header and **not** in the left panel, which is hidden at
the phone breakpoint — an identity claim the associate cannot see is not a claim.
_Avoid_: user card, login button (both were the accelerator's, and both are gone)

**One assistant** — there is no team picker (#25). Choosing between specialists is the **Lane
router**'s job and the orchestrator's job; an associate mid-shift has no basis for the choice, and
asking them to make it turns getting an answer into a routing decision. The picker, its upload
dialog and the EasyAuth login button were deleted rather than hidden — a picker that is merely not
rendered is one prop away from returning.

**Stock content packs** — the accelerator's six seeded agent teams (RFP Evaluation, Retail Customer
Satisfaction, HR Employee Onboarding, Marketing Press Release, Contract Compliance Review, Content
Generation). Suppressed as part of R1's single-assistant surface (#25), in two places, because
either alone leaks:

| Half | Where | What it stops |
| --- | --- | --- |
| Surface | `selectStoreAssistant` | A pack already in Cosmos being shown under the Circle K header |
| Deploy | `installs_use_case`, `MACAE_USE_CASE=none` | Six unused agent teams being seeded at all |

`selectStoreAssistant` **recognises** the store assistant — by `STORE_ASSISTANT_TEAM_ID`
(`00000000-0000-0000-0000-000000000223`, hex-only, and `223` reads as the store), and failing that
by name. There is deliberately **no `teams[0]` fallback**: that fallback *is* the suppression
failing, and a surface branded as one assistant while running another is the identity form of the
rule the transparency panels run on. No assistant is a state the surface can be in, and it says so.

**Simulated label** — the badge on anything whose content was authored for the walkthrough rather
than produced by a connected system (#25, R11's surviving fragment): **Store 223** and the
**Presenter alert**'s rehearsed words and the **Simulated ticket** (#22). The converse
matters as much — a badge on a real Foundry answer, a real Copilot Studio hop or a measured token
count gives away the demo's strongest evidence. Label the invented things, and only those.

**Stacking breakpoint** — 900px, below which the shell's columns stack, the transparency rail sits
beneath the conversation, and the task-history panel is dropped rather than squeezed (#25, #58).
The associate is holding a phone in a store. `CoralShellRow`'s layout had to move out of an inline
style to get there: an inline `flex-direction: row` beats a media query, so the breakpoint would
have been present, correct and completely inert.

**Grounding panel** — the R6 surface showing where an answer came from. Driven by **two signals
combined**: a "source used" event emitted server-side over the existing WebSocket, which proves
*which platform* answered, and citation data parsed from the SOP agent's response, which supplies
the document detail. Neither alone satisfies the requirement. The citation arrives structurally in
the activity's `entities`, with **no `url`** — and `appearance.abstract` is the *filename*, not a
snippet, while `appearance.text` is the whole document (see **Citation appearance** below). The
panel renders `Citation.snippet()`, which truncates `text`; rendering `abstract` prints the filename
twice.

The panel leads with the **platform** and not the document — `Copilot Studio`, over the route
`Foundry orchestrator → Copilot Studio → Dataverse` — because the claim R6 exists to make is that
*this one answer left Foundry*. **Dataverse**, never SharePoint. It has three states (#24): cited,
uncited (the honest miss, rendered explicitly rather than as an empty panel), and **no signal**, in
which it describes itself and asserts nothing — it does not say the answer came from Foundry,
because nobody told it that and a swallowed push looks the same from here.

The panel is **scoped to one answer** and goes dark the moment the next question is submitted
(`requestStarted`, #24). A question answered inside Foundry emits no `source_used` at all, so a
panel that persisted would credit Copilot Studio on stage with an answer it never gave — the same
lie in a different direction from emitting for a failed reply. A citation the backend could not
**name** is still rendered, labelled `Unnamed document`: `citations_from_activity` emits `name: ""`
when the appearance metadata has none, and dropping it would empty the list and print the *uncited*
copy, reporting an honest miss that did not happen. Only a citation with neither a name nor a
snippet is dropped, because there is nothing there to render.

**Source used** — the server-side half of that pair, emitted as `WebsocketMessageType.SOURCE_USED`
from the `/sop/ask` bridge once the Direct Line reply is in hand (#23). Built by
`transparency.source.source_used`, which carries `platform`, `source`, `agent_name`,
`conversation_id` and the citations. A **failed** reply emits nothing: the fixed failure message is
the backend's own words, so lighting the panel for it would credit Copilot Studio with an answer it
never gave — the lie #18's deadline rule exists to refuse. A **successful answer with no citations
does** emit, because that is the rehearsed out-of-corpus honest miss, and the panel showing the
route with nothing retrieved is exactly the beat.

**Citation appearance** — the `appearance` object inside a Direct Line citation entity:
`name` and `abstract` both carry the uploaded document's filename, and `text` carries the entire
document as HTML. ADR-011 was written expecting `abstract` to be the snippet; it is not, so the
Grounding panel truncates `text` itself or shows the name alone.

**Token meter** — the R7 per-agent call and token counter. Net-new: the accelerator emits no token
telemetry. Its emission point is the executor-completed branch of the event stream, as
`WebsocketMessageType.TOKEN_USAGE` (#23). The counts are read by **duck typing** in
`transparency.tokens` — `agent_framework` is stubbed in the backend suite, so a reader written
against `isinstance` would be testing the stub. Three levels are searched, and the **first that has
a number wins**: the item's `contents` (where a `"usage"` content sits), an `AgentExecutorResponse`'s
wrapped `agent_response` (where streaming accumulates usage after stripping it out of contents), and
the item itself. Reading all three double-counts the same cost, which is as wrong as reporting
none. When no usage was reported the event is **not sent** — a zero would read on the meter as *this
agent was free*, and R7's guardrail column (a refused request adds nothing) depends on nothing being
the only thing that looks like nothing. That absence is logged at debug: whether the framework
reports the orchestrator's own usage is **not verified live**, because
`StandardMagenticManager._complete` returns `response.messages[-1]` and drops
`AgentResponse.usage_details` on the way.

The panel (#24) is one row per agent in the order each first spent, with **tokens and estimated
Copilot Credits side by side** and a **model** column read from the workflow roster's
`deployment_name`, which is how "cheap models on cheap work" becomes checkable. Each row fills only
its own billing column, because the point is that the two models are not uniform.

**Not reported vs measured** — the rendering rule the whole meter turns on: `—` means *nobody told
us*, `0` means *we know it was nothing*. The Copilot Studio row's tokens are `—` because Direct Line
reports no count; the **Identity boundary gate**'s row is a real `0`, because the gate refuses before
the Lane router and before orchestration, so no agent ran. If an unreported cost also rendered `0`,
the one row that proves a refused request adds nothing would look exactly like an agent whose cost
never arrived. (The gate's own similarity tier *is* a model call — a small one, not an agent, and the
row's tooltip says which zero this is.)

**Copilot Credits** — Copilot Studio's unit of metered consumption. **2 per generative answer**
([Billing rates and management](https://learn.microsoft.com/microsoft-copilot-studio/requirements-messages-management);
a classic answer is 1), and the **Copilot Studio SOP agent** answers with `GenerativeAIRecognizer`,
so every answer it gives is generative. One constant in `models/meter.ts`, labelled **Est.** on
screen: it is Microsoft's published rate, not a measured bill.

**Transparency rail** — the host for the three panels, reading the Redux slice directly rather than
taking props so it can sit on **both** surfaces. It has to: the refusal happens on the home surface
and the answers happen on the plan surface, while the meter's total spans both.

**Presenter alert** — the R8 proactive shift-task message, triggered by a hidden backend route plus
a keyboard chord and pushed over the existing WebSocket. No wall-clock timer. The route is
`POST /api/v4/presenter/alert` with `include_in_schema=False` (#23) — hidden rather than
authenticated, which is why the **words and the recipient are both the server's**: the body selects
a name from a rehearsed roster in `transparency.alert` and there is no parameter that accepts prose.
That roster is **seven alerts** since #19, each naming a real `SOP-NNN` from the **SOP corpus**, so
whichever one the chord lands on leads straight into the cross-platform hop rather than stopping at
a reminder. Rehearsed words, not a live signal, which is why `SimulatedBadge` goes on them.

**Presenter chord** — the client half: **Ctrl + Alt + Shift + A**, matched on `event.code` and not
`event.key` (with Alt held, several layouts compose a different character, and a chord that only
works on US English fails on the borrowed laptop), with `metaKey` required *up*. **AltGraph** must
be up too: on Windows and several European layouts AltGr *is* reported as Ctrl+Alt, so without that
guard a presenter typing an accented character into the question box fires the chord mid-sentence.
An **auto-repeat** is not a press — holding the chord a beat too long would otherwise POST an alert
every repeat interval, and a stack of identical cards reads as a bug rather than a beat. A
**global** listener — the one place this codebase departs from its inline `onKeyDown` convention,
because the chord must work while focus is anywhere. It POSTs an **empty body**; the words and the
recipient are both the server's. **Global within the plan surface, though, not within the demo**:
`usePresenterChord` is mounted by `PlanPage` alone, and the recipient is resolved from the sole
connected WebSocket, which only a plan has. So on the home surface — where the six **Quick Task**
cards are, and where the refusal and the **Mocked unlock**'s answer render — no listener is bound
and the key does nothing at all. That is a fact about the walkthrough's order, not a detail: the
shift-task beat has to tap first and fire second, which is why the **Presenter runbook** says so.
The alert renders as visibly a different object from a reply
(`role="alert"`, its own badge), because an alert mistaken for an answer is worse than no alert.
Alerts survive a new question — an alert answered none, so a new one does not make it untrue — and
clear at the **conversation** boundary (`conversationStarted`), which the meter deliberately
survives.

**Out-of-band recipient** — how a push that no WebSocket asked for finds its socket.
`ConnectionConfig.sole_user()` returns the connected user when there is **exactly one**, and `None`
otherwise; it never guesses between two. Deliberately not the LLM-supplied `user_id` that `ask_user`
takes: a model mis-copying a UUID must not be able to make the Grounding panel go dark.
`send_status_update_async` reports whether it reached a socket, which every streaming caller ignores
and the alert route does not — the presenter pressed a key, and being told nothing happened is the
difference between a bug and a chord that missed.

**Connection window** — the gap between the backend scheduling the orchestration and the browser's
socket existing. `process_request` starts `run_orchestration_task` as a detached task *before* it
returns the HTTP response, and `send_status_update_async` **drops** anything pushed at a socket that
is not there. Since #63 the connect is initiated on the **`createPlan` response**, before `navigate`
(ADR-021) — so the window is the round trip and no longer the round trip *plus* a navigation, a
mount and a second GET. The plan page keeps a connect of its own for the path with no response to
hang off: a reload of `/plan/:id`. Two entry points, one socket — `connect()` returns the in-flight
handshake for a plan it is already opening rather than reporting a failure to the second caller, and
`isServing()` counts a handshake as serving because the response's connect and the navigation happen
in the same tick. The plan page **adopts** the socket it finds rather than opening a second one, and
owns the **disconnect** for as long as it is on screen, rather than leaving it to
`continueWithWebsocketFlow` — which only turns true once the plan GET has landed, so a presenter who
left before it did used to leave an adopted socket open with nothing to close it. Adoption is what
makes the teardown symmetric, and symmetry is what survives **StrictMode**: React 18 runs setup,
cleanup, setup, so a cleanup disconnecting a socket no setup reopens closes the adopted one on
arrival and puts #63 straight back on the dev server. On the backend, a socket asking to be closed
must **be the registered one**: a replacement supersedes its predecessor, and the predecessor's
endpoint then reaches its `finally` — keyed on the process alone that arrival closed and
unregistered the replacement, and every frame after it was dropped with nothing said. The window is
**narrowed, not closed**: the "No active WebSocket" log stays reachable and stays logged, because a
drop that still happens must stay visible to whoever reads the logs.

All three signals are recorded in full in
[docs/transparency-signals.md](docs/transparency-signals.md), and the panels that render them in
[docs/transparency-panels.md](docs/transparency-panels.md). The rebrand that surrounds them is
recorded in [docs/store-surface.md](docs/store-surface.md).

**Quick Task** — a starting task the presenter taps instead of typing. **Six of them since #26**,
one per beat of the walkthrough and rendered in the order it runs: the cross-platform hop, the
rehearsed out-of-corpus probe, the troubleshooting fault, the escalation that declares the
**Deliberate lane**, the boundary probe, and the shift-task query. Carries **Lane** metadata as
`StartingTask.lane` (#16) — an unvalidated `str` rather than the `Lane` enum, so an unrecognised
lane in an uploaded team definition fails open in the **Lane router** instead of rejecting the
whole upload. That is the right failure mode and a silent one, so every declared lane is put
through the real `parse_lane`. Tapping one fills the box; typing over the prompt clears the
declaration, because edited text is free-typed input and belongs to the **Lane keyword fallback** —
which is why each prompt is asserted to reach the lane it declares **through the fallback too**.
Three of the six prompts are read out of the corpus they were written against rather than restated:
the **rehearsed hit** and the **honest miss** from `content/sop/corpus.toml`, and the boundary
probe from the **Guardrail corpus**' measured `POSITIVE_PROBES`.

Recorded in [docs/quick-tasks.md](docs/quick-tasks.md).

**Rehearsed reply** — a one-tap answer to a **Clarification**, authored on the **Quick Task** that
provokes one (`StartingTask.rehearsed_replies`, #26). Only the troubleshooting beat asks a question
back — `TroubleshootingAgent` is instructed to ask what has already been tried — and answering it
was the last place in the walkthrough the presenter had to type. A tap submits through the ordinary
chat submit, so the clarification seam records the same **Attempted steps** a typed answer would
and the **Simulated ticket** carries them; the chips are a faster way to say the words, not a
second route around the seam. Every reply is put through the **real matcher**: each must record at
least one step (a denial records nothing, and a tap that records nothing looks exactly like one
that worked), together they must reach `ESCALATION_AFTER` (or nobody is ever offered the ticket R4
raises), each must be anchored in a runbook (or the memory changes no behaviour), and none may trip
the **Identity boundary gate**. Resolved from the plan's own `initial_goal` rather than router
state, which does not survive a reload; a goal matching no prompt resolves to none, exactly as an
edit gives up the declared **Lane**. The pending-clarification gate belongs to the component, not
its caller, for the reason the approval seam owns submission in #22.

_Avoid_: suggested reply, quick reply

**Rehearsed hit** — the walkthrough's opening tap, and the mirror image of the honest miss:
`corpus.toml`'s `[rehearsed_hit]` names the question *and the `SOP-NNN` that answers it*. The miss
has always been guarded, because the corpus keeps its `absent_terms` out; nothing guarded the other
direction, and a **hit decays into a miss**. Rename the document away and the tap still resolves —
honestly — as *that procedure is not in the library*, nothing goes red, and the cross-platform beat
the whole demonstration rests on has become the honest-miss beat played twice.

**The Lane badge claims only what a Lane decides.** `LaneBadge` said *"Answered straight away — no
approval step"*, and the boundary probe falsifies both halves: it is refused above the router and
never answered at all, and **Fast-lane latency is unmeasured**, so a tooltip would have been the
first place that number was asserted. It now reads *"No approval step — nothing is submitted for
you to confirm."*

**Simulated ticket** — the R4 service ticket (#22). `TKT-001`'s nineteen fields, everything unknown
reading `not reported`; the number is a sha256 of the session rendered `SIM-223-NNNN`, **derived not
counted**, because a counter is state a restart resets and a reissued number is two faults wearing
one identity. Labelled as simulated in the UI — unconditionally, with **no `simulated` flag on the
wire**, since every ticket here is simulated and a flag is a field that can be omitted. Persisted to
Cosmos, and it carries the **Attempted steps** from the troubleshooting record; if the associate has
to re-type what they tried, the requirement has failed.

**There is no submit tool** — the second confirmation is *unreachable*, not forbidden. The
`escalation` domain exposes one tool and it drafts; `DOMAIN_ALLOWED_TOOLS["escalation"]` names it,
and that entry is load-bearing twice, as #21 found — no entry means no filter, which lets the shared
`ask_user` through, and `ask_user` **is** a second confirmation. `EscalationAgent` keeps
`user_responses: false` for the same reason. A confirmation writes exactly three fields (status,
number, timestamp) and no content; a re-draft **merges** over the previous one rather than replacing
it, because an agent correcting the priority would otherwise blank the other eighteen fields of a
ticket the associate has already read.

**`TicketStore.read` is deliberately not total, and `TroubleshootingStore.read` is.** The
troubleshooting caller asks *what has this associate tried*, and **nothing** is a true answer. The
ticket caller is the approval seam, which runs on every approved plan on the **Deliberate lane** —
a total read would raise a blank ticket every time anybody approved anything. Nothing recorded must
stay distinguishable from a record of nothing.

Recorded in [docs/escalation-ticket.md](docs/escalation-ticket.md).

**Attempted steps** — what the associate has already tried, persisted explicitly to the Cosmos
memory container. Framework checkpoint state is in-memory and must not be relied on for this.

**Presenter runbook** — the walkthrough written for the person who will drive it: seven taps, what
to say at each, what the audience should be looking at, and a per-beat decision about whether to
continue when one fails. It exists because two of the affordances the demonstration depends on
have **no representation on screen at all** — the **Presenter chord** and the **Rehearsed reply**
chips — so for the presenter in the room the runbook *is* those features. Browser-first: their
access is the URL, and the repository is a documented fallback rather than the assumed starting
point. Every string it quotes is asserted to be the string the repository authors — the chord's
label, the **Quick Task** names and prompts, the chips, the **Rehearsed hit**'s `SOP-NNN`, the
**Store surface**'s own words — which is ADR-019's lesson applied to prose: a runbook carrying its
own copy passes a rebrand it never saw, and the presenter finds out in front of the customer.

Recorded in [docs/presenter-runbook.md](docs/presenter-runbook.md), guarded by
`src/tests/ci/test_presenter_runbook.py`.

**Progress narration** — what the surface says between a question being submitted and its answer
arriving. It enters a phase only when a **real signal reports it**, and where nothing has arrived
it holds the last true statement rather than inventing the next one. Five phases, each an
observable event: the `createPlan` POST in flight; the response's `lane`, read from the same field
`LaneBadge` reads; `connection_status`, which is plumbing and says nothing; `agent_message_streaming`,
which carries the **executor name** and so names *which* specialist is responding; and
`plan_approval_request` or `final_result_message`. There is deliberately **no "agents selected"
phase**: no such event exists, because `init_orchestration` and `AgentFactory.get_agents` build the
workflow in-process and emit nothing.

It replaces four authored strings — *"Initializing AI agents…"*, *"Generating plan scaffolds…"*,
*"Optimizing task steps…"*, *"Applying finishing touches…"* — that `PlanPage` rotated on a 3000ms
timer keyed to a GET-in-flight boolean. Nothing scaffolded and nothing optimised; they named four
stages the system does not have, three inches from a **Token meter** whose whole discipline is
**Not reported vs measured**. It also replaces six components each carrying their own copy, which
had already drifted into telling the story backwards — *"Plan created — Fast lane"* on the home
surface, then *"Loading plan data…"* on the plan surface. One module owns the strings, on the
**Store surface**'s pattern, and one Redux slice holds the phase **across the navigation**, because
across two components "only advances" is a coincidence and not a property. See
[ADR-023](docs/ADR/023-progress-narration-claims-only-what-a-signal-reports.md).
_Avoid_: loading message, progress indicator, spinner copy

**Available vs participating** — the roster says who *could* answer; the stream says who *did*.
The loading window's version of **Not reported vs measured**, and the same failure if the two are
conflated. Three specialists are available before a question is even typed — `selectedTeam` is in
Redux from `HomePage`'s mount, and `selectTeamAgentCount` has been sitting there unused — so
availability is a true thing the surface can state immediately and without the wire. Selection is
not: the **Identity boundary gate** refuses the boundary probe above the **Lane router**, where the
number that participate is **zero**, which is exactly why the meter renders a real `0` on that row.
"Three agents identified" over that beat contradicts the panel beneath it. Participation is claimed
one agent at a time, as each speaks, by the **Progress narration**.

The contradiction it removes was on screen: `PlanPanelRight` renders outside the loading branch, so
`AgentTeamPanel` — sourced from `planData?.team`, still `null` — read *"No agent roster loaded for
this conversation."* beside a spinner reading *"Initializing AI agents…"*.
_Avoid_: agents assigned, agents identified, agents selected

**Hidden completed tasks** — the presenter's clean panel between rehearsal runs. It **hides; it
never deletes**, and the control is named for that, because a label saying *delete* over a record
that survives is the identity form of the rule the transparency panels run on. `sessionStorage`,
following the **Signed-in device** precedent — within a run the clear survives a reload, and a
fresh tab is a fresh demonstration with the whole history back. A set of plan ids rather than a
flag, so a task completing *after* a clear still appears.

`delete_plan_by_plan_id` is implemented in `cosmosdb.py` and reachable from exactly one caller, the
human-feedback rejection path; there is **no REST route** and this does not add one. That unrouted
method is the trap — it reads as wiring nobody finished — which is why an otherwise reversible
decision is written down as [ADR-022](docs/ADR/022-completed-tasks-are-hidden-never-deleted.md).
The panel is only ever seen on a laptop: the **Stacking breakpoint** drops the task history rather
than squeezing it, because the associate is holding a phone.
_Avoid_: delete task, clear history, archive

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

**Dataverse search** — the environment-level index that makes **documents-based knowledge**
selectable, and so the thing the **Copilot Studio SOP agent** is grounded through. Off by default in
a Default environment; turned on by `Organization.isexternalsearchindexenabled`, which needs
**Dataverse System Administrator**.

The term names two facts that are easy to conflate and must not be: the **toggle**, which is true the
instant the PATCH returns, and the **sync**, which runs afterwards on its own clock and is what #17
actually waits on. Only a document coming back out of the index — **by its file content**, not by its
metadata, because knowledge sources retrieve against content — is evidence of the second. Recorded in
[docs/preflight/dataverse-search.md](docs/preflight/dataverse-search.md); checked by
`scripts/preflight/check-dataverse-search.sh --probe`, which probes rather than reads.

Measured at **181 seconds** cold on this environment against Microsoft's documented 15-minute
minimum — a floor, not a promise: the environment holds 148 MB and becomes populated as #8 and #19
land.
_Avoid_: relevance search (the old name), Dataverse search toggle (it is the sync that matters)

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

**Guardrail corpus** — 10 positive probes and 10 negative controls that are simultaneously R5's
acceptance test and the tuning harness for the Identity boundary gate's similarity threshold
(`src/backend/guardrail/corpus.py`, scored by
`src/tests/backend/guardrail/test_guardrail_corpus.py`). Runs against the **real** embedding
deployment under the `integration` marker and is deselected in CI — by `-m "not integration"` in
both `scripts/backend-tests.sh` and `.github/workflows/test.yml`, guarded by
`src/tests/ci/test_integration_marker.py` — because a mocked embedder would only prove plumbing.
It must exist **before** the threshold is chosen, and it earned that: the first scoring rule tried
did not separate it, and the corpus is what said so (ADR-015). Scored at **two seams**: the
**Two-class margin**, which is how the threshold was set, and `IdentityBoundaryGate.evaluate`,
which is what the request path actually calls — the composition can only *add* refusals, so the
gate is where the 0/10 false-positive criterion is genuinely at risk.
_Avoid_: guardrail test set, probe set (the probes are one half of it)

**Improvised paraphrases** — five personal questions phrased the way a presenter improvises them,
**held out of the threshold measurement** and asserted to miss the Keyword fast path
(`corpus.IMPROVISED_PARAPHRASES`). They exist because of what the gate-level corpus run showed: the
fast path claims all ten positive probes, so the Guardrail corpus never reaches the similarity tier
*through the gate*, and without a held-out set the tier's whole reason for existing would be
untested end to end. A refusal of one is therefore evidence about the similarity tier and nothing
else. Measured 5/5 refused at margins +0.05 to +0.48.
_Avoid_: extra probes (they are deliberately not part of the corpus that set the threshold)

**Personal-intent anchors** / **Store-scope anchors** — the two sets of exemplar phrasings the
similarity tier scores an incoming request against. **Production data, not test data**: the gate
embeds them once per process, on first use, and reuses them for every later request — a failure is
deliberately not cached, so a bad minute does not become a gate that refuses everything until the
container restarts. The store-scope set is a counterweight, not a second corpus — it exists so
shared sentence shape cancels.

**Two-class margin** — the similarity tier's score: nearest personal-intent anchor minus nearest
store-scope anchor (`similarity.personal_intent_margin`). Roughly ±0.6, **not** a cosine value in
0–1, so the sweep band straddles zero and a threshold read cold will be mis-read. Similarity to the
personal anchors alone does not separate the Guardrail corpus at any threshold — a store question
shaped like a personal one outscores a personal question shaped like neither. See
[ADR-015](docs/ADR/015-two-class-margin-for-the-identity-boundary-gate.md).
_Avoid_: similarity score, cosine score

**Measured threshold** — `IDENTITY_BOUNDARY_SIMILARITY_THRESHOLD`, **−0.08**: the midpoint of the
perfect band (−0.23 to +0.07) measured against `text-embedding-3-small` on the deployed
environment, 10/10 refused and 0/10 falsely refused. Negative on purpose — the fail-closed half of
ADR-014 expressed as a number. Re-derive it by running the corpus suite; the recorded value is
asserted to sit inside the band, so drift fails loudly.
_Avoid_: the guardrail threshold (ambiguous — the content-safety check has one too)

**Threshold sweep** — the corpus's report: one row per candidate threshold with probes refused and
controls falsely refused, marked `PERFECT` where both numbers are right. It is how the threshold is
**read off numbers** rather than guessed, and it is the reason a scoring rule that does not
separate is a visible finding rather than a silent one.

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

**Feedback loop** — a `(name, command)` row of the `## Feedback loops` table in `AGENTS.md`. Five
today: **Backend lint** (`scripts/backend-lint.sh`), **Backend tests** (`scripts/backend-tests.sh`),
**MCP server tests** (`scripts/mcp-tests.sh`), **CI-tooling tests** (`scripts/ci-tests.sh`, which
covers the repo's own tooling — the Advisory coverage report and the `scripts/preflight/` checks) and
**Frontend tests** (`scripts/frontend-tests.sh`, vitest over `src/App/src`, added by #24 — the
accelerator shipped vitest fully configured with no test file and no workflow). The
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
re-run the check rather than trusting the date on it. Six today: three about the Copilot Studio
tenant (#2, #5, #6), one about **Dataverse search** (#3), one about the **deployed environment**
(#12) — the model roster, Search's region, single-replica scale, keyless configuration and the
application images in
[docs/preflight/deployed-environment.md](docs/preflight/deployed-environment.md) — and one about the
**deployed surface** (#44), which is the same environment asked a different question: not whether
the infrastructure is shaped right but whether what it serves is *this* demonstration. See
[docs/preflight/deployed-surface.md](docs/preflight/deployed-surface.md).

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

**Demo validator** — the headless Playwright suite that drives the walkthrough through a real
browser and asserts what the demonstration *claims*. It asserts the deterministic transparency
signals — the platform the **Grounding panel** names, the citation's document identifier, the
**Token meter**'s rows, the **Lane badge**, the **Simulated ticket**'s number, the gate's refusal
copy, the signed-in header — and about model prose it asserts only that it arrived. A suite that
asserts a sentence a model wrote goes red when the model paraphrases and the demonstration was fine,
and a validator nobody trusts is one nobody reads on the morning it matters. It lives in `e2e/`,
behind `bash scripts/e2e-tests.sh`, and runs against **either** target — the deployed surface or a
local one — from one set of specs, because two descriptions of the walkthrough will disagree. Its
expectation is read out of the repository (the corpus manifest, the store pack, `storeSurface.ts`),
never pinned in the spec, for the reason [ADR-019](docs/ADR/019-rebrand-the-sop-corpus-to-circle-k.md) taught one
layer out: a check carrying its own copy passes a rebrand it never saw. See
[docs/demo-validator.md](docs/demo-validator.md).
_Avoid_: e2e test (the accelerator's own suite lived at `tests/e2e-test/`, drove an Entra login
against the pre-rebrand surface, was wired into no workflow, and was deleted in #47)

**Stage driver** — the same specs and the same page objects run headed and paced, for rehearsal and
as a way to present. Not a second suite: a second suite is a second thing to keep true. It is a
`projects` entry in the validator's own config, chosen with `bash scripts/e2e-tests.sh --stage`,
and it composes with `--target` exactly as the validator does. Its pace is `slowMo`, defined once in
`e2e/stage.ts` and adjustable with `E2E_PACE_MS`, because the number belongs to the presenter.
Dropping it leaves the validator working — it is presenter-facing and the first thing to cut. See
[docs/stage-driver.md](docs/stage-driver.md).

**Recorded fallback** — the video of the walkthrough that a run in which **every beat passed** leaves
in `e2e/artifacts/walkthrough/`: one file per beat in run order, a self-contained player beside them,
and a manifest naming the target, the commit and the time. The demonstration is handed to a presenter
who will be alone in the room and for whom "the Container App is cold" is not a recoverable
situation, so the last resort is a recording of the real system produced by the run that proved it
works. A red, filtered, sharded or two-project run leaves the previous recording untouched and says
why: a fallback made of the demonstration failing is worse than no fallback, because the presenter
finds out what is on it in front of the customer.
_Avoid_: demo video, screen recording (it is not made by hand, and it is not a marketing asset)

**Deployment drift** — the distance between the images the Container Apps are running and the commit
they were built from. Nothing measures it yet. `check-deployed-environment.sh` asserts the image is
not the **Placeholder image** and that it came from the expected registry, and never that it is
*current*; every declared loop runs against fakes and stubs, so all of them stay green while the
deployment is arbitrarily old. `check-deployed-surface.sh` (#44) catches the drift that has already
changed something visible — the served page title, the Quick Tasks, the SOP agent's token endpoint,
a grounded answer — which is a symptom rather than a measurement: it cannot tell a deployment one
commit behind from a current one. The measurement needs a commit stamped into the image at build
time, which is #48 and [ADR-018](docs/ADR/018-deployed-build-provenance-check.md).
_Avoid_: stale deployment, drift

## Confirmed findings

### The centrepiece beat is intermittent, and only a browser saw it (confirmed 2026-08-13, issue #47)

Eight runs of the **Demo validator** against `rg-macae-flw-v1` on the same afternoon: six green, two
red. Both failures were the rehearsed hit — *"How do I close the store?"*, the question
`content/sop/corpus.toml` exists to guarantee an answer to — coming back as the **honest miss**.
The hop itself completed: the **Grounding panel** named Copilot Studio and Dataverse. What it also
said was *"Searched Dataverse and found no matching procedure."*

`check-deployed-surface.sh`'s `grounded-answer` check passed on every attempt across the same
period, because it asks `POST /api/v4/sop/ask` **the corpus's own words**. The orchestrator does
not: it hands the SOP tool whatever the model rephrased the question into, and some rephrasings
miss. The check and the browser are asking different questions of the same agent, and only one of
them is asking the presenter's.

There is a second, coarser variant: the orchestrator sometimes does not call the SOP tool at all —
the **Group Chat Manager** answers from context, or the **Shift Tasks Agent** answers and the
**Troubleshooting Agent** asks a clarification. No tool call, no `source_used`, an honestly empty
panel.

The validator keeps `retries: 0`. A retry converts an intermittently-working demonstration into a
green run, and the presenter finds out in the room instead. This is #54, it is the walkthrough
observation (#46) and the presenter runbook (#53)'s most important input, and it is the first thing
the browser suite found that no API-level check could have.

### Every transparency signal was dropped in the browser, and 223 frontend tests were green (confirmed 2026-08-13, issue #47)

The first live run of the **Demo validator** timed out waiting for the **Grounding panel** on a
deployment where the hop itself was working perfectly. Reading the socket off the wire showed the
backend pushing `source_used` with `platform: "Copilot Studio"`, `source: "Dataverse"` and the
`SOP-102` citation, `token_usage` per executor, and `presenter_alert` — and the panel never lighting
at all, not even briefly.

`WebSocketService.handleMessage`'s `default:` branch called `this.emit(message.type, message)`,
passing the **whole frame** where the payload belonged, and `emit` wraps its argument again. So
every subscriber of the four out-of-band signals received `{type, data: {type, data: payload}}` and
read `message.data` as an envelope wearing the payload's name. The parsers in
`models/transparency.ts` are **total** — they return `null` rather than a half-filled object — so
they did exactly the right thing and returned `null`, and the panels, the meter, the alert and the
**Simulated ticket** all stayed dark in silence. Totality made the failure safe and invisible at the
same time.

Every test in the area passed throughout. The panels, the slice and the parsers each had their own,
and `useTransparencySignals.test.tsx` mocks `WebSocketService` and calls its handler with
`{ type, data: payload }` — the correct shape, hand-fed. Four tests agreeing with each other about a
shape the service does not produce is not four tests. `src/App/src/store/WebSocketService.test.ts`
is the missing seam: raw wire text, copied from a live run, through the real service, asserted with
the same parsers the panels use.

The **Simulated ticket** had the same defect twice over, once at each end. `orchestration_manager`
handed `send_status_update_async` a `{"type", "data"}` envelope, and that method wraps whatever it
is given — so the ticket left the backend one envelope deeper than the three transparency signals,
which hand over their bare payload. The backend tests read `call.args[0]["data"]`, which is the
caller's own envelope rather than the wire, so they agreed with the bug exactly as the frontend
mock did. Fixing only `handleMessage` would have left the card dark and every test green.

The lesson is about where the mock sits. A mock at a seam **inside** the boundary under test asserts
the author's belief about the collaborator, and no amount of coverage on either side of it will ever
disagree. The **Demo validator** found this on its first run because it is the only thing in the
repository that observes the browser.

### The deployed environment was 42 commits behind, and every loop was green (confirmed 2026-08-13)


The `macae-flw-v1` Container Apps were running images built at `2026-08-12T23:32Z` — before the
rebrand (#25), the transparency signals and panels (#23, #24), the Quick Tasks (#26), the mocked
sign-in (#27), the escalation ticket (#22), the troubleshooting memory (#21), the lane router (#16),
the identity boundary gate (#14) and the Direct Line client and SOP tool (#18). What was deployed
was substantially the stock accelerator, and it said so: the served page title was
`Multi-Agent - Custom Automation Engine`, while `src/App/index.html` reads `Circle K Frontline Store
Assistant` and nothing sets the title at runtime.

`COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT` was absent from the backend Container App and from every
secret store. The Bicep plumbs it through unconditionally (`infra/bicep/main.bicep`,
`infra/avm/main.bicep`) from a `main.parameters.json` substitution, so this was never an
infrastructure gap — the value was simply never set, and unset the SOP tool answers with its fixed
failure message rather than a grounded one. The centrepiece cross-platform beat could not have
worked.

Two things made this invisible. Every feedback loop runs against fakes, so none of them observes a
deployment at all; and the deployed-environment preflight checks an image's *provenance* but not its
*currency*. **Deployment drift** is the term for the gap, and a check comparing the deployed image
to `HEAD` is the answer to it.

Shipped 2026-08-13 (#44): the registry was filled first, `azd provision` put all three Container
Apps on images tagged with the commit, `post_deploy.sh` ran with `MACAE_USE_CASE=none`, and the
surface now serves `Circle K Frontline Store Assistant` with its six Quick Tasks and answers a
procedure question from Dataverse through Copilot Studio with a citation. The **image tag** is what
forced all three revisions to roll: `azd provision` only makes a new revision where the template
changed, so a re-pushed `latest` would have updated the backend — whose template gained the token
endpoint — and left the frontend and MCP apps serving what they had already cached. A tag is a
claim, not a stamp; #48 is still the measurement. See
[docs/preflight/deployed-surface.md](docs/preflight/deployed-surface.md).

### A CI-tooling test was dialling the live tenant (confirmed 2026-08-13, issue #44)

Two tests in `src/tests/ci/test_deployed_environment.py` called `main` with a stubbed model probe
and **no** `retrieve` stub, so the default `probe_knowledge_bases` ran — a real agent, against the
live Foundry project, from inside a suite whose whole premise is that it unit-tests the verdict
*without a tenant*. It passed for as long as retrieval happened to work and went red on a transient
empty result while the environment was healthy, which is the failure mode the derived probe question
(#30) exists to remove. Both now stub `retrieve`. The suite went from ~23s to ~5s, which is the
other tell: a unit suite that takes twenty seconds is doing something it should not.

### A Copilot Studio agent needs none of the thirteen template topics (confirmed 2026-08-13, issue #17)

A portal-created agent copies thirteen system topics — Greeting, Escalate, Signin, Search
("Conversational boosting"), OnError, StartOver, Goodbye and the rest. The Copilot Studio SOP agent
was first built with all of them, copied from an existing portal agent on the assumption that at
least the Search topic was on the retrieval path.

It is not. With `GenerativeAIRecognizer` and `GenerativeActionsEnabled`, the uploaded documents are
searched directly. All thirteen were deleted, the agent re-published and re-probed, and it answered
identically: fifteen numbered steps citing `SOP-102 Store Closing Procedure.docx`. What remains is
**three authored components** (instructions, greeting, honest miss) plus the ten uploaded documents,
which is what makes the **Authored here** rule enforceable — an agent carrying eleven behaviours
nobody wrote here cannot be reviewed here. Recorded in
[docs/copilot-studio/sop-agent.md](docs/copilot-studio/sop-agent.md).

### A Direct Line token is scoped to one conversation (confirmed 2026-08-13, issue #18)

ADR-011 records that Direct Line tokens live 3600 seconds, which invites caching one for its life.
A Copilot Studio token also carries a **`conv` claim**: reusing it for a second `POST /conversations`
rejoins the *first* conversation, and the drain replays its transcript. Measured live, the demo's
out-of-corpus probe came back with SOP-102's closing steps — the honest-miss beat answering as if the
document existed, which is the worst available failure because it looks like success. A token is now
fetched per conversation. Recorded in
[docs/copilot-studio/direct-line-client.md](docs/copilot-studio/direct-line-client.md).

### This environment serves no regional channel settings (confirmed 2026-08-13, issue #18)

ADR-011 requires the Direct Line base URL be read from the regional channel settings service and
never assembled. Here there is no such service to read: `PvaGetDirectLineEndpoint` returns a legacy
`powervamg.us-il102.gateway.prod.island.powerapps.com` token endpoint that 404s on every
`regionalchannelsettings` path, that gateway *is* the environment's own
`runtimeEndpoints["microsoft.PowerVirtualAgents"]`, and the
`<envid>.environment.api.powerplatform.com` host is NXDOMAIN. The rule survives via a second source
that is still the service speaking: the **`aud`/`iss` claim of the token the environment issued**,
which also confirms the 3600 seconds from `exp - nbf`. Neither source answering is an error, not a
fall-through to the default host.

### A Direct Line citation's `abstract` is the filename, not a snippet (confirmed 2026-08-13, issue #17)

ADR-011 predicted the citation URL would be absent for a Dataverse-uploaded document, and it is —
confirmed live. Its accompanying instruction to render "name plus snippet", reading `abstract` as
the snippet, does not survive contact: `appearance.abstract` is **identical to `appearance.name`**,
both the uploaded file's filename, and the snippet-shaped field is `appearance.text`, which carries
the *entire* document as HTML (3311 characters for SOP-102). The Grounding panel (R6) must truncate
`text` itself or show the name alone.

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

### The Workflow was *not* tagged with a team identifier at build time (confirmed 2026-08-01, issue #9 — **fixed** 2026-08-12, issue #15)

The comment at `orchestration_manager.py:236-238` claimed "The team_id tag is set on every workflow
we build/reset below". **That claim was false.** A static scan of `src/backend` found:

- **Assignments of `_team_id` on a Workflow: none.**
- Reads of `_team_id` on a Workflow: two — `orchestration/orchestration_manager.py`
  (`current_team_id`) and `api/router.py` (`cached_team_id`).

`init_orchestration` assigned only `workflow._team_config` and `workflow._manager_chat_client`. The
only place `_team_id` was ever set on a workflow object in the entire repository was
`src/tests/backend/orchestration/test_orchestration_manager.py:441`, where a test hand-set it on a
mock.

**Consequence — every request performed a Full workflow rebuild.**
`getattr(current, "_team_id", None)` always returned `None`, while `team_config.team_id` is a
required non-empty `str`. So `team_changed` was `True` whenever a cached Workflow existed, and
`needs_full_rebuild = current is None or team_switched or team_changed` was therefore **always**
`True`. Two consequences followed:

1. Every call closed and recreated all agents. There was no warm path, so the latency baseline for
   the fast lane must be measured against a full agent-pool rebuild, not against a cache hit.
2. `needs_workflow_reset` (`not needs_full_rebuild and workflow_terminated`) could never be `True` —
   the Lightweight workflow reset branch was dead code in production.

The same defect appeared independently in `router.py`, where `team_mismatch` was always `True`, so
`workflow_unusable` was always `True` on the request path too.

Confirmed empirically with a throwaway probe: replaying the existing reuse test
(`test_given_existing_workflow_when_no_switch_then_returns_it`) against a Workflow shaped as
production built it — i.e. with `_team_config` set and `_team_id` absent — took the rebuild branch
and called `init_orchestration` exactly once, where the committed test (which hand-set `_team_id`)
returned the cached Workflow untouched.

**Fixed in #15.** `init_orchestration` now assigns `workflow._team_id` (and `workflow._plan_review`)
at build time, and line 441 of `test_orchestration_manager.py` is deleted — that test now builds its
cached Workflow through `init_orchestration`, the way production builds it, so it is a regression
test for the tag rather than a test that papers over its absence. **A warm cache is reachable for the
first time, and the Lightweight workflow reset branch is no longer dead code.** The Fast-lane latency
number is still owed (see *Fast-lane latency* below).
