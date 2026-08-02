# ADR-004: Fork MACAE by merging the pinned upstream commit into this repository

## Status

Accepted

## Date

2026-08-01

## Issue

#9 (spec #1)

## Context

The Circle K Frontline Store Assistant is built on Microsoft's **Multi-Agent Custom Automation
Engine (MACAE)** solution accelerator rather than from scratch. Upstream
(`microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator`) is actively maintained and
was pushed to on the day of verification, so tracking `main` would let an upstream push change the
build the day before a stakeholder demo.

We also need upstream fixes to remain cherry-pickable without a second clone or a separate fork to
keep in sync.

## Decision

Merge upstream into **this** repository at the pinned commit
`c5a7a4d1f0bfb6930b4c7b7f6356f28e7e03c309` with `--allow-unrelated-histories`, preserving upstream
history, and retain an `upstream` remote for cherry-picks. One consolidated repository; no separate
fork.

```
git remote add upstream https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator.git
git fetch upstream
git merge c5a7a4d1f0bfb6930b4c7b7f6356f28e7e03c309 --allow-unrelated-histories
```

### Conflict resolutions

Three add/add conflicts arose against the pre-merge scaffolding:

- `CONTRIBUTING.md`, `SECURITY.md` — took upstream's canonical accelerator versions so future
  cherry-picks apply cleanly.
- `.gitignore` — took upstream's, then appended a fork-specific block (editor/OS noise, tool caches,
  and `.reference/` for the superseded build-requirements document).

`.github/pull_request_template.md` (the scaffolded lowercase copy) was removed because it collides
with upstream's `.github/PULL_REQUEST_TEMPLATE.md` on case-insensitive filesystems.

## Toolchain minimums (verified on the build machine)

| Tool | Verified | Finding |
| --- | --- | --- |
| `azd` | 1.25.1 | Usable. `azd config set provision.preflight off` is accepted and reads back `"off"`. The accelerator's own `docs/DeploymentGuide.md` requires this setting for 1.23.9 and above; it is **not** an alpha feature, so no `alpha.` prefix. |
| Bicep CLI | **v0.36.1 minimum** | Established by bisection against `az bicep build --file infra/main.bicep`. |
| Python | 3.11 | Matches `.github/workflows/test.yml`. |
| Node | 22 | `src/App` builds with `npm ci && npm run build` (Vite 7). |

### How the Bicep minimum was established

`az bicep build --file infra/main.bicep` was run against successively older Bicep CLI releases:

| Version | Result |
| --- | --- |
| v0.24.24 / v0.26.170 / v0.30.23 | Fail — `deployer()` does not exist (BCP057) |
| v0.32.4 | Fail — `deployer()` exists but has no `userPrincipalName` (BCP053) |
| v0.33.93 | Fail — same, plus resource-derived types require an experimental flag (BCP385) |
| v0.34.44 / v0.35.1 | Fail — `deployer().userPrincipalName` still missing (BCP053) |
| **v0.36.1** | **Pass** — exit 0, warnings only |
| v0.45.15 | Pass — exit 0, warnings only |

`v0.35.1` is the last v0.35 release and `v0.36.1` is the first v0.36 release, so **v0.36.1 is the
minimum**. The binding constraint is `deployer().userPrincipalName`, used by the deployer role
grants in `infra/`.

## Build and test contract

Tests run from the repo root with the **two-phase invocation** `.github/workflows/test.yml` already
performs, and that split must be preserved — the suite mutates `sys.modules` and the environment at
import time, so `test_app.py` must run in its own pytest process first:

```bash
PYTHONPATH=src:src/backend python -m pytest src/tests/backend/test_app.py \
  --cov=src/backend --cov-config=.coveragerc -q

PYTHONPATH=src:src/backend python -m pytest src/tests/backend \
  --cov=src/backend --cov-append --cov-report=term --cov-report=xml \
  --junitxml=pytest.xml --cov-config=.coveragerc --ignore=src/tests/backend/test_app.py
```

Verified green at the merge commit: **29 + 834 = 863 passed**, 86% line coverage (above the
workflow's 80% gate).

## Consequences

- Upstream history is preserved (4,424 commits reachable), so `git log`/`git blame` on accelerator
  files still work and `git cherry-pick upstream/<sha>` is available.
- Upstream's CI workflows now live in `.github/workflows/` and will run on this repository. They are
  left untouched for now to keep cherry-picks clean; pruning or disabling the deployment workflows is
  a follow-up.
- `.github/requirements.txt` (what CI installs) has drifted from `src/backend/pyproject.toml` — it
  pins none of the `agent-framework` packages. The suite passes anyway because it doubles those
  modules at import time. Do not treat `.github/requirements.txt` as the runtime dependency set.
- `.github/workflows/test.yml` passes `--cov-config=.coveragerc`, but `.coveragerc` no longer exists
  (it was consolidated into the root `pyproject.toml`). Coverage silently falls back, so the flag is
  a no-op rather than a failure.
