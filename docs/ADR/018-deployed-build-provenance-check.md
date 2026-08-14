# ADR-018: Check that the deployed build is the build we think it is

## Status

Accepted

## Date

2026-08-13

## Issue

#1 (spec #1)

## Context

On 2026-08-13 the `macae-flw-v1` deployment was found to be running images built at
`2026-08-12T23:32Z` — **42 commits behind `main`**, and predating the rebrand (#25), the
transparency signals and panels (#23, #24), the Quick Tasks (#26), the mocked sign-in (#27), the
escalation ticket (#22), the troubleshooting memory (#21), the lane router (#16), the identity
boundary gate (#14) and the Direct Line client and SOP tool (#18). What was deployed was
substantially the stock accelerator. The served page title said so: `Multi-Agent - Custom Automation
Engine`, against a repository whose `src/App/index.html` reads `Circle K Frontline Store Assistant`.

Nothing caught it, and the reasons are structural rather than careless:

- **Every declared Feedback loop runs against fakes and stubs.** The backend suite stubs
  `agent_framework`; the frontend suite is jsdom. None of them observes a deployment, so all of them
  stayed green.
- **The deployed-environment preflight checks provenance, not currency.**
  `_application_images_check` asserts the image is not the **Placeholder image** and that it comes
  from the expected registry hostname. Both were true of an image four weeks of work out of date.

So the repository had thirteen green checks on a deployment that could not have run its own
centrepiece beat. A demonstration is the one artefact where "the tests pass" and "the thing works"
being different is not an academic distinction.

## Decision

**Add a check that compares the running Container Apps' images to `HEAD`, and fail loudly on drift.**

The check records the commit each image was built from — the image tag carries it, or an OCI label
does — and compares it to the current `HEAD`. It reports the number of commits between them and the
titles of anything not deployed. It joins `scripts/preflight/` alongside the other records, keeping
its decision logic in a pure importable module so the CI-tooling loop can unit-test the verdict
without a live tenant, as every other check here does.

It is also the **Demo validator**'s first assertion. A validator that proves seven beats against
last month's code proves nothing, and the presenter running the preflight needs to be told *"this
is not the build you think it is"* before they are told the beats are green.

## Considered Options

- **Rely on discipline — always redeploy after merging.** Rejected. It is what was already in place,
  and the failure mode is silent, so discipline has nothing to fail against.
- **Deploy automatically from `main`.** Rejected for this build: `azure-dev.yml` is
  `workflow_dispatch` on purpose, the deploy path involves a manual `az acr build` ordering that
  commit `6a7199a5` established for good reasons, and `post_deploy.sh` re-seeds content packs — an
  automatic deploy would re-seed the six stock packs #25 suppressed unless `MACAE_USE_CASE=none` is
  pinned. Automating a path with that many live edges, the day before a demonstration, is the wrong
  order of operations. Worth revisiting afterwards.
- **Check only that the image is newer than some date.** Rejected: it answers "is it recent" when
  the question is "is it *this*". A rebuild of old code passes a freshness check.

## Consequences

- **Positive:** The class of failure that produced this ADR becomes loud, and becomes the first
  thing the presenter's preflight reports.
- **Positive:** The check is cheap and read-only — an `az containerapp show` and a `git` count — so
  it can run before every validator run without cost.
- **Negative:** It requires the image tag or label to carry the commit. `build_and_push_images.sh`
  must be changed to stamp it, which means the first run after this change has nothing to compare
  against and must report *unknown* rather than *drifted*. Unknown is a true answer and is reported
  as one; treating it as a pass would rebuild the exact hole this closes.
- **Negative:** It couples a preflight check to `git` state, so it is meaningless run from a
  detached or stale checkout. The check reports which commit it compared against, so the reader can
  see when that has happened.

## References

- `CONTEXT.md` — **Deployment drift**, **Placeholder image**, and the confirmed finding of
  2026-08-13
- [docs/preflight/deployed-environment.md](../preflight/deployed-environment.md)
- [ADR-016: TypeScript `@playwright/test` for the Demo validator](./016-typescript-playwright-for-the-demo-validator.md)
