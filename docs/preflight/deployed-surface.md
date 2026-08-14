# Check: the deployed surface is the demonstration

**Verdict: `macae-flw-v1` serves the Circle K Frontline Store Assistant at the commit this
repository is on, and a procedure question is answered from Dataverse through Copilot Studio with
a citation.** Observed 2026-08-13 (issue #44), in `rg-macae-flw-v1`, subscription
`3523b0e6-bb53-4e87-8340-25c416e26093`, images built from `23d97b3dda59`. Re-observed 2026-08-13
(issue #47) after the frontend and backend were rolled onto `47-transparency-wire`, which carries
the WebSocket envelope fix at both ends and nothing else; the MCP app is untouched and still on
`23d97b3dda59`.

That tag is not commit-shaped, which is a knowing exception to the rule the *Scope* section states.
The change it carries is one branch of `WebSocketService.handleMessage` and one call site in
`orchestration_manager`, it had to be proved on the deployed surface before the commit that
describes it could honestly claim it worked, and amending that commit would have changed the very
sha the tag was meant to name. #48 replaces the whole scheme with a stamp inside the image, at which
point the argument goes away.

The images were built from that commit's tree; everything committed since is documentation and the
check tooling below, none of which is inside an image's build context (`src/backend`,
`src/mcp_server`, `src/App`). The tag is a claim about what was built, not a stamp the image
carries — see *Scope*.

Re-observed 2026-08-14 (issue #53). The running frontend was still **pre-#55**: its Quick Task card
filled the question box and waited for send, while the Demo validator taps once and expects a plan,
so the walkthrough's opening beat timed out on a card it had found and tapped. It was rolled onto
`macaefrontend:5758aa1c`, and the beat passed.

**Two integration branches were rolling this deployment minutes apart**, which is the fact worth
carrying forward. #50 rolled the backend to `macaebackend:834c82bf2db1` and the frontend to its own
build; #53 rolled the frontend again; #50 rolled it back to `macaefrontend:038f5e6c8927`. Beat 1
timed out once on a backend that had just been replaced under it, and was green on a re-run. Nothing
serialises this — the resource group is shared, `az containerapp update` is last-writer-wins, and a
red validator run is as likely to mean *somebody else is deploying* as it is to mean the beat is
broken. The MCP app was untouched throughout, on `23d97b3dda59`.

The **selector** consequence is recorded in [../demo-validator.md](../demo-validator.md#selectors):
a locator that depends on an attribute added the same morning cannot be told apart from a locator
that is simply pointed at an older image, so the Quick Task tap is aimed at the region's layout
class instead — which every one of those three images carries.

Re-check with `scripts/preflight/check-deployed-surface.sh` — it exits non-zero the moment any of
the facts below stops being true.

This is the record's other half.
[deployed-environment.md](deployed-environment.md) proves the **infrastructure**: the right
regions, the whole model roster answering, three application hosts on one replica each, running
images from our own registry. All thirteen of its checks were green on 2026-08-13 while the
Container Apps were running images built **42 commits earlier** — before the rebrand (#25), the
transparency panels (#23, #24), the Quick Tasks (#26), the mocked sign-in (#27), the escalation
ticket (#22), the troubleshooting memory (#21), the lane router (#16), the identity boundary gate
(#14) and the Direct Line client (#18). What was deployed was substantially the stock accelerator,
and it said so in the page title.

An image's **provenance** is not its **currency**, and every declared feedback loop runs against
fakes, so nothing in this repository observed the deployment at all. This check is what observes
it: it reads the running surface the way the presenter will.

## What the check proves, and why each fact needed proving

| Check | Why it is not assumable |
| --- | --- |
| `store-surface` | Nothing sets the document title at run time, so the served `<title>` is whatever `src/App/index.html` said **in the image that is running**. That makes it the cheapest honest answer to "is this the build we think it is" available without a commit stamp, and it is the string that gave the drift away: `Multi-Agent - Custom Automation Engine` served while the repository read `Circle K Frontline Store Assistant`. A surface that served no title at all is a cold or failed revision, which fails for a different reason and is reported as one. |
| `quick-tasks` | The Quick Tasks live in **Cosmos**, not in the image — `post_deploy.sh` uploads the store pack and a re-provision does not re-seed it. So a deployment can be running the current build and still have no assistant on it, and the surface then reports that the assistant is not loaded. Each task's **declared lane** is checked too: a task that arrives without one falls to the keyword router, and the escalation beat runs without the approval gate that raises its ticket — which looks like a working demonstration right up to the ticket. The team the backend answered with is checked against the authored identifier, because an earlier pack left in Cosmos under a renumbered one carries tasks that satisfy every name while the surface, which recognises the authored identifier, shows none of them. |
| `mandatory-agents` | The store team is `is_default`, and `delete_team` **refuses to delete a default team**. The post-provision upload warns and uploads anyway, writing a second document with the same `team_id` under a new partition key — so every deploy since the pack was authored has left another one behind. Six were live when this row was added, and five of them predated `require_all_agents`, which the backend defaults to on. That flag is what decides whether the opening question may be answered by one agent or is put through all three store specialists, one of whose job is to ask what you already tried; with it on, the rehearsed beat comes back as a clarifying question. `get_team` now orders newest-first so the pack's value wins, and this row is what notices if that ever stops being true. It is a separate check from `quick-tasks` because every task can be present and correct while the beat still fails this way. |
| `direct-line-endpoint` | `COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT` had **never been set** on this deployment. The bicep plumbs it through unconditionally from a `main.parameters.json` substitution, so this was never an infrastructure gap; the value was simply missing, and unset the SOP tool answers with its fixed failure message. The check also rejects a value assembled from the default Direct Line hostname, which [ADR-011](../ADR/011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md) rules out — the token endpoint is whatever `PvaGetDirectLineEndpoint` returned for *this* environment's region, and a hand-built URL is a plausible-looking one that issues no token. |
| `direct-sop-answer` | The three above are all readable without asking the deployment a question, and all three were true of environments whose centrepiece beat could not have worked. One real procedure question goes through `/api/v4/sop/ask` — the exact path the MCP tool takes — and what is graded is the **provenance and the citations**, never the prose: a fluent answer is precisely what an ungrounded fallback produces. The citation must name a document out of `content/sop/docx`: `direct-line-endpoint` accepts any endpoint that is not the assembled hostname, so a second Dataverse-grounded agent in the same tenant would answer and cite *something*, and the filename is what ties the answer back to the corpus this repository uploaded. Probed by default. `--no-probe` does not quietly omit it: it reports the cross-platform hop as unproven and exits non-zero, because a run that asked nothing must not claim the SOP agent is reachable. It is named for what it asks rather than for what it establishes: it asks the corpus's own wording, straight at the backend, with **no orchestrator in front of it**, and the presenter's tap goes through one that rephrases. Under its old name, `grounded-answer`, it was green on every attempt across the afternoon the browser watched the same question fail twice in eight runs (#54) — a check reading as *the grounded answer works* while the grounded answer did not. |
| `direct-sop-answers-every-time` | The row above grades **one** reply, which answers *can it* and was the whole of this gate's evidence until the fault the walkthrough kept failing on was finally measured: about **6% per Direct Line conversation**, inside Copilot Studio, with no orchestrator anywhere near it (#54, `bf7792a7`). One asking of a 6% fault comes back clean nineteen times in twenty and ten askings about half the time — so a single-sample row was green whatever the beat was doing, and `deploy-main.yml` gates on it. `--samples N` asks N times in N fresh conversations and grades every one of them **by the same rule as the first**, because a repeat held to a laxer bar is a green row that means less than the row above it. **Sampling is not proof, and the green row says by how much**: it names the smallest per-conversation fault that many askings is likelier than not to catch — 50% at one asking, 12.9% at five, 5.6% at twelve — so nobody reads "N of N" as "it cannot miss". The deploy gate asks **twelve**, which is where an even chance sits for the fault actually measured; `src/tests/ci/test_deploy_workflow.py` derives that bar from the rate rather than pinning the number. What the words say matters too: a run in which nothing answered is reported as **broken** rather than intermittent — a state to fix rather than a rate to measure — and an asking the backend never answered at all is reported as the hop not happening, never as the honest miss. A single asking still passes, and says out loud that it is one sample. |

Observed 2026-08-13, all four checks then green, `'How do I close the store?'` answered from
Dataverse through Copilot Studio citing `SOP-102 Store Closing Procedure.docx` — **once**, which
is the sample size `direct-sop-answers-every-time` was later added to say out loud.

Re-observed 2026-08-14 (issue #54) with that row live: **12 of 12 askings** answered from the
corpus, each in a fresh Direct Line conversation, the whole check in 2m05s — which is what the
`--samples 12` on the deploy gate costs, against a step that already spends twenty minutes and a
provision.

The question is read from `content/sop/corpus.toml`'s `[rehearsed_hit]` rather than pinned here, for
the same reason the rest of the expectation is (below) — and section-scoped, because `question` is a
key under `[honest_miss]` too, and a probe that picked up *that* one would ask the deployment the
question the corpus deliberately cannot answer and report a working SOP agent as a broken one.

**A row of PASSes is not a working walkthrough, and the report now says so.** Every check here
asks the deployment something the presenter never asks, and the closest one asks it past the layer
that breaks. What the presenter asks is asked by the **Demo validator**, through a browser, and
proven repeatable by `scripts/sop-rehearsal.sh` — which is the last line of every green run.

## The expectation is read out of the repository

The assistant's name comes from `src/App/src/models/storeSurface.ts`, the team identifier and the
Quick Tasks from `content_packs/store_assistant/agent_teams/store_assistant.json`, and the SOP
filenames a citation may name from `content/sop/docx/` — not from constants in the check.
This is the [ADR-019](../ADR/019-rebrand-the-sop-corpus-to-circle-k.md) lesson applied one layer
out: a check carrying its own copy of the surface's strings passes a rebrand it never saw, which is
the exact failure mode being guarded against here.

## The order that shipped it

The registry is filled **before** provisioning, for the reason
[deployed-environment.md](deployed-environment.md#the-fix-fill-the-registry-first-then-provision)
records — the accelerator's documented order updates Container Apps that provisioning never
created, and the placeholder image stalls the whole `mcp → backend → frontend` chain.

```bash
# 1. The three images, built server-side straight into ACR, tagged with the commit.
sha="$(git rev-parse --short=12 HEAD)"
az acr build --registry crmacaeflwv1flrpd --image "macaemcp:$sha"      --image macaemcp:latest      --file src/mcp_server/Dockerfile src/mcp_server
az acr build --registry crmacaeflwv1flrpd --image "macaebackend:$sha"  --image macaebackend:latest  --file src/backend/Dockerfile   src/backend
az acr build --registry crmacaeflwv1flrpd --image "macaefrontend:$sha" --image macaefrontend:latest --file src/App/Dockerfile       src/App

# 2. The Direct Line token endpoint, read from the live agent rather than pinned.
python3 -c "import sys; sys.path.insert(0, 'scripts')
from copilot_studio import sop_agent as s
env = s.resolve_environment(None); bot = s.read_bot(env)
print(env.call(f\"bots({bot['botid']})/Microsoft.Dynamics.CRM.PvaGetDirectLineEndpoint\", 'POST', {})['Endpoint'])"

azd env set COPILOT_STUDIO_DIRECT_LINE_TOKEN_ENDPOINT '<what that printed>'
azd env set MACAE_USE_CASE none
azd env set AZURE_ENV_IMAGE_TAG "$sha"
azd provision

# 3. The store pack, and nothing else.
MACAE_USE_CASE=none bash infra/scripts/post-provision/post_deploy.sh
```

Three things about that sequence are load-bearing:

- **The image tag is the commit, not `latest`.** `azd provision` only produces a new revision where
  the template changed, so a re-pushed `latest` leaves the frontend and MCP apps serving the image
  they already cached — the backend would pick up the new setting and the other two would not, and
  the run would look successful. A commit-shaped tag changes all three templates and forces all
  three pulls. It is not a provenance stamp; the image carries no commit of its own. That is #48.
- **`MACAE_USE_CASE=none` is set before `post_deploy.sh` runs.** Unset, the script prompts, and an
  unattended run has nobody to answer it; answered wrongly, it restores the six stock content packs
  that #25 deliberately suppressed. The store pack itself is uploaded regardless of the selection,
  which is why `none` still leaves an assistant on the surface.
- **The endpoint is re-read, not remembered.** It is what `PvaGetDirectLineEndpoint` says today for
  this environment's region. See
  [../copilot-studio/direct-line-client.md](../copilot-studio/direct-line-client.md).

Which Copilot Studio agent the token endpoint points at is **not** proven here, only that the agent
it reaches answers out of this corpus. The agent's own identity, its authored components and its
published state are [../copilot-studio/sop-agent.md](../copilot-studio/sop-agent.md)'s to prove.

## Scope

Verified: the served page title, the six Quick Tasks and the lane each declares, the SOP agent's
token endpoint on the backend Container App, and one procedure question answered from Dataverse
through Copilot Studio citing a document this repository authored — asked as many times as
`--samples` said, each in a fresh Direct Line conversation, and every asking graded.

**Not** verified here: that the Container Apps are running the **current commit** — the tag says
so, and a tag is a claim rather than a stamp (#48); nor any of the seven beats end to end through a
browser (#47, #49, #50); nor the fourth specialist, which does not exist yet (#52). The roster this
deployment holds is three agents — `TroubleshootingAgent`, `ShiftTasksAgent`, `EscalationAgent`.
