# CONTEXT.md

Glossary and ubiquitous language for the **Circle K Frontline Store Assistant** — built on the
**MACAE baseline**, the Microsoft Multi-Agent Custom Automation Engine (MACAE) solution accelerator
taken at commit `c5a7a4d1f0bfb6930b4c7b7f6356f28e7e03c309` and diverged from (see
[ADR-004](docs/ADR/004-fork-macae-at-pinned-upstream-commit.md) and
[ADR-006](docs/ADR/006-macae-is-a-one-way-baseline.md)).

ADRs live in `docs/ADR/` — the directory upstream already uses, with its three-digit `NNN-`
numbering continued rather than the four-digit example in `docs/agents/domain.md`.

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
Upstream hardcodes it as a literal; the two-lane design makes it a per-request value.

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

## Build and test

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
re-run the check rather than trusting the date on it.

**Runner state** — `.git-loopy/` at the repo root holds the runner's event log, run summaries and
diagnostics. The runner appends `.git-loopy/` to `.gitignore` itself when the entry is missing, and
never commits that edit — which dirties the base worktree and makes the integration publish
(`git merge --no-ff`) refuse to overwrite `.gitignore`. The entry is therefore **tracked** in
`.gitignore`, which keeps the runner's append a permanent no-op. Do not remove it. Its diagnostic
log (`.git-loopy/logs/<iso>-<run_id>.log`) is the first place to look when the gate reports red —
it distinguishes "gate could not run" and "publish failed" from an actually-failing loop.

## Confirmed findings

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
