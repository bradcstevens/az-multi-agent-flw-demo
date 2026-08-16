# Architecture decision records

The decisions that shape the **Circle K Frontline Store Assistant**. Three-digit `NNN-`
numbering, continued from the directory upstream already uses — see `CONTEXT.md` for the
glossary these ADRs speak in, and
[docs/superseded-requirements-corrections.md](../superseded-requirements-corrections.md) for
the factual corrections to the reference material this build started from.

Every ADR in this directory appears in the table below; a CI-tooling test
(`src/tests/ci/test_durable_record.py`) enforces that.

| ADR | Decision | Status |
| --- | --- | --- |
| [001](./001-retain-custom-json-declarative-config.md) | Retain custom JSON declarative configuration over the MAF declarative package | Accepted |
| [002](./002-foundry-iq-file-search-over-azure-ai-search.md) | Foundry IQ vector store (`FileSearchTool`) over Azure AI Search | **Superseded by 007** |
| [003](./003-reasoning-model-for-orchestrator-manager.md) | A reasoning model for the orchestrator manager | Accepted |
| [004](./004-fork-macae-at-pinned-upstream-commit.md) | Merge the MACAE baseline at the pinned commit `c5a7a4d`; toolchain minimums | Accepted — remote clause superseded by 006 |
| [005](./005-declare-feedback-loops-in-agents-md.md) | Declare the Feedback loops in `AGENTS.md`, backed by scripts in `scripts/` | Accepted |
| [006](./006-macae-is-a-one-way-baseline.md) | MACAE is a one-way baseline — no `upstream` remote, no upstream automation | Accepted |
| [007](./007-foundry-iq-knowledge-bases-require-azure-ai-search.md) | Foundry IQ Knowledge Bases keep Azure AI Search as a deployment dependency | Accepted — supersedes 002 |
| [008](./008-decouple-search-region-from-foundry-location.md) | Azure AI Search deploys to a region decoupled from the Foundry primary location | Accepted |
| [009](./009-eastus2-as-the-only-viable-primary-region.md) | East US 2 is the primary region; `swedencentral` and `eastus` are invalid | Accepted |
| [010](./010-keyless-by-default-over-mcaps-tag-exemption.md) | Keyless by default — do not apply the standard MCAPS local-auth tag exemption | Accepted |
| [011](./011-direct-line-over-a2a-for-the-copilot-studio-sop-agent.md) | Reach the Copilot Studio SOP agent over Direct Line, not A2A | Accepted |
| [012](./012-grounding-option-a-dataverse-documents-only.md) | Ground the SOP agent on Dataverse Documents only — Option B deleted, not deferred | Accepted |
| [013](./013-per-request-plan-review-over-orchestrator-bypass.md) | Vary Plan review per request instead of building an orchestrator bypass | Accepted |
| [014](./014-deterministic-identity-boundary-gate.md) | The identity boundary gate is deterministic code, not a prompt | Accepted |
| [015](./015-two-class-margin-for-the-identity-boundary-gate.md) | Score the identity boundary gate's similarity tier as a two-class margin | Accepted |
| [016](./016-typescript-playwright-for-the-demo-validator.md) | TypeScript `@playwright/test` for the Demo validator, against the Python loop convention | Accepted |
| [017](./017-workforce-agent-answers-process-never-record.md) | The Workforce agent answers HR process, and never an individual's record | Accepted |
| [018](./018-deployed-build-provenance-check.md) | Check that the deployed build is the build we think it is | Accepted |
| [019](./019-rebrand-the-sop-corpus-to-circle-k.md) | Rebrand the SOP corpus to Circle K, reversing the Brightpath position | Accepted |
| [020](./020-deploy-main-on-every-commit.md) | Deploy `main` on every commit, and make the deploy prove its own result | Accepted |
| [021](./021-connect-the-socket-before-navigation.md) | Connect the WebSocket on the `createPlan` response, not on the plan page | Accepted |
| [022](./022-completed-tasks-are-hidden-never-deleted.md) | Completed tasks are hidden, never deleted | **Superseded by 026** |
| [023](./023-progress-narration-claims-only-what-a-signal-reports.md) | The loading screen claims only what a signal reports | Accepted |
| [024](./024-the-escalation-continues-the-troubleshooting-conversation.md) | The escalation continues the troubleshooting conversation | **Superseded by 027** |
| [025](./025-chat-is-the-unit-of-the-surface.md) | Chat is the unit of the surface | Accepted |
| [026](./026-chats-are-deleted-not-hidden.md) | Chats are deleted, not hidden | Accepted — supersedes 022 |
| [027](./027-resume-continues-the-session.md) | Resume continues the session | Accepted — supersedes 024 |
| [028](./028-a-reviewable-plan-is-earned-by-a-transaction.md) | A reviewable plan is earned by a transaction, not by a question | Accepted |
| [029](./029-an-issue-declares-its-model-with-one-task-type-label.md) | An issue declares its model with one `task-type:` label, over a committed table | Accepted |
| [031](./031-leaving-a-chat-ends-its-turn.md) | Leaving a Chat ends its turn, and says so | Accepted |
| [035](./035-the-rail-pushes-and-the-chat-panel-floats.md) | The rail pushes and the chat panel floats | Accepted |
| [033](./033-a-one-tap-control-never-invents-the-words-it-offers.md) | A one-tap control never invents the words it offers | Accepted — replaces ADR-024's home-card rule |
| [034](./034-the-identity-boundary-gate-covers-the-clarification-seam.md) | The Identity boundary gate covers the clarification seam | Accepted |
| [036](./036-the-simulated-badge-comes-off-and-the-disclosure-stays-in-the-words.md) | The Simulated badge comes off, and the disclosure stays in the words | Accepted — amends the **Simulated label** rule |
| [037](./037-a-fabricated-human-decision-is-never-indistinguishable-from-a-real-one.md) | A fabricated human decision is never indistinguishable from a real one | Accepted — bounds 036, binding on spec 4 |

## Writing a new one

Copy the shape of a recent ADR: `# ADR-NNN: <decision>`, then `## Status`, `## Date`,
`## Issue`, `## Context`, `## Decision`, `## Considered Options`, `## Consequences`,
`## References`. Add the row here in the same commit — the test fails otherwise.

**Do not edit a superseded ADR's body.** Mark its status and leave the reasoning intact; ADR-002
is retained unedited precisely because reading its stale consequence as authority nearly caused
a load-bearing resource to be deleted.
