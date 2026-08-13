# The store content pack and the Foundry agent roster

Issue #19. What #25 branded, this fills: until this pack is uploaded,
`selectStoreAssistant` finds nothing under
`00000000-0000-0000-0000-000000000223` and the surface truthfully reports that
*The Circle K Frontline Store Assistant is not loaded on this deployment.*

Everything the demonstration says is grounded in one of three places, and this
document records which.

## The pack

```
content_packs/store_assistant/
├── pack.json                         two blob indexes
├── agent_teams/store_assistant.json  the roster
└── datasets/
    ├── troubleshooting/   RB-201..RB-204  → store-troubleshooting-index
    └── operations/        STORE-223, TKT-001 → store-operations-index
```

The documents are authored **as the indexed artefact**. `index_datasets.py`
decodes anything that is not `.pdf` or `.docx` as UTF-8 and indexes it whole,
so the markdown *is* the document and there is no build step. This is
deliberately unlike the SOP corpus under `content/sop/`, which must be built to
`.docx` because Copilot Studio's file knowledge source will not take markdown.

## The roster

Three Foundry participants, plus the orchestrator, plus the Store SOP Assistant
reached as a tool rather than as a participant.

| Agent | `input_key` | Model | Grounding |
| --- | --- | --- | --- |
| `TroubleshootingAgent` | `troubleshooting` | `gpt-5.4` | `store-troubleshooting-kb`, `user_responses: true` |
| `ShiftTasksAgent` | `shift_tasks` | `gpt-5.4-mini` | `sop` toolbox — **no Foundry knowledge base** |
| `EscalationAgent` | `escalation` | `gpt-5.4` | `store-operations-kb` |
| the manager | — | `ORCHESTRATOR_MODEL_NAME`, `gpt-5.4-mini` | — |

### The shift-tasks agent owns the SOP tool and nothing else

This is the load-bearing decision. An agent holding both a Foundry knowledge
base and `search_store_procedures` chooses between them turn by turn, and the
branch it does not take is the cross-platform hop the whole demonstration rests
on — R6 exists to show an associate that *this one answer left Foundry*, and a
hop that happens on four runs out of five is not a claim anybody can make on
stage. So the agent that answers procedure questions has no procedure knowledge
of its own; the tool is its only source, and its system message says so in as
many words.

The same reasoning runs the other way for troubleshooting. Runbooks are the
store's own, they are not procedures, and they are indexed into their own
knowledge base rather than merged into anything — a shared source would make
"which platform answered this" unprovable at exactly the moment the panel
claims it.

### The models

`gpt-5.4` for the two agents that reason over retrieved material and have to
decide what *not* to say — a runbook branch to skip because the associate
already tried it, a ticket field with no answer anywhere. `gpt-5.4-mini` for
the agent whose job is to call a tool and quote what came back, and for the
orchestrator (ADR-003).

Both are in `SUPPORTED_MODELS`, which matters more than it looks — see below.

## The silent skip

`AgentFactory.get_agents` catches `UnsupportedModelError` and logs a warning:

```python
except UnsupportedModelError as e:
    logger.warning(...)
    continue
```

So an agent whose `deployment_name` is not in the `SUPPORTED_MODELS`
allowlist — or absent entirely — is dropped. The upload returned 200, the team
is in Cosmos, the surface shows the assistant, the walkthrough starts, and one
member of the cast simply never speaks. Nobody reads a container's warning
stream during a rehearsal.

There are two allowlists and they do not agree. `validate_team_models` at
upload time hard-bypasses `gpt-5.4-mini`, `gpt-5.4`, `gpt-5` and `o3` by name
and fails open on any exception; `create_agent_from_config` at run time reads
the `SUPPORTED_MODELS` environment variable. An upload can therefore pass while
the agent it uploaded will never be constructed.

