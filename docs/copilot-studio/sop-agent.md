# The Copilot Studio SOP agent

**Verdict: the agent exists, is published with no authentication, and answers procedure questions
over Direct Line in numbered steps citing a named SOP document.** Authored, published and proved
2026-08-13 (issue #17). Re-proved 2026-08-14 (issue #45) against the **Circle K**-rebranded corpus,
with a ninth check that reads the banner back out of the live index.

Re-check with `scripts/copilot_studio/check-sop-agent.sh` — a bare run opens a fresh Direct Line
conversation and asks the rehearsed questions, and exits non-zero if any answer stops holding.

| Flag | What it does |
| --- | --- |
| *(none)* | Reads the agent and probes it over Direct Line. |
| `--provision` | Creates or converges the agent, its three authored components and the ten SOP documents. Idempotent by schema name, and by document **content** — a rewritten document is re-uploaded even though its filename never changed. |
| `--publish` | Publishes and **waits**. `PvaPublish` returns before the publish has finished. |
| `--probe` | Explicit form of what a bare run already does. |
| `--export <dir>` | Writes the solution export — the only backup a Default environment can have. |
| `--environment <id>` | Works against the identifier shown in the Copilot Studio URL rather than the tenant's Default one. |

The agent: **Store SOP Assistant** (`cr48b_StoreSopAssistant`), botid
`c846cba0-e696-f111-8076-0022482abf62`, in the Default environment
`Default-0f87abfb-0840-4199-96b7-1882c01a998b` (`https://org5dadb450.crm.dynamics.com/`), in the
unmanaged solution `Cr688e5`.

## Why the agent is authored through the Dataverse Web API rather than `pac`

`pac` CLI 1.49.4 is installed and carries `pac copilot create` and `pac copilot publish`, so the
obvious route is the supported one. It is not usable here: **`pac auth create` requires an
interactive sign-in or a service principal**, and this build runs unattended against a user
identity that already holds a token. The device-code flow cannot be answered by a loop, and
creating a service principal to author one demo agent adds a credential to a tenant whose data
policy is itself a recorded precondition.

So the agent is authored the way every preflight check in this repository already reaches the
tenant: the **Dataverse Web API with an `az` access token**. A Copilot Studio agent *is* Dataverse
data — a `bot` row and its `botcomponent` children — so this is not a way around the product, it is
the product's own storage. The consequence worth stating is that the repository, not the portal, is
the source of truth for the agent's behaviour, and the `authored-here` check below is what keeps it
that way.

## What the agent is made of

Thirteen components, all of them written in `scripts/copilot_studio/sop_agent.py`:

| Component | Type | What it is |
| --- | --- | --- |
| `…gpt.default` | 15 (Custom GPT) | The instructions: answer in numbered steps, name the source, never invent a procedure. |
| `…topic.ConversationStart` | 9 (Topic V2) | The greeting, fired by an explicit `startConversation` event. |
| `…topic.Fallback` | 9 (Topic V2) | The honest miss, verbatim. |
| `…file.sop101` … `…file.sop110` | 14 (Bot File Attachment) | The ten SOP documents from `content/sop/docx/`. |

Nothing else. A portal-created agent starts from a template that copies **thirteen system topics**
(Greeting, Escalate, Signin, Search/Conversational boosting, OnError, StartOver, Goodbye, …), and
the first build of this agent copied them from an existing portal agent to be safe. They were then
deleted and the agent re-published and re-probed: **it answers identically without them.** Under
generative orchestration (`GenerativeAIRecognizer` plus `GenerativeActionsEnabled`) the uploaded
documents are searched directly; the Conversational-boosting topic is not on that path. That is
worth knowing because it is the difference between an agent whose every word this repository can
show you the source of and one carrying eleven behaviours nobody here wrote.

The `authored-here` check is the guard on that. It fails, naming each component, if the agent
carries anything this repository did not author — which is what a portal edit looks like from
outside. Its remedy is deliberately **not** "re-run `--provision`": provisioning creates and
converges, it never deletes, so the operator has a decision to make (author it here, or remove it
there) and pointing them at a no-op would waste the run.

### The configuration that makes the honest miss possible

```json
{"settings": {"GenerativeActionsEnabled": true},
 "aISettings": {"useModelKnowledge": false, "isSemanticSearchEnabled": true},
 "recognizer": {"$kind": "GenerativeAIRecognizer"}}
```

**`useModelKnowledge: false` is the honest miss's off switch.** With it on, the out-of-corpus
question ("how do I run the car wash?") is answered fluently and plausibly from the model's own
knowledge, and the rehearsed beat that demonstrates a grounded agent's limits instead demonstrates
the opposite. The Fallback topic supplies the wording; this flag is what makes the Fallback topic
the thing that runs.

## Findings

| # | Finding | Evidence |
| --- | --- | --- |
| 1 | Creating a `bot` row **auto-provisions**. `PvaProvision` exists but is not needed: `provisioningStatus` walks Provisioning → ContentReady → Provisioned in about 40 seconds, and a component cannot be attached before it reaches Provisioned. | `POST /api/data/v9.2/bots`, then polling `synchronizationstatus` |
| 2 | An uploaded document is **exactly one `botcomponent` of type 14**, with no separate knowledge-source row. Type 16 (Knowledge Source) is for website/SharePoint-style sources. | Live creation; corroborated by Microsoft's own solution-export fixtures |
| 3 | Bytes go up as a second call: `PATCH botcomponents(<id>)/filedata` with `Content-Type: application/octet-stream` and an `x-ms-file-name` header. | Ten uploads, all ten searchable |
| 4 | `authenticationmode` **1** is None. The platform sets `accesscontrolpolicy` to 2 on create; PATCHing it back to **0** (Any) sticks. | The bot row after create, and after PATCH |
| 5 | The bound actions live on `bots(<id>)`: `PvaPublish`, `PvaPublishStatus`, `PvaGetDirectLineEndpoint`, `PvaProvision`, `PvaCreateBotComponents`. | `sdkmessages` and the `$metadata` document |
| 6 | The agent answers a procedure question in **15 numbered steps** citing `SOP-102 Store Closing Procedure.docx`, greets on `startConversation`, and refuses the out-of-corpus question with the authored sentence. | Live Direct Line conversations, 2026-08-13 |
| 7 | The solution export is now **48 KB / 31 entries**, carrying `bots/…/configuration.json` and every `botcomponent` including the ten `.docx` files. | `POST /api/data/v9.2/ExportSolution` |
| 8 | **A provision that decides by filename uploads nothing when a document is rewritten.** The Circle K rebrand ([ADR-019](../ADR/019-rebrand-the-sop-corpus-to-circle-k.md)) changed all ten bodies and renamed none of them — the filename is the citation the associate reads — and the provision skipped every one while reporting the corpus present. `provision()` now reads the attached bytes back (`GET botcomponents(<id>)/filedata/$value`) and uploads on content. Dataverse returns the uploaded bytes verbatim, so a second run uploads nothing. | The rebrand upload, 2026-08-14: ten skips before the fix, ten uploads after, zero on the re-run |
| 9 | **Eight of the nine checks pass against a stale index.** After the rebrand was published, a probe asking the closing procedure's owner answered `"Owner: Brightpath Convenience - Northgate District Operations"` while the corpus, authored, published and numbered-steps checks were all green. Only reading a changed line back out of the index distinguishes the two. | The `corpus-content-current` check's first live run, 2026-08-14 |

## Publish propagation, measured

Publishes took **17s, 43s, 85s, 11.6s and 48.5s** — a spread wide enough that a fixed sleep is not a
substitute for polling, which is why `publish()` waits on `publishedon` changing and then reads
`lastFinishedPublishOperation.status`.

The behaviour that matters more for a rehearsal is what a publish reaches. Measured with a marked
wording change:

- A **new** conversation, opened after the publish finished, gets the new content immediately.
- A conversation **already open** across the publish keeps the **old** content, indefinitely.

So the rule for the demo is: **open a fresh conversation after every publish**, and stop publishing
before the rehearsal rather than during it. A change made "to be safe" ten minutes before a demo and
tested in the window that is already open tests nothing.

## The citation shape, for the orchestrator (#18)

Citations arrive structurally, in the activity's `entities`, exactly as
[ADR-011](../ADR/011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md) requires — and
**there is no `url` key**, which is that decision's central prediction confirmed:

```json
{"type": "https://schema.org/Message",
 "citation": [{"@type": "Claim", "@id": "turn13search0", "position": 1,
               "appearance": {"@type": "DigitalDocument",
                              "name": "SOP-102 Store Closing Procedure.docx",
                              "abstract": "SOP-102 Store Closing Procedure.docx",
                              "text": "<h1>Store Closing Procedure</h1> Document ID: SOP-102 …"}}]}
```

One nuance corrects the expectation ADR-011 was written with. It says to render "name plus
snippet", reading **`abstract`** as the snippet. Live, **`abstract` is the filename** — identical to
`name` — and the snippet-shaped field is **`text`**, which carries the *whole* document as HTML
(3311 characters for SOP-102). The Grounding panel (R6) must therefore truncate `text` itself, or
show the document name alone; rendering `abstract` gives the filename twice, and rendering `text`
raw drops an entire SOP into the panel.

The markdown reference-style form in the activity text (`[1]: cite:1 "Citation-1"`) is the parallel
representation ADR-011 warns against parsing: `cite:1` is not a URL and resolves to nothing.

## Traps that cost time here

- **A Dataverse create answers `204 No Content`.** Without `Prefer: return=representation` the new
  id is only in the `OData-EntityId` header. Every create here asks for the representation.
- **PATCH by alternate key does not work for bot components.**
  `botcomponents(schemaname='…')` is a 400; the GUID has to be resolved first.
- **The publisher prefix is not yours to choose.** `Cr688e5` carries prefix `cr48b`, so the agent is
  `cr48b_StoreSopAssistant`. A schema name with a different prefix is rejected on create.
- **The platform writes back to `configuration` after a create**, setting
  `gPTSettings.defaultSchemaName` and sometimes injecting `aISettings.model.modelNameHint`. A
  convergence run that compared the whole document to what it authored would report drift forever;
  the check compares the fields it owns.
- **A `botcomponent` PATCH is not a publish.** Direct Line serves published content, and an agent
  holding the whole corpus but never published answers nothing at all — which reads exactly like a
  grounding failure.

## Prerequisites this depends on, and what it proves in turn

Dataverse search must be on and its index synced before an uploaded document is searchable at all —
[the search preflight record](../preflight/dataverse-search.md), where per-document indexing was
measured at **36–218 seconds** on a warm index. That is a rehearsal hazard rather than a defect: a
document uploaded mid-rehearsal is not immediately answerable, so the corpus must be uploaded and
published well ahead.

Verified here that Copilot Studio does offer documents-based knowledge with **No authentication**
and does retrieve from it anonymously — the question
[ADR-012](../ADR/012-grounding-option-a-dataverse-documents-only.md) turned on, and which the search
preflight explicitly left to this ticket.

## Scope

Verified: the agent exists with no authentication, the whole corpus is uploaded, only components
authored here are present, a publish succeeded, and a live anonymous Direct Line conversation
greets, answers in numbered steps with a named source, refuses the out-of-corpus question, and
reads the corpus' **Circle K** banner back out of a cited document.
**Not** verified here: calling the agent as a tool from the Foundry orchestrator (#18), the
Grounding panel's rendering of these citations (R6), or the agent's behaviour under concurrent
conversations.
