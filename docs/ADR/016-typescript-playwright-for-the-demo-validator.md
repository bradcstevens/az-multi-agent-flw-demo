# ADR-016: TypeScript `@playwright/test` for the Demo validator, against the Python loop convention

## Status

Accepted — amended by [ADR-044](./044-the-feedback-loops-table-is-what-the-gate-runs.md), which
takes the validator out of the `AGENTS.md` Feedback loops *table*: the integration gate runs that
table unattended on a branch nothing has deployed, so the row could only ever be red. Everything
below stands — the language, the entry point, the self-bootstrapping script and the declaration in
`AGENTS.md` — except that the declaration now lives in the notes beneath the table rather than as a
row of it.

## Date

2026-08-13

## Issue

#1 (spec #1)

## Context

Every declared **Feedback loop** in this repository is Python behind a `bash` script, a convention
[ADR-005](./005-declare-feedback-loops-in-agents-md.md) established and `AGENTS.md` enforces. The
backend, the MCP server, the SOP corpus tooling and the preflight checks are all Python. The one
existing browser suite, `tests/e2e-test/`, is Python `playwright.sync_api` inherited from the
accelerator.

So the obvious choice for a browser suite is Python, and it is the wrong one.

The **Demo validator** is not being built to gate a pull request. It is being built because the
deployment was found 42 commits behind while every loop was green (see *Confirmed findings* in
`CONTEXT.md`), and because the demonstration is being handed to a presenter **who does not know
agent orchestration** and who will be in the room alone. The suite's real user is that presenter,
not CI.

That changes what the runner is for. When a beat fails at 11:40 on the morning of a demonstration,
a stack trace is a request for an expert. `@playwright/test` records a **trace with a DOM snapshot,
console log and network log at every step**, and renders it as a single HTML file that shows the
moment it broke. It emits an HTML report that reads as seven green rows or one red one. It records
**video** as a by-product, which is the demonstration's own fallback (ADR: see *Consequences*). And
the **Stage driver** — the headed, paced way to present the same walkthrough — is a second project
in the same config file rather than a second program.

The inherited Python suite is not a starting point. It drives a real Entra login and the
pre-rebrand accelerator surface, it is wired into no workflow, and it tests generic accelerator
scenarios ("HR workflow", "golden path") that this fork deleted. It is deleted here rather than
left, because it looks like the e2e suite and is not.

## Decision

**The Demo validator and the Stage driver are TypeScript `@playwright/test`, in a new top-level
`e2e/` directory, behind `scripts/e2e-tests.sh` declared in `AGENTS.md` as a Feedback loop.**

`tests/e2e-test/` is deleted in the same change.

The loop convention is honoured where it actually binds — the entry point is a `bash` script that
bootstraps its own toolchain and is declared in `AGENTS.md`, exactly as ADR-005 requires. What
changes is the language behind the script, and only for the suite whose subject is a browser.

## Considered Options

- **Python `pytest` + `playwright`, extending `tests/e2e-test/`.** Rejected. It matches the repo's
  convention and loses the three things this suite exists to provide: the trace viewer, the HTML
  report and a near-free stage driver. It would also inherit an Entra login flow that this
  deployment does not use — EasyAuth is off, and the demonstration's sign-in is
  [the Mocked unlock](../mocked-unlock.md), not an identity provider.
- **Keep both — Python for CI, TypeScript for the presenter.** Rejected: two suites asserting the
  same seven beats is two places for the walkthrough to be described, and they will disagree.
- **No browser suite; extend the vitest component tests.** Rejected on the evidence that opened
  this: the vitest suite was green throughout the period the deployed surface was the unbranded
  accelerator. jsdom cannot observe a deployment.

## Consequences

- **Positive:** The failure artefact is legible to a non-expert. That is the whole point.
- **Positive:** The **Stage driver** costs a `projects` entry — `headless: false` plus
  `launchOptions.slowMo` — rather than a second codebase.
- **Positive:** Selectors are shared with the vitest component tests, which already target these
  React components, so `data-testid` attributes serve both and drift in one is caught by the other.
- **Negative:** A second language in the test toolchain, and a second lockfile to keep current.
  Dependabot already raises PRs against `src/App`, so `e2e/` joins that surface.
- **Negative:** ADR-005's "loops are Python" reading is now false as stated. The binding part of
  that ADR — *declare every loop in `AGENTS.md` behind a script that bootstraps itself* — is
  preserved, and this ADR is the record that the language was the incidental half.

## References

- [ADR-005: Declare the Feedback loops in `AGENTS.md`](./005-declare-feedback-loops-in-agents-md.md)
- [ADR-018: A deployed-build provenance check](./018-deployed-build-provenance-check.md)
- `CONTEXT.md` — **Demo validator**, **Stage driver**, **Deployment drift**
- [docs/demo-validator.md](../demo-validator.md) — the validator's record
- [docs/stage-driver.md](../stage-driver.md) — the Stage driver and the recorded fallback (#51)
- [docs/quick-tasks.md](../quick-tasks.md) — the walkthrough the validator asserts
