# ADR-006: MACAE is a one-way baseline — no `upstream` remote, no upstream automation

## Status

Accepted

## Date

2026-08-01

## Issue

Spec #1. Partially supersedes [ADR-004](./004-fork-macae-at-pinned-upstream-commit.md) (issue #9).

## Context

[ADR-004](./004-fork-macae-at-pinned-upstream-commit.md) merged the accelerator into this repository
at the pinned commit and **retained an `upstream` remote** so that upstream fixes stayed
cherry-pickable. That remote points at
`microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator`, which lives in the
SAML-enforced `microsoftopensource` GitHub enterprise.

`gh` resolves the base repository by querying GitHub for **every** git remote in the clone, not just
`origin`. One remote inside a SAML-enforced enterprise therefore poisons every `gh` command run from
inside this working tree:

```
GraphQL: Resource protected by organization SAML enforcement.
You must grant your OAuth token access to this organization. (repository)
```

The failure is invisible in the code and easy to misdiagnose, because it is **not** a property of
this repository. Verified on the build machine:

| Invocation | Result |
| --- | --- |
| `gh issue list` (both remotes present) | **Fails** — SAML enforcement, GraphQL 403 |
| `gh issue list` (only `origin` present) | Passes |
| `gh issue list -R bradcstevens/az-multi-agent-flw-demo` | Passes — `-R` skips remote resolution |
| `gh api repos/...` (REST) | Passes |
| `gh api graphql` with an explicit query | Passes |

This repository is **not** a GitHub fork (`isFork: false`, `parent: null`), is private, and is owned
by a personal account. Nothing about it requires SAML. Only the remote did.

The cost was already being paid. `docs/agents/issue-tracker.md` mandates the broken path — *"Infer
the repo from `git remote -v` — `gh` does this automatically when run inside a clone"* — so every
agent skill hit it. The runner's own logs record agents burning iterations rediscovering the
workaround, and issue #9 being left open because it could not be closed through the tracker:

> ⚠️ `gh` is blocked by org SAML enforcement (GraphQL 403), so I could not close or comment on the
> issue.

Because REST kept working while GraphQL did not, agents recorded the failure as intermittent and
token-related rather than structural, and re-attempted it.

The merge also brought upstream's 25 CI workflows into `.github/workflows/`. ADR-004 left them in
place *"to keep cherry-picks clean"*. Among them, `stale-bot.yml` deletes branches and
`scheduled-Dependabot-PRs-Auto-Merge.yml` auto-merges pull requests, both unattended and both able
to collide with the runner's in-flight `git-loopy/*` branches; four more fire on a schedule against
Azure without credentials.

## Decision

**MACAE is a one-way baseline.** This repository took a snapshot of the accelerator at
`c5a7a4d1f0bfb6930b4c7b7f6356f28e7e03c309` and diverges from it. There is no sync relationship, no
cherry-pick path, no contribution back, and no upstream automation — and therefore no reason for
anything here to touch a SAML-enforced enterprise.

1. **The `upstream` remote is removed.** No remote in this clone may point at a SAML-enforced
   organisation. Fixes to accelerator code are made here as our own commits.
2. **Upstream's automation is pruned.** 18 of the 25 inherited workflows are deleted; 7 remain.

If a specific upstream fix is ever genuinely needed, fetch it as a one-off and never persist a
remote:

```bash
git fetch https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator.git <sha>
git cherry-pick FETCH_HEAD
```

### What was deleted, and why

| Group | Files | Reason |
| --- | --- | --- |
| Unattended robots | `stale-bot.yml`, `scheduled-Dependabot-PRs-Auto-Merge.yml` | Upstream's project-management apparatus. Delete branches and auto-merge PRs without a human; collide with `git-loopy/*` lanes. |
| Scheduled deploy / validation | `deploy.yml`, `deploy-v2.yml`, `deploy-waf.yml`, `azd-template-validation.yml`, `validate-bicep-params.yml` | Fire on a schedule against Azure with credentials this repository does not have. |
| Orphaned by the above | `deploy-orchestrator.yml`, `job-deploy.yml`, `job-deploy-linux.yml`, `job-deploy-windows.yml`, `job-docker-build.yml`, `job-cleanup-deployment.yml`, `job-send-notification.yml`, `test-automation.yml`, `test-automation-v2.yml` | `workflow_call`-only, reachable solely from the deleted entrypoints. They look live but can never fire. |
| Guaranteed red | `docker-build-and-push.yml` | Triggers on push to `main` over `src/**`, `infra/**` and `azure.yaml` — all present — then logs into a container registry with no credentials. |
| Inert residue | `agnext-biab-02-containerimage.yml` | Path-filtered to `agnext-biab-02/**`, a directory that does not exist here. |

### What was kept

`pylint.yml` and `test.yml` — the two **feedback loops** declared in `AGENTS.md`
([ADR-005](./005-declare-feedback-loops-in-agents-md.md)). `codeql.yml` — scheduled but
self-contained and needs no secrets. `broken-links-checker.yml`, `pr-title-checker.yml` and
`telemetry-template-check.yml` — pull-request-triggered and harmless. `azure-dev.yml` —
`workflow_dispatch` only.

Tuning the retained workflows (the coverage gate, MCP test coverage) is **not** part of this
decision; it belongs to issue #10.

## Considered and rejected

- **Keep the remote, hide it from `gh`** (`gh repo set-default`, or `-R owner/repo` on every call).
  Both work, but both are configuration rather than structure: any fresh clone, new worktree or new
  machine re-breaks until reconfigured, and the `-R` variant requires editing every agent doc and
  relies on every future agent remembering. The failure mode is silent and expensive to rediscover.
- **Collapse upstream history into a single vendored snapshot commit.** The SAML problem is the
  remote, not the 4,421 upstream commits. A rewrite would orphan the in-flight `git-loopy/*`
  branches and destroy `git blame` on every accelerator file to solve a problem already solved by
  removing the remote.

## Consequences

- `gh` works from inside the clone again, so `docs/agents/issue-tracker.md`, `/wayfinder` and the
  runner's issue operations function as written.
- Upstream history is untouched — 4,421 commits remain reachable, and `git log`/`git blame` on
  accelerator files still work.
- ADR-004 remains authoritative for everything except its `upstream` remote clause: the pinned
  commit, the conflict resolutions, the toolchain minimums (notably **Bicep v0.36.1**) and the
  two-phase test contract all stand.
- The `upstream` remote lives in `.git/config`, which is never committed — so this decision cannot
  be enforced by the repository contents alone. `docs/agents/issue-tracker.md` carries an explicit
  prohibition at the point of failure, and spec #1 was corrected because it previously *instructed*
  agents to add the remote.
- Upstream CI that this project does not use will no longer run, so a red check on `main` means
  something this project actually cares about.
