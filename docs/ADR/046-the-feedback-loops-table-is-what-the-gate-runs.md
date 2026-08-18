# ADR-046: The Feedback loops table is what the gate runs, so nothing in it may observe a deployment

## Status

Accepted — amends ADR-005's table

## Date

2026-08-17

## Issue

#115 (auto-resolution of the post-merge gate)

## Context

ADR-005 put the loop commands in one place — the `## Feedback loops` table in `AGENTS.md` — because
the integration gate reads that table and runs those commands to decide whether a merged lane is
green. That is still right, and it is also the whole of the problem: **a row is not advice to a
reader, it is a command the gate executes against every lane that ever merges.** The gate runs it in
a *fresh worktree* (ADR-045), through a plain shell, unattended, with no `az login` behind it, on an
integration branch that by definition has not merged.

The **Demo validator** was a row. Its first assertion, by ADR-018, is that the Container Apps are
serving `HEAD`:

> `e2e/deployedBuild.ts` runs `check-deployed-build.sh` and stops the run if the Container Apps are
> not serving `HEAD`.

And by ADR-020 a deployment happens on a push to `main`. An integration branch is the branch that
has *not* been pushed to `main` yet. So the validator run at the gate is red before a browser opens,
every time, for every lane — and no diff can turn it green. Reproduced on 2026-08-17 against #115's
integration branch:

```
FAIL  build-currency: 82590b278dc5 (…) is 11 commit(s) behind HEAD.
The deployed build is not this commit, so no beat below would mean what it says.
```

Two further properties made this expensive rather than merely wrong. The gate is **fail-fast**, so
the validator's red hid whatever it ran before; and the run costs `npm ci`, a Chromium download and
an `az containerapp show` before it reports. Issue #115 spent its post-merge gate and all three
auto-resolution attempts on it — attempt 1 fixed a genuine Backend lint failure (ADR-045), the gate
advanced to the Demo validator, and the next two attempts had nothing they could fix.

`AGENTS.md` had, all along, a note saying the validator "is not in any workflow and must not be
added to one", for exactly this reason — a live conversation with the agent pool that a pull request
cannot hold. It said *workflow*. The integration gate is not a workflow, so the note was true and
the table contradicted it anyway. Three other tools — the **Stage driver**, the **SOP rehearsal**,
the **Routing probe** — already carry the sentence "it is not a loop and is not in the table",
which is the correct treatment arrived at three times and never generalised.

## Decision

**A tool that observes a deployment is not a declared loop.** The Demo validator's row comes out of
the `## Feedback loops` table and joins the notes beneath it, alongside the Stage driver, the SOP
rehearsal, the Routing probe and fast-lane latency. The table above the notes is exactly the set of
commands that hold against fakes and stubs in a fresh worktree with no tenant.

The table now says so in its own right, rather than leaving it to be inferred from six rows that
happen to comply. Losing that sentence is how the row came back once already.

And the rule is enforced by `src/tests/ci/test_feedback_loops.py`, in the CI-tooling loop, which
parses the table **the way the gate parses it** — the same section regex, the same column-by-header
lookup, the same end-of-section rule — and then asserts three things:

- No row names a deployment-observing entry point. Those four are listed with the reason each one
  needs a tenant.
- No row *reaches* the Azure CLI, following one level of indirection through `scripts/` and
  stripping `#` comments first, so a script that documents `az login` in a banner is not mistaken
  for one that runs it. This is the derived half: it catches a tool nobody thought to name.
- The table parses and every row is runnable. A table the gate cannot parse raises rather than
  passing, and the safe reading of "cannot gate" is "do not land" — so a table that stops parsing
  takes every lane down with it, which is worth a cheap test of its own.

## Considered Options

**Keep the row and set `E2E_SKIP_BUILD_CHECK=1` at the gate.** Rejected twice over. The flag exists
for the Stage driver, where refusing to start over a one-commit drift mid-demonstration does more
harm than the drift; using it at the gate would run every beat against whatever build happens to be
deployed and report the resulting failures as findings about the lane — which is precisely the
day-long misdiagnosis ADR-018 was written to end. And the run would still need `az login` and still
hold a live conversation with the agent pool on nobody's behalf.

**Keep the row and let the gate skip loops it cannot run.** Rejected: the gate has no way to tell
"this loop cannot run here" from "this loop failed", which is the same conflation ADR-045 fixed for
the bootstrap by giving it exit 3. Teaching the runner a second such convention is a change to a
tool outside this repository, to accommodate a row this repository should not have.

**Leave it to the note and trust the next reader.** Rejected: that is the state that produced the
defect. The note and the table disagreed for weeks and the table won, because the table is what
runs.

## Consequences

- The gate is about the lane again. Six rows, all of which hold offline, and a red one is a finding
  about somebody's diff.
- The validator loses nothing it had. It was in no workflow before and is in none now; it is run
  deliberately, after `az login`, exactly as `docs/demo-validator.md` already described. What it
  loses is a caller that could never have satisfied its first assertion.
- **Nothing gates the walkthrough automatically, and nothing did.** The validator's value was never
  in being run by CI — it cannot be — so this removes a false green-or-red, not a check. The
  standing obligation is unchanged: run it after deploying, and read `e2e/artifacts/report`.
- Adding a deployment-observing tool to the table is now a red CI-tooling loop with the reason in
  the failure message, rather than a red integration gate three attempts later with the reason
  nowhere.
- The rule generalises the sentence three notes were already carrying, so the next such tool has
  somewhere obvious to go.

## References

- [ADR-005](./005-declare-feedback-loops-in-agents-md.md) — the table this amends.
- [ADR-045](./045-the-feedback-loops-virtualenv-is-shared-across-worktrees.md) — the fresh worktree
  the gate runs in, and the exit-3 distinction between "cannot run" and "found something".
- [ADR-016](./016-typescript-playwright-for-the-demo-validator.md) — the validator itself.
- [ADR-018](./018-deployed-build-provenance-check.md) — the deployed-build check that is its first
  assertion.
- [ADR-020](./020-deploy-main-on-every-commit.md) — deployment happens on a push to `main`.
- `docs/demo-validator.md` — how to run it, and what it is for.
