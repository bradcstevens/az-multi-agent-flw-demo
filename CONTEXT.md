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

**Plan record** — the row every request creates, before a **Lane** has been chosen for it. It is the
conversation's record and not a plan: the **Chat** list is that query, and the row also carries the
turn's streaming text and its clarification. It records the **Lane** taken, so a surface holding one
can tell whether that conversation was ever reviewable
([ADR-028](docs/ADR/028-a-reviewable-plan-is-earned-by-a-transaction.md)).
_Avoid_: plan, the plan

**Reviewable plan** — the plan the associate approves, and the only thing "plan" means when spoken
to an associate. It exists on the **Deliberate lane** and nowhere else, which is why a surface asks
for the approval frame rather than asking whether a **Plan record** exists. A request earns one when
it **commits something on the associate's behalf**; a question earns none, however many specialists
answer it (ADR-028).
_Avoid_: plan, the plan

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
`/process_request` response, is recorded into **Session state** so it survives a reload and onto the
**Plan record** so a conversation carries it, and is
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
Because Deliberate wins outright, the Fast vocabulary can be widened without ever costing a
transaction — which is the only direction that fails silently, and since ADR-028 it guards the shift
swap as well as the escalation.

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

**Chat** — the surface name for one **Session** and its persisted records. A Chat can contain more
than one **Plan**; the surface groups those plans as one conversation while the domain keeps
`Plan` and `session_id` as their precise names. A route served by a plans endpoint and grouped by
session is therefore still a chat surface, not a reason to rename the model.

The surface says it in its own names (#73, ADR-025): `ChatPanelLeft` (*"Chat history"*, **New
chat**), `ChatList`, `ChatPage`, `NewChatService`, `Chat` as the row, and the route **`/chat/:id`**
— whose `:id` is a **Plan**'s, because a row opens the chat's latest plan. `/plan/:id` still
redirects there, for the presenter who has the old path in a tab. `Plan`, `PlanStatus`,
`planSlice`, `PlanPanelRight` and the plan endpoints keep their names, and so does `TaskService`,
which creates Plans and signs a device in rather than owning the panel.