`store_pack roster` is the check that closes it. It reads the team back out of
the deployment after upload and compares it to what was authored — every agent
present, every model the one it was given. `post_deploy.sh` and `.ps1` both run
it, and a mismatch sets `has_errors`.

```bash
PYTHONPATH=tools python -m store_pack roster \
  --backend-url "$BACKEND_URL" --user-principal-id "$USER_PRINCIPAL_ID"
```

The offline half needs no deployment at all:

```bash
PYTHONPATH=tools python -m store_pack verify
```

## The deploy path

The store pack is **not** one of the six stock content packs #25 suppressed, so
the use-case selection does not gate it. `none` means no *stock* pack; a
deployment that seeded nothing at all is the surface honestly reporting that
the assistant is not loaded, which is honest and unusable.

Two orderings are load-bearing:

- **Data before team configuration.** `deploy_content_pack` creates the two
  search indexes; `upload_all_team_configs` uploads a definition that names
  them. A knowledge base whose index does not exist does not fail — it returns
  nothing, and an agent grounded on nothing improvises, which is the one thing
  every system message here forbids.
- **The store pack last among the uploads.** `is_default: true` and the
  accelerator's own ordering both make the most recently uploaded default team
  the one a fresh deployment lands on.

`upload_all_team_configs` exists so that "does `none` still install the store
assistant?" is a question something can be *asked* rather than seven guards that
agree by inspection. `src/tests/ci/test_store_pack.py` sources the real script,
stubs `upload_team_config`, and reads the sequence back.

The two knowledge bases are appended to the seeding filter outside the use-case
map for the same reason. That map has no entry for `none`, so an agent's
grounding must not depend on which stock pack somebody chose.

## The honest miss, across two corpora

`content/sop/corpus.toml` declares `absent_terms` — car wash, wash bay, wash
tunnel — because the rehearsed out-of-corpus probe is a car-wash question and
the demonstration's honesty depends on nothing answering it. The runbooks are a
*different* corpus reached by a *different* tool, so the SOP corpus' own
verifier cannot see them. A car-wash runbook would answer the probe, the miss
would never happen, and every check would still be green.

`store_pack verify` and `test_store_pack.py` therefore assert those terms
appear in no pack document either.

## The content

Four runbooks, each branching, each naming what is usually already tried and
where to stop:

| Document | Equipment |
| --- | --- |
| RB-201 | Coffee brewer not brewing |
| RB-202 | Hot food case holding below temperature |
| RB-203 | Fuel dispenser not authorizing |
| RB-204 | Walk-in cooler running warm |

Plus the store profile (`STORE-223`: site, asset tags, contacts, service
windows) and the service-incident ticket template (`TKT-001`), which carries a
`steps_attempted` field — that field is why escalation happens *here* rather
than on a phone call, and it is what #22 consumes.

The content is fictional: **Brightpath Convenience, Store 223**, matching
`content/sop/corpus.toml`. The surface is branded Circle K; the documents are
not, for the same reason #25 drew an abstract storefront rather than reproducing
a real mark.

## The shift-task alerts

`src/backend/transparency/alert.py` holds seven rehearsed alerts, each naming a
real `SOP-NNN` from the corpus so that the presenter's chord lands on a beat
that leads straight into the cross-platform hop. They are rehearsed words, not
a live signal, which is why `SimulatedBadge` goes on them.

## Not verified

- Nothing here has run against a live deployment. The roster check is unit
  tested against synthetic responses; it has never read a real Cosmos team.
- Whether the KB MCP path actually surfaces these documents to
  `TroubleshootingAgent` is unverified — it is asserted that the indexes are
  created and the knowledge bases registered, not that retrieval returns.
- The PowerShell entry point is asserted by reading the file. There is no pwsh
  in CI.
- The two placeholder starting tasks are gone: #26 replaced them with the six
  Quick Tasks, one per beat of the walkthrough, recorded in
  [docs/quick-tasks.md](quick-tasks.md).