The list holds chats in **every** `PlanStatus` (#74). `GET /plans` filters nothing — it reads
`get_all_plans_by_team_id`, newest first — and `transformPlansToChats` returns one list rather than
an `inProgress` bucket the filtered endpoint could never populate and the panel discarded anyway.
The chat most worth resuming is the one that did not finish, and that was exactly the chat the
filter hid: a chat mid-escalation is `in_progress`, because a Chat's state is its **latest** plan's.
Each row therefore states its own state, in `chatStateLabel`'s words
(`src/App/src/models/chatState.ts`), which is total — a status the backend adds later reaches the
panel as itself rather than as a blank row. `failed` and `canceled` chats are listed too, which
makes rehearsal debris visible and is why **Chat deletion** follows. Each row carries an overflow
menu whose one item is that deletion (#75, ADR-026); the hide control it replaced is gone.
_Avoid_: plan history, task history, hide completed tasks

**Leaving a Chat** — going somewhere else while a **Chat** has a turn in flight: **New chat**,
selecting another chat row, or the logo. One act with one declaration, and it **ends that Chat's
turn** — the orchestration is cancelled and the **Plan record** written `canceled`
([ADR-031](docs/ADR/031-leaving-a-chat-ends-its-turn.md)). Scoped to the session left, so it can
never settle another Chat, and it never overwrites a **Settled status** a turn already reached. A
socket dropping is *not* leaving — a network blip must not kill a live turn — which is why browser
back and a closed tab remain a named gap rather than a guess. The associate is not asked to confirm
it: nothing is lost that a confirmation could protect.
_Avoid_: plan cancellation, cancel the plan, new chat confirmation

**Abandoned turn** — what **Leaving a Chat** produced before ADR-031, and what browser back and a
closed tab still produce: the client is gone, the orchestration keeps computing against a connection
that no longer exists, and every frame is dropped. Because the transcript is written only by the
browser echoing frames back, the turn leaves **no** record — no transcript row, no answer, and a
**Plan record** stuck at `in_progress` for ever, which no delete route will take. Not a turn that
was lost, but one whose loss the surface went on denying.
_Avoid_: orphaned plan, stuck plan, stale chat

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

**Store assistant roster** — the four Foundry participants in
`content_packs/store_assistant/agent_teams/store_assistant.json`, uploaded under
`00000000-0000-0000-0000-000000000223`, which is the identifier `selectStoreAssistant` looks for.
`TroubleshootingAgent` (`gpt-5.4`, the runbook knowledge base, `user_responses: true`),
`ShiftTasksAgent` (`gpt-5.4-mini`, the `sop` toolbox), `EscalationAgent` (`gpt-5.4`, the
operations knowledge base) and the **Workforce agent** (`gpt-5.4-mini`, the `workforce` toolbox).
The manager runs on `ORCHESTRATOR_MODEL_NAME` (ADR-003).

**Workforce agent** — `WorkforceAgent`, the fourth participant, decided 2026-08-13 (ADR-017) and
built in #52. It answers an **HR process question** and never an individual's record. Named for its
function rather than for Workday because the surface would otherwise claim an integration that does
not exist, which is the rule every other simulated thing here is held to.

Its grounding is the **Workforce procedure library** and it holds `toolbox_filter: "workforce"` and
no knowledge base — the shift-tasks agent's shape, and for the shift-tasks agent's reason. On
`gpt-5.4-mini`, because looking a procedure up and quoting what came back is not reasoning work and
the **Token meter** renders that claim on screen.
_Avoid_: WorkdayAgent, HR agent

**Workforce procedure library** — `src/mcp_server/services/workforce_library.py`, four authored
procedures (`WF-401` and up) about swapping a shift, changing availability, reporting an absence
and picking up an open shift. **Mocked, and it says so on every answer**: there is no employment
system behind this deployment and a surface may say nothing but may not say something that is not
so. Pure — no MCP, no network — so the store pack's own suite can ask whether the seventh tap
resolves to a procedure that exists, which is the check `[rehearsed_hit]` gives the opening tap.

It holds nobody's balance, rate, hours or entitlement, and neither tool takes an individual to look
one up: `list_workforce_procedures` takes nothing and `get_workforce_procedure` takes a topic. That
is ADR-017's boundary drawn in the vocabulary rather than in a prompt, and it is asserted from both
sides — the library's own text against the record vocabulary, and `DOMAIN_ALLOWED_TOOLS["workforce"]`
against anything that reads one.

**HR process question** — a question about how an employment task is performed ("how do I swap a
shift with another associate?"), as against a **personal question**, which is about an individual's
own record ("how much PTO do I have?"). Only the second is the **Identity boundary gate**'s
business. The first has to clear both of the gate's tiers, which is why the wording of the beat that
asks one is a design decision and not copy: the **Keyword fast path** is deterministic and
inspectable, but the similarity tier is a live model call that can refuse a process question on
stage. Since #52 the beat's question is the **Guardrail corpus**' eleventh
`NEGATIVE_CONTROL`, so that tier is measured against it rather than trusted — ADR-017's second
negative consequence, closed.

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

**The session is the conversation, and the conversation is what the shift had.** This entry and its
document — [docs/troubleshooting-memory.md](docs/troubleshooting-memory.md), *"The memory of one
shift"* — read as though they disagreed, and #61 is where the gap was load-bearing rather than
verbal. What the surface had wrong was not the key but its boundary: an associate who tries three
things and then asks for help is having **one** conversation, and the surface ended it at the home
screen. **Follow-on task** joins them. Re-keying the record to the shift was the obvious repair and
is rejected in ADR-024, because the requirement above runs one way and a wider key is exactly how
one fault's steps reach another fault's ticket.

**The clarification seam** — `OrchestrationManager._handle_tool_approvals`, where the manager already
intercepts the associate's answer before approving `request_user_clarification`. Both halves of the
memory ride it: the **write**, because that is where the report actually arrives, so it happens on
every clarification turn rather than whenever a model remembers; and the **read**, because the tool
body returns exactly what was stored, so an agent cannot proceed without having been told what it
must not repeat. Fetching would have been a tool call the model could skip.

**Only a clarification is a question** — the framework pauses on *every* approval-gated tool call and
the seam handed all of them to the associate, so a gated call that asks nobody anything arrived as
the placeholder *"The agent needs clarification."* and held the turn for the full wait (#62).
`orchestration.clarification` decides which pause is one: the clarification tool, with words in its
`questions`. Pure and no I/O, like `troubleshooting.steps` beside it, and its requirement runs the
**one way** the record's does — it may leave a real question unasked, and the agent is told so, but
it may never put a question to the associate that nothing will read the answer to. The lesson is
`ask_user`'s again at a different seam: **a pause is not a question**, and treating every pause as
one is how a **Rehearsed reply** is spent on a call that will not read it and an unasked answer is
written into the record the **Simulated ticket** is filled from.

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

**Send control** — the button that submits what has been typed, one component
(`components/content/SendControl.tsx`) on both surfaces, named out loud because it is an icon and
nothing else: **Send question** on the **Store surface**, **Send message** on the chat surface
(#56). It was two declarations that had already drifted — one repainted by a stylesheet Fluent
overrides, one by inline styles that override Fluent — so the surface's primary action rendered
transparent with a grey glyph and looked like its own disabled state. Nothing anywhere declares its
colour, and the two ways to break that fail differently: a rule in `styles/` loses, because Fluent's
styles are injected after an imported stylesheet — it reads like the thing the surface renders and
does nothing — while an inline style wins, and hardcodes past the theme. The surface has two
(`teamsLightTheme`, `teamsDarkTheme`), so a contrast ratio met by a hardcoded colour is met in at
most one of them. Colour is the theme's to state.

Unavailability is **`disabledFocusable`, not `disabled`** — a natively-disabled control leaves the
tab order, so the one affordance that asks a question disappears for a keyboard user instead of
saying why it cannot be used. `opacity: 0.3` on the input wrapper is not a claim a screen reader can
read.

**Character counter** — `ChatInput`'s count against the 5000-character cap, shown from
`COUNTER_INFORMATIVE_FROM` (the last 500) and not before. On an empty box a zero of five thousand is
noise beside the **Send control**, reporting a limit nobody is near; near the cap it is the only
warning that the textarea is about to drop what is typed in silence.

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

Declared **once**, in `storeSurface.css`, for every column the shell puts beside the conversation —
including the rail's *container* on the chat surface. A fixed pixel width and a `border-left` are
what a side column looks like, and below the breakpoint there is nothing to its left, so both are a
lie. `.plan-panel-right` kept them after the rail itself had given them up, which stacked the rail
as a 280px band with a left border wrapping a rail with a top border: the same disagreement one
level up. `CoralShellRow.test` now reads every such rule **out of the stylesheets** and requires
the breakpoint to release it — to `width: 100%`, `box-sizing: border-box` and `border-left: none`,
or to `display: none` — so the next column added beside the conversation cannot quietly decline to
stack. The border box is part of the release rather than a detail: these columns are padded and the
shell clips horizontally, so a content-box column at `width: 100%` is wider than the viewport and
loses its right-hand end silently, which for the **Token meter** is the credits column.

Stacking the columns is not the same as **sizing** them, and #60 is the second half. Three rules,
each read out of the stylesheets by the frontend loop rather than listed in it:

- **Declared is rendered.** A padded, fixed-width box carries `box-sizing: border-box`. The rail
  declared 320px and rendered 353px, so every container sized to its number clipped 33px of it.
- **One width per column.** The rail declares it; `.plan-panel-right` takes `width: min-content`,
  which is the rail's number and not a second one. It used to declare 280px with `overflow: hidden`
  around a 353px rail, amputating 53px at every desktop width with no scrollbar to say so.
- **One scroll region per column, and nothing shrinks when stacked.** Every column has a non-visible
  `overflow`, and a flex item with one has an automatic minimum size of **zero** — so the stacked
  shell crushed its children rather than scrolling, and a 900px conversation rendered 17px. The
  breakpoint releases both (`flex-shrink: 0`, `overflow: visible`), so the surface scrolls as one.

None of which reaches a column whose layout is an inline style. `Content` declared `flex: 1`,
`height: 100%` and `min-width: 320px` inline — the trap #25 already found in the shell, one column
over — so its layout moved to `storeSurface.css` too. The minimum is now 280px, because 320 plus the
task-history panel's 280 plus the rail's 320 is 920px of columns in a shell that stacks at 900, and
the 19px band above the breakpoint was clipped off the rail's end without a scrollbar.

**Heading outline** — the surface's structure, stated in headings rather than only in layout (#57).
A query for every heading element on the deployed page came back **empty**: Fluent's typography
components render a generic span unless they are told what element to be, so "How can I help?",
"Quick tasks", "Plan Overview", "Grounding", "What this cost" and "Agent Team" were all styled
spans and the whole surface was one undifferentiated run of text. Heading navigation is how a
non-visual user skims a page, and here it landed on nothing. WCAG 2.1 Level A, 1.3.1.

Two levels, declared once in `models/headingOutline.ts` on the `storeSurface.ts` precedent — a
level chosen beside each title is a level that drifts, and an outline that skips one is the same
defect in a different form. The **surface heading** is the assistant's name in the conversation's
header, and it has to be that one: the left panel's toolbar says the same name and is dropped at
the **Stacking breakpoint**, so a heading there is one the associate's phone never renders. Every
section — the question input, the Quick tasks, the plan overview, each **transparency panel** —
is one level below it. A third, `SUBSECTION_HEADING`, was added by #65 for a named part *inside* a
section, and has exactly one user: the Agent Team panel's count of who is available.

The outline is **conditional** (#78). "Plan Overview" heads the rail's plan section only where there
is a plan to *review* — the `plan_approval_request` frame, ADR-023's *Done* phase — because a `Plan`
is constructed before the **Lane router** has run and every request has one, so "a plan exists" is
not the question. On the **Fast lane** the section and its heading are not on screen at all: a
heading a non-visual user skims to and finds nothing behind is the same defect one step further on.
The outline is therefore asserted once per lane, and neither skips a level.

It costs the **transparency rail** most. The rail exists to be *skimmed*, and its panel titles are
what make it skimmable; rendering them as spans took the rail's argument away from exactly the
users who most need it stated in structure rather than in layout.

Applied with Fluent's `as` override, so the typography classes still beat the user-agent sheet and
nothing about the surface's appearance changes — except where a heading is **blockified**. A flex
item or a flex container is a block box, and a block-level `h2` picks up the user-agent's
`margin: .83em 0`: unzeroed, each transparency panel measured 71px instead of 48 and the Quick
tasks header 43px instead of 20. Every class that heads a section declares its own margin.

A **reply may not head the surface**. `react-markdown` renders a model's `#` as a real `h1`, and
the orchestrator emits `### {display_name}` into the reply stream, so an answer could put a second
top-level heading — and a skipped level — above the panels that explain that same answer.
`replyHeadings.tsx` gives those elements `role="presentation"`: they keep every pixel and give up
the semantics, on all three Markdown renderers, found by searching the source rather than listed.
Demotion was rejected because the conversation has no section heading of its own to descend from.
_Avoid_: visually-hidden headings — the outline is made of the titles the surface already shows.

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

The table gives its width up in the **names**, never the figures (#60): `white-space: nowrap` is
scoped to `.token-meter__number`, and `table-layout: fixed` makes each column a share of the rail
rather than a negotiation the largest token total wins. Unscoped, the table measured 448px inside a
320px rail and the column outside the box was the credits one — the panel that proves what an
answer cost, losing the number it exists to show.

The share the **Agent** column gets is the one that holds the longest word in the **Store assistant
roster** (#70). The table is **~257px**, not the 288px the rail's own arithmetic suggests: the panel
inside the rail is a card with 14px of padding and a hairline border of its own. `Troubleshooting`
measures **96.4px** at 12px and weight 600, so at 30% the name was snapped after eleven characters
in the panel whose job is to be the most credible thing in the room; the column holds **41%** now,
which is 101.4px of text. Every number in that sentence is *measured* rather than reckoned, and the
reckoning is why #70 took two goes: the ticket's own arithmetic and the first fix's each came out
short by their own several pixels and each was believed, the second of them with a green test
beneath it. The room came from **Model**, **Calls** and two points of **Tokens** — which keeps
enough to set the five-figure total #60 sized it for, with 0.9px to spare — by the same rule: a
model deployment breaks at its own hyphens and costs a line, while a token total is `nowrap`, so a
column too narrow for a five-figure count sets it across the estimated Copilot Credits instead of
wrapping it. `overflow-wrap: break-word` stays as the last resort for a name nobody sized the column
for — under `table-layout: fixed` the wrapping mode no longer decides the table's width, only what
happens to a word wider than its share — and it is scoped to the **body**, because a heading is a
label and the one heading that broke, `MODEL` as `MO`/`DEL`, was a column heading obeying a rule
written for data.

The **column headings are sentence case** for the same arithmetic: uppercase costs about a fifth of
a label's width, and once the Agent column took what its longest name needs, uppercase headings no
longer fit their columns. Having nothing telling them to break, they ran into each other. What still
does not fit is `Calls`, by 9.3px — holding every heading, every figure and a 96.4px name at once
needs 5.8px more than the table has, so one label overflows into its neighbour, which is what the
headings have always done and there is less of it than before.

**Agent display name** — one base name, two presentations, and the rule that says which. The base is
`getAgentDisplayName`: the roster's own name (`WorkforceAgent`, or the wire's humanised
`Workforce Agent` — the backend's `format_agent_display_name` deliberately does *not* strip the
suffix, because the surface does) cleaned to spaces with the trailing `Agent` removed. Prose adds it
back with `getAgentDisplayNameWithSuffix`: the **Agent Team** panel, the **Progress narration** and
the streamed reply headings all name an agent inside a sentence, where `Troubleshooting Agent` is
what an agent is called. The **Token meter** does not, because its column is *headed* `Agent` and a
cell repeating the noun says it twice — in 73px of rail, the second word is what pushed the first
into breaking mid-word. The meter was also the only panel reading `agent_name` raw off the wire,
which is why it was the only one that could disagree about a name at all. The exception inside the
exception: the guardrail row's name is this repository's own constant, not a name that arrived from
anywhere, so it is rendered as written — the **Identity boundary gate**, which a helper that
title-cases what it is handed would rename on screen.

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
and the answers happen on the chat surface, while the meter's total spans both.

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
recipient are both the server's. **Global within the chat surface, though, not within the demo**:
`usePresenterChord` is mounted by `ChatPage` alone, and the recipient is resolved from the sole
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
mount and a second GET. The chat page keeps a connect of its own for the path with no response to
hang off: a reload of `/chat/:id`. Two entry points, one socket — `connect()` returns the in-flight
handshake for a plan it is already opening rather than reporting a failure to the second caller, and
`isServing()` counts a handshake as serving because the response's connect and the navigation happen
in the same tick. The chat page **adopts** the socket it finds rather than opening a second one, and
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

**Quick Task** — a starting task the presenter taps instead of typing. **Seven of them since #52**,
one per beat of the walkthrough and rendered in the order it runs: the cross-platform hop, the
rehearsed out-of-corpus probe, the troubleshooting fault, the escalation that declares the
**Deliberate lane**, the boundary probe, the shift-task query, and the **HR process question** the
**Workforce agent** answers. Carries **Lane** metadata as
`StartingTask.lane` (#16) — an unvalidated `str` rather than the `Lane` enum, so an unrecognised
lane in an uploaded team definition fails open in the **Lane router** instead of rejecting the
whole upload. That is the right failure mode and a silent one, so every declared lane is put
through the real `parse_lane`. Tapping one fills the box; typing over the prompt clears the
declaration, because edited text is free-typed input and belongs to the **Lane keyword fallback** —
which is why each prompt is asserted to reach the lane it declares **through the fallback too**.
Four of the seven prompts are read out of the corpus they were written against rather than
restated: the **rehearsed hit** and the **honest miss** from `content/sop/corpus.toml`, the boundary
probe from the **Guardrail corpus**' measured `POSITIVE_PROBES`, and the shift-swap question from
the same corpus' `NEGATIVE_CONTROLS` — the one it is measured *not* to refuse.

**Follow-on task** — a **Quick Task** that another Quick Task leads to, named by `StartingTask.follow_on`
and rendered *inside* the conversation it follows rather than on the home grid (#61, ADR-024). One
user today: the troubleshooting fault names the escalation. It exists because beats 3 and 4 are one
conversation — an associate trying things and then asking for help with the same fault — and the
only route back to the home screen is **New chat**, which starts a new one by construction, so the
**Simulated ticket** read an empty **Troubleshooting record** and said `not reported`. Tapping it
submits the authored prompt and the authored **Lane** with *the current plan's* `session_id`, which
needs no backend change: a Lane is a property of the request, so the escalation keeps its
**Deliberate lane** and its own approval gate while sharing the session.

**A task named as a follow-on is not a home card** — the roster still declares six and the grid
renders five. The rule is derived from the pointer rather than being a second flag, and it is what
stops the cold tap that produces the empty ticket, because *a Quick Task is a claim about what will
happen when somebody taps it* and that claim may not depend on where it was tapped. **The card is
ungated**: the gate is the agent's offer, driven by `escalation_due`, where the audience can watch
it fire — a second copy in the UI would ride a flag this subsystem writes best-effort and would
fail **closed**, mid-beat. It sits above the chat box and below the **Rehearsed reply** chips'
slot, not in the rail, which stacks *beneath* the conversation below the **Stacking breakpoint**.

The card is **unchanged** by **Resume** (#77, ADR-027) and is still the rehearsed path: it carries
authored wording and a declared **Lane** and needs no keyboard. Both now go through one seam,
`ChatPage.submitTurnIntoSession`, because everything around a continuation is what a second caller
quietly drops — the previous answer's provenance going dark, the **Progress narration**'s three
beats, the socket connected before the navigation (ADR-021), and the navigation itself.

_Avoid_: next task, chained task, escalation button

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

**The message box is one control with two acts.** It answers a pending **Clarification** against
that question's `request_id`, and outside one it **resumes**. It used to do only the first and offer
itself regardless — *"Type your message here…"* over a submit that defaulted a missing identifier to
`''` and posted anyway, a clarification answering nothing and the associate's message gone with
nothing on screen to say why (#68). Availability and the payload are one claim,
`turnModeFor` in `src/App/src/models/resume.ts`: `PlanChatBody` decides from it whether the box may
be used and what it invites, `ChatPage` decides from it where what was typed goes, and a box open
over a submit path that disagreed is #68 read from the other side. The two acts read differently
before either happens, because the placeholder is the only place the surface says which is about to
— *"Type your message here..."* against a question, *"Ask another question in this chat..."*
outside one. A question carrying **no identifier is not one this surface can answer**, so it is not
pending either — refused where the frame arrives, since the parser is total and the socket's
re-wrapping had that refusal throwing inside a listener and being logged there; it is no longer a
reason to close the box, only a reason for what is typed to be a new turn. **Answering one settles
it**, since a clarification left in the store outlives its answer and the surface goes on offering
to answer it — which is what the **Rehearsed reply** chips going hidden after a tap has always
meant, and what `troubleshooting.spec.ts` already asserted. The answer settles **the question it
answered**, by name: the backend releases the orchestration before it finishes persisting, so the
next question can reach the browser while the last answer is still in flight, and an answer that
settled whatever happened to be stored would close the box over a question the backend is waiting
on. The gate lives in `PlanChatBody` for the reason the chips own theirs, and the chips keep their
own — they answer a Clarification and only that.

**Resume continues the Chat's Session** ([ADR-027](docs/ADR/027-resume-continues-the-session.md),
#77). A turn typed into an open Chat carries **that Chat's** `session_id` rather than minting a new
one, which needs no backend change: the request notes the turn against the session it names, and
`troubleshooting.turn.turn_for` — the seam the MCP container's tools resolve a session through — then
reads the same partition the earlier turns wrote. It is the **recovery** path, for a presenter who
tapped **New chat** by mistake or came back to the list; the **Follow-on task** card remains the
**rehearsed** one, authored, lane-carrying and keyboard-free, and is unchanged.

**Resume carries only what was persisted** — the **Attempted steps**, the identity, the **Lane** and
the **Simulated ticket**. The transcript on screen is display-only and is never replayed into an
agent's context: the **Workflow cache** is process-local and keyed by *user*, so there is no
per-Chat agent thread to restore, and replaying the transcript would claim one. Both halves are said
in `docs/presenter-runbook.md`, because *"it remembers everything we said"* is a claim the next turn
can falsify in front of the customer.

It is **fail-closed** at both ends: a chat the surface cannot name a session for is not continued —
the box closes and says why — because minting a session here starts a *new* conversation under an
old heading and silently loses exactly the records resume exists to carry. A pending clarification
**wins** over a resumable session, since a turn typed while the orchestration waits on an answer
*is* that answer and starting a plan with it strands the turn that asked; and a clarification needs
no session, being posted against a `request_id` and a `plan_id`.

**A resumed turn is an ordinary turn, so it can end without a plan.** A question typed into a chat
reaches `process_request` exactly as one typed on the home screen does, so the **Identity boundary**
gate can refuse it and the **Mocked unlock** can answer it out of the associate's record — both
plan-less, neither a failed request. Until resume the chat surface had no way to produce either and
so had no surface for them; reporting them through *"Unable to create plan"* would make a governed
refusal look like a bug, which is the confusion [ADR-014](docs/ADR/014-deterministic-identity-boundary-gate.md) exists
to remove. `PolicyBlockNotice` is now one component both surfaces render, because a refusal styled
twice is two refusals. The chat surface's carries **no door**: signing in is the home screen's
rehearsed beat (#27), and a second one is a decision no ADR has taken. It carries the refusal's two
side effects, though, because they are claims about the conversation rather than about the surface:
the **Signed-in device** is forgotten, since a refusal *is* the gate saying nobody is signed in and a
header naming an associate it has just declined to serve says something untrue; and the refusal goes
on the **Token meter** as a measured zero, since a refused request that left no row is a refusal the
transparency panels cannot show happened.

**One continuation lock, not two.** The **Follow-on task** card and the box submit through the same
`submitTurnIntoSession`, and the lock is the seam's rather than either caller's — two locks let the
card and the box submit at once, and `process_request` **cancels** whatever orchestration that user
already had running before it schedules the next. Two turns into one Session is one turn cancelled,
and the cancelled one is the escalation the presenter just tapped.

That same cancellation is why **the box refuses while this chat is working**: a resumed turn does not
queue behind the running one, it replaces it. The gate is `showProcessingPlanSpinner` and
deliberately *not* `showApprovalButtons` — that flag is set from the plan's **stored**
`overall_status` on every load, so counting it would close the box on every reopened chat that never
finished, which is the chat #74 said is most worth resuming. A pending clarification is exempt:
there the spinner is up over a turn that cannot progress until the box is used. The two closures say
different sentences, because "still working" is a wait and "cannot be continued" is a state.

`submittingChatDisableInput` means what it says since #77, and it did not before: it began `true` and
was released only when a clarification arrived, which made it a second, quieter answer to *may the
box be used at all* — one that agreed with the first only by coincidence. It now defaults to `false`
and is released on **every** terminal status rather than on the branch that remembered, which is
#69's lesson applied to the lock; a final error used to *lock* it, leaving the failed chat — the one
most worth resuming — the one chat that could not be.

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

**Ticket on approval** — the authored `StartingTask.ticket_on_approval` flag (#62), read off the
running team's configuration rather than off the browser's request, which may name a task but may
not decide what its approval does. It settles two things at once and is read **once** and carried:
the approval **drafts** from the session's record before it submits, so the ticket does not depend
on a model electing to call `draft_service_ticket` — a live approved turn that ran to completion did
not — and the turn asks the associate **nothing**, because nothing they could answer changes what
the ticket says. Deriving it twice would let the two halves disagree: a turn that raises the ticket
deterministically and interviews the associate about it anyway.

Recorded in [docs/escalation-ticket.md](docs/escalation-ticket.md).

**Attempted steps** — what the associate has already tried, persisted explicitly to the Cosmos
memory container. Framework checkpoint state is in-memory and must not be relied on for this.

**Presenter runbook** — the walkthrough written for the person who will drive it: eight taps, what
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

**Progress narration** — what the surface says between a chat being submitted and its answer
arriving. It enters a phase only when a **real signal reports it**, and where nothing has arrived
it holds the last true statement rather than inventing the next one. The Sent phase says
*"Starting chat…"*, from the `createPlan` POST in flight. The remaining observable events are the
response's `lane`, read from the same field `LaneBadge` reads; `connection_status`, which is
plumbing and says nothing; `agent_message_streaming`, which carries the **executor name** and so
names *which* specialist is responding; and `plan_approval_request` or `final_result_message`.
There is deliberately **no "agents selected" phase**: no such event exists, because
`init_orchestration` and `AgentFactory.get_agents` build the workflow in-process and emit nothing.

It replaces four authored strings — *"Initializing AI agents…"*, *"Generating plan scaffolds…"*,
*"Optimizing task steps…"*, *"Applying finishing touches…"* — that `ChatPage` rotated on a 3000ms
timer keyed to a GET-in-flight boolean. Nothing scaffolded and nothing optimised; they named four
stages the system does not have, three inches from a **Token meter** whose whole discipline is
**Not reported vs measured**. It also replaces six components each carrying their own copy, which
had already drifted into telling the story backwards — *"Plan created — Fast lane"* on the home
surface, then *"Loading plan data…"* on the chat surface. `models/progressNarration.ts` owns the
strings, on the **Store surface**'s pattern — and a test reads the source tree, because six
components each holding a copy is a fault about the repository that no render can see —
while `store/slices/progressSlice.ts` holds the phase **across the navigation**, because across two
components "only advances" is a coincidence and not a property. The slice carries the **plan the
narration is about** as well, so opening an earlier task from the left panel mid-request does not
leave *"Shift Tasks Agent is responding…"* over a conversation that finished last week.

**And it stops.** Reaching Done removes the in-flight indicator from the screen, on the **Fast
lane** — which has no `plan_approval_request` at all — as well as the Deliberate one and the error
path. Stated separately because every other rule here governs what the surface *says* and none of
them governs it ever *finishing*: #69 was a narration that claimed only what a signal reported and
then ran for the rest of the conversation. Its guard drives raw wire text through
`WebSocketService` into the real `PlanChat` and asserts no `progressbar` remains — by role, not by
copy, so that rewriting these strings did not delete it. It is pointed at the phase now, and
`waitingForPlan` is gone: nothing on the surface reads a second boolean about whether a request is
in flight. **And the slice has to actually be in the store**: `progressSlice` reaches
`agentIconUtils` to name an executor, and that module imported the `@/store` barrel, so the running
store dropped the `progress` key while all 407 tests — each building its own store — stayed green.
`store/store.test.ts` imports a slice before the store and asserts the store carries every reducer
it claims. See
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

Since #79 the **home surface**'s rail states it too, before a question is typed — the same panel,
given only the roster, because there is no conversation there to have one, and rendered only once
there *is* a roster to state, on #78's rule. That is the surface where
the distinction is hardest to get away with, since the gate's refusal happens on it and the meter's
measured `0` is two panels below the count. Availability is deliberately **not** a phase of the
**Progress narration**: the phases are each an observed event running from a question being sent to
its answer arriving, and availability is a standing fact that is true before any of them. The note
under the count says *"which of them take part"* rather than *"which of them take this question"*,
because before anything is typed there is no *this question*.
_Avoid_: agents assigned, agents identified, agents selected

**Settled status** — `completed`, `failed` or `canceled`: the three states in which a **Chat** may
be deleted. The rule is **total and fail-closed** — any other answer, including none, means running.
It is held twice, in `src/backend/chat/deletion.py` and `src/App/src/models/chatDeletion.ts`, and
the two copies are kept in agreement by `src/tests/ci/test_chat_deletion_contract.py`. `canceled`
was unreachable until [ADR-031](docs/ADR/031-leaving-a-chat-ends-its-turn.md) gave **Leaving a
Chat** the write, which is why the way out of `in_progress` is to end the turn and never to loosen
this rule.
_Avoid_: terminal state, final status, deletable status

**Chat deletion** — an irreversible removal of a **Chat**. It deletes every document in that
session partition — its plans, transcript, `m_plan`, **Troubleshooting record**, **Simulated
ticket**, and **Session state** — scoped to its `user_id`, so one associate cannot delete another's
chat. `delete_plan_by_plan_id` remains the human-feedback rejection path's single-purpose
primitive; it neither owns nor authorizes Chat deletion. The accepted cost is that a rehearsal can
destroy the diagnosis trail that #47, #54, #61, and #62 used.

Built in #75. The rule of *which* chats may go is pure and lives in `src/backend/chat/deletion.py`
— a chat is deletable once its latest plan is `completed`, `failed` or `canceled`, and **any other
answer, including none, means running**, because offering a delete the route will refuse is the
surface claiming an action it does not have. `CosmosDBClient.delete_chat` reads that status **raw**
rather than through `Plan` — the shared `query_items` helper drops documents it cannot validate and
turns a Cosmos failure into an empty list, either of which would defeat the rule above — proves
ownership twice (a plan of this user's, and no other user's record anywhere in the partition), and
counts what actually went: `DELETE /api/v4/chats/{session_id}` answers **404** for no such chat or
somebody else's, **409** for a running one, **500** when the sweep could not take everything, and
**200** with the number of documents removed — never success unconditionally. The row's half is
`src/App/src/models/chatDeletion.ts`, and the two copies of the settled-status rule are held
together by `src/tests/ci/test_chat_deletion_contract.py`. The refusal is said in one sentence,
shared: the menu's reason and the 409's detail are the same string, and a refused delete is
reported in the confirmation dialog itself rather than through a Fluent `Toaster` this application
has never mounted.

The list-level control is #76 — `DELETE /api/v4/chats`, one action clearing the panel between
rehearsal runs. It cannot answer in a status code, because its chats do not all end the same way
and a code carrying the worst of them would throw away which rows the panel may drop; it answers
**200** with the accounting in the body, and every chat that goes goes through `delete_chat` on
exactly the terms above. Three things make that honest, and all three were found by review of the
first version:

- **The sweep is the list that was confirmed.** The panel lists chats by **team**
  (`get_all_plans_by_team_id`) and the confirmation states that list's count, so
  `delete_all_chats` is scoped by `team_id` as well as `user_id` and the route takes the team from
  `get_current_team` rather than from the request. No current team is the empty list `GET /plans`
  answers with, and the store is not reached at all.
- **A running Chat is kept at the moment the documents go**, not merely when the status was read.
  The status is read again after the partition is enumerated — a latest plan the enumeration never
  saw is a turn that started behind it — the latest plan is deleted **first** and conditionally on
  its `_etag`, so a plan that moved refuses the delete while the chat is still whole, and the
  partition is counted afterwards: a record written behind the sweep makes the chat `incomplete`.
- **An incomplete sweep is never reported as a cleared list.** The panel reads `chats_failed`, not
  just `deleted_sessions`; the confirmation stays open and says how many chats are still in the
  record, while the rows that did go are pruned and a chat kept running is still named. "Could not
  take everything" and "would not take a live chat" are different sentences and both are said.
  Nor is a chat list the route could not *read* reported as one it cleared: `get_current_team` goes
  through `query_items`, so an outage and a team-less associate both arrive as `None`, and the
  route answers **500** rather than an empty sweep.

The sweep is still not atomic, and two residues are recorded rather than claimed away: a document
written after the partition's final count cannot be told apart from one written after the delete
returned, and a sweep that takes the latest plan and then fails leaves a partition the chat list
cannot show, because the list is built from plans. Both want a deletion fence every session writer
honours; neither is closeable inside `delete_chat`, and the surface says nothing that depends on
either being closed.
_Avoid_: hidden completed tasks, delete plan, clear history, archive

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
they were built from. Measured by `check-deployed-build.sh` (#48,
[ADR-018](docs/ADR/018-deployed-build-provenance-check.md)), which reads the commit off every
Container App's image tag and asks `git` how far it is from `HEAD`, reporting the distance and the
subject line of everything not deployed. The two older checks each miss it in their own way.
`check-deployed-environment.sh` asserts the image is not the **Placeholder image** and that it came
from the expected registry, and never that it is *current*; every declared loop runs against fakes
and stubs, so all of them stay green while the deployment is arbitrarily old.
`check-deployed-surface.sh` (#44) catches the drift that has already changed something visible — the
served page title, the Quick Tasks, the SOP agent's token endpoint, a grounded answer — which is a
symptom rather than a measurement: it cannot tell a deployment one commit behind from a current one.
The measurement is three-state rather than two: an image whose tag names no commit is **unknown**,
never a pass, because rounding it to a pass rebuilds the hole. It is also the **Demo validator**'s
first assertion, so a drifted deployment stops the run rather than producing seven beats about
another commit. See [docs/preflight/deployed-build.md](docs/preflight/deployed-build.md).
_Avoid_: stale deployment, drift

## Confirmed findings

### One session renders as two rows (confirmed 2026-08-14, fixed 2026-08-14, issue #71)

The left panel built one row per **Plan** while keying and selecting rows by `session_id`. When the
troubleshooting turn and its escalation share a session, React received duplicate keys, either row
opened the first plan, and the troubleshooting row stayed highlighted while the escalation was open.
The panel was therefore inconsistent with **Chat**: one session must be one row, named by its first
plan and opening its latest plan.

Fixed by grouping in `TaskService.transformPlansToChats`, which now emits one row per `session_id`
— named by the **first** plan's `initial_goal`, carrying the **latest** plan's id as the row's own
`planId`, and taking its status and date from that latest plan. First and latest are read from
`timestamp`, because the order a history endpoint returns plans in says nothing about which turn
opened a conversation. `ChatPanelLeft` navigates to the row's `planId` rather than searching the
plans for one matching the row's session: that search took the first match, and taking the first
match is what made the escalation unreachable.

### The escalation drafts nothing and interviews the associate instead (confirmed 2026-08-14, issue #62)

An approved escalation turn ran to completion against `rg-macae-flw-v1` — `final_result_message` on
the wire, 2810 characters of answer — and `GET /api/v4/escalation/ticket` answered
`{"drafted": false}`. The `EscalationAgent` never called `draft_service_ticket`. There was no draft,
so the submission seam #22 built had nothing to submit and had **never once fired live**, and the
**Simulated ticket** the demonstration promises existed only in the prose the model wrote.
[docs/escalation-ticket.md](docs/escalation-ticket.md) had named the risk out loud — *"that a live
`gpt-5.4` turn calls `draft_service_ticket` before presenting a ticket is **instructed**, not
measured"* — and measuring it is what found it.

What the same run showed about *why* is the more general half. After the approval the plan stopped
twice in one pause — a `list_attempted_steps` tool approval rendered to the associate as *"The agent
needs clarification."*, and a `request_user_clarification` asking what was failing — and then kept
improvising diagnostics until the turn ended in troubleshooting advice. The plan's step made the
drafting conditional on a judgement (*"if the fault cannot be resolved on shift"*) the model never
reached.

Both halves are the same repeated lesson at two seams: **anything the demonstration promises, a
model may decline to do.** The draft is taken at the approval seam from the session's record, and
the questions are bounded at zero there too. The placeholder question was the sharper defect of the
two, because it was not confined to the escalation: every approval-gated tool call became a
**Clarification**, so a **Rehearsed reply** could be spent on a call that would not read it and the
substituted answer was written into the record the ticket's attempted steps are filled from.

Still unproven live: `e2e/specs/escalation.spec.ts` asserts the beat through a browser and needs a
deployment, `az login` and real Copilot Credits, so it is run deliberately and not by any workflow.

### One extra socket darkens the Grounding panel (confirmed 2026-08-14, issue #54)

`_push_source_used` — the frame the demonstration's centrepiece panel renders — resolved its
recipient with `sole_user()`, *the* connected user when there is exactly one. With a **second**
socket registered, the push is dropped and the panel stays dark on a turn that retrieved and cited
`SOP-102`.

Measured with a positive control by the [Routing probe](docs/routing-probe.md): one Fast-lane turn
taken with a single idle bystander socket open beside it graded `no-tool-call` with an answer that
opened *"Here's the Store 223 closing procedure from **SOP-102 Store Closing Procedure**"*. The
retrieval worked; only the provenance was lost.

The second socket does not have to be another associate. A presenter's other tab, a colleague's
screen, or a reconnect the backend has not yet noticed closing is enough — and the failure is
indistinguishable, on the screen and in the browser ledger, from the orchestrator never having
called the SOP tool. Issue #54's coarser variant, *"No tool call, no `source_used`, an honestly
empty panel"*, may partly have been this rather than the routing.

`_panel_recipient()` now asks `sole_turn()` first — the one user with a request **in flight**, which
the troubleshooting tools were already asking one module away — and falls back to `sole_user()`.
Both refuse to guess between two, so the recipient is still resolved server-side and is still never
a UUID a model copied. A connection is not a question.

The general lesson is the one this repository keeps re-buying: **an ambient singleton is a
correlation ID with no error case.** Any bridge that resolves *who* by counting what is connected
works perfectly until something else connects, and then fails silently, on stage.

### The two hardest beats have never been asserted on `main`, and #50 is closed (confirmed 2026-08-14, issue #61; corrected 2026-08-14, issue #67)

`e2e/specs/escalation.spec.ts` and `e2e/specs/troubleshooting.spec.ts` **had never existed on
`main`.** Their three commits — `834c82bf`, `038f5e6c` and `b095186e` — lived only on
`git-loopy/…/integrate/issue-50`, which `git merge-base --is-ancestor` confirmed was not an ancestor
of `main`. The branch was 7 ahead and **21 behind**, and `e2e/` had moved on both sides:
`deployedBuild.ts` and `evidence.ts` existed on `main` and not on the branch, `backend.ts` and
`wire.ts` the reverse.

Issue #50 is **closed**. Its specs ran live against `rg-macae-flw-v1`, found two real defects and
filed them — #61, the escalation that cannot reach the attempted steps, and #62, the ticket that is
never drafted at all. Both issues cite *"the Demo validator's escalation beat (#50)"* as the thing
that found them. Neither the beat nor the spec was on `main`. So the **Demo validator** on `main`
covered exactly one beat, the cross-platform hop, and the two hardest ones — the pair #50 itself
called *"the demonstration's strongest single claim"* — were asserted nowhere.

This was invisible in the way that matters here: every **Feedback loop** was green, `main` deploys on
every commit (ADR-020), and the deploy gate asks a procedure question, which is beat 1. Nothing that
runs would notice the absence. It was found only by reading #61's fourth acceptance criterion —
*"`e2e/specs/escalation.spec.ts` loses its `not reported` branch"* — against the file tree, and
discovering there was no such file.

It is the same shape as the transparency-signal finding below and the deployment-drift one after it:
the check that would have caught it is not the one that was running. A closed issue is evidence that
work was *done*, never that it **landed**.

**Both specs are on `main`** now, rebased onto the current `e2e/` helpers and reached by
`bash scripts/e2e-tests.sh`, and the escalation beat is reached through the **Follow-on task** inside
the troubleshooting conversation rather than from a home-screen card. What closes the finding is not
the landing, though — it is that *the check that would have caught it now runs*.
`test_each_claimed_beat_has_a_spec_and_every_spec_is_reachable` reads the claimed beats **out of this
record** — every `*.spec.ts` this file, `AGENTS.md` or `docs/` names — and fails when one of them has
no spec file behind it. Run against the tree as it stood before the landing, it goes red naming both
files and this paragraph's own ancestor as the thing that claimed them. A roster of the four spec
names in the test would not have: it could only have been written once the files were on disk, which
is the shape of every check that arrives after the fault it would have caught. The other direction —
every landed spec is named somewhere in the record — is what stops a documentation edit quietly
emptying the claim.

### The centrepiece beat is intermittent, and only a browser saw it (confirmed 2026-08-13, issue #47)

Eight runs of the **Demo validator** against `rg-macae-flw-v1` on the same afternoon: six green, two
red. Both failures were the rehearsed hit — *"How do I close the store?"*, the question
`content/sop/corpus.toml` exists to guarantee an answer to — coming back as the **honest miss**.
The hop itself completed: the **Grounding panel** named Copilot Studio and Dataverse. What it also
said was *"Searched Dataverse and found no matching procedure."*

`check-deployed-surface.sh`'s check passed on every attempt across the same period, because it asks
`POST /api/v4/sop/ask` **the corpus's own words**. The orchestrator does not: it hands the SOP tool
whatever the model rephrased the question into, and some rephrasings miss. The check and the browser
are asking different questions of the same agent, and only one of them is asking the presenter's. It
is now named `direct-sop-answer` for that reason, and a green report names the rehearsal that proves
the beat rather than implying one.

There is a second, coarser variant: the orchestrator sometimes does not call the SOP tool at all —
the **Group Chat Manager** answers from context, or the **Shift Tasks Agent** answers and the
**Troubleshooting Agent** asks a clarification. No tool call, no `source_used`, an honestly empty
panel.

The validator keeps `retries: 0`. A retry converts an intermittently-working demonstration into a
green run, and the presenter finds out in the room instead. This is #54, it is the walkthrough
observation (#46) and the presenter runbook (#53)'s most important input, and it is the first thing
the browser suite found that no API-level check could have.

**Measured and closed 2026-08-14 (#54)** — see [docs/sop-rehearsal.md](docs/sop-rehearsal.md). Every
validator run now records what the orchestrator actually asked, and the ledger settled two things a
description could not. The rephrasings are **unbounded** — two runs produced two wordings never seen
before — so the alias list was replaced by a turn-scoped session marker that is
phrasing-independent. (It was one-shot until it was read carefully: spending the marker on a turn's
*first* SOP lookup let a second lookup in the same turn overwrite the Grounding panel with the raw
rephrasing. It now stands for the whole turn and is disarmed at the turn's end, held to that turn's
own token.) And the failure that survived was not retrieval at all: a run whose panel named
Copilot Studio, reported Dataverse and cited SOP-102 was **red**, because the visible turn was the
Troubleshooting Agent asking *"What is stopping Store 223 from closing right now?"* while the answer
sat cited behind it. The cause is the inherited `MANDATORY AGENTS` clause forcing all three
specialists into a plan for a one-lookup question; the store team now opts out with
`require_all_agents: false`, and mandatory inclusion stays the default for every team that predates
the flag.

The proof itself then had to be made honest about *what* it proved. A rehearsal's ledger rows carried
the commit the **harness** ran from and nothing about the deployed build, so a run that got past the
build gate with `E2E_SKIP_BUILD_CHECK` — which the gate's own failure message offers, rightly, for a
presenter mid-demonstration — was indistinguishable from a verified one, and ten of them printed *the
beat is proved* about a build nobody could name. The gate now publishes what it verified, every row
records `deployedBuild` and `buildVerified`, and a streak that skipped the gate, ran against a local
surface, or spanned a redeploy is reported as no proof at all.

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
