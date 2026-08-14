# Check: the deployed build is the build we think it is

**Verdict: measured, not assumed.** `check-deployed-build.sh` reads the commit off every Container
App's image and asks `git` how far it is from `HEAD`. First run 2026-08-14 (issue #48) against
`rg-macae-flw-v1`, and it went red on its first attempt with a true finding — the three application
hosts were on `6b6de130dfa6`, one commit behind, and the report named what was missing:

```
Deployed build: rg-macae-flw-v1
  PASS  comparison-base: compared against 231eeeecfce6 on branch main
  PASS  build-stamp: all 3 container apps run a commit-tagged image
  FAIL  build-currency: 6b6de130dfa6 (ca-mcp-macaeflwv1flrpd, ca-macaeflwv1flrpd,
        app-macaeflwv1flrpd) is 1 commit(s) behind HEAD. Not deployed: 'Give the surface an
        outline, and stop the model heading it'
  PASS  build-agreement: every container app runs the same build
```

Re-check with `scripts/preflight/check-deployed-build.sh`. It is **read-only** — one
`az containerapp list` and a handful of `git` queries — so it costs nothing to run before every
rehearsal.

This is the third of the three deployment records, and the one that measures rather than infers.

| Record | Asks | Blind to |
| --- | --- | --- |
| [deployed-environment.md](deployed-environment.md) | Is the **infrastructure** right? Regions, the model roster, three hosts on images from our own registry. | Currency. All thirteen checks were green on 2026-08-13 against images 42 commits out of date. |
| [deployed-surface.md](deployed-surface.md) | Is the **surface** the demonstration? The served page title, the Quick Tasks, the token endpoint, one procedure question. | Distance. It catches drift that has already changed something visible, and cannot tell a deployment one commit behind from a current one. |
| **this record** | Is the deployed build **this commit**? | What is *in* the commit. It is a distance, not a quality. |

**Deployment drift** is the term for the gap the third one closes, and
[ADR-018](../ADR/018-deployed-build-provenance-check.md) is the decision.

## What the check proves, and why each fact needed proving

| Check | Why it is not assumable |
| --- | --- |
| `comparison-base` | The verdict is a claim *about `HEAD`*, so a detached or stale checkout makes every line below it meaningless. It reports the commit, the branch, and whether the worktree is dirty, so the reader can see when that has happened rather than trusting a number derived from somewhere they are not. |
| `build-stamp` | Every host's image tag names a commit. An image on `:latest`, or pinned by digest, cannot say what it was built from — and ADR-020 records why a deployment *on* `latest` is its own failure: `azd provision` rolls only the app whose template changed. |
| `build-currency` | The commit is `HEAD`. A failure reports the **distance** and the subject line of every commit that is not deployed, because "9 commits behind" and "the frontend fix you are gating is not in there" are different mornings. |
| `build-agreement` | All three hosts run the *same* build. Three hosts on two commits is ADR-020's second failure mode seen from outside — a deploy that looked successful and updated one app in three — and it passes a per-app currency check whenever the newest app happens to be `HEAD`. |

## Unknown is not a pass

The check has three states, not two, and the third is the reason it exists.

| Exit | Means |
| --- | --- |
| `0` | Every check passed. The deployment is this commit. |
| `1` | A check **failed**. The deployment is a different commit, and the report says which and how far. |
| `3` | Nothing failed and something could not be **proved** — an image whose tag names no commit, a commit this checkout has never heard of, no `git` at all. |

ADR-018 is explicit that rounding the third to `0` rebuilds the exact hole the check closes: an
untagged image is precisely the state a hand-run `az acr build` leaves behind, and it is the state
that looks most like everything being fine. The report prints `UNKN`, four characters wide, for the
same reason — a reader scanning a column of verdicts reads shape before words.

## Scope: the tag is the stamp, and a tag is a claim

The commit is read from the **image tag**. `deploy-main.yml` builds `<image>:<sha>` from
`git rev-parse --short=12 HEAD`, so every image the deploy path produces carries the commit it was
built from, applied at build time.

What that is not is a stamp *inside* the image. Anyone with registry rights can push any tag onto
any image, and a hand-run `az acr build` with a hand-typed tag would be believed. ADR-018 anticipated
needing an OCI label for this reason and treated the first run as having nothing to compare against;
by the time the check was built that was no longer true, because ADR-020 had already made the tag
the commit and the deploy path the only way images reach this environment. So the first version
reads the tag, and this paragraph is the honest limit rather than a silence.

The direction that limit fails in is the safe one. A tag that names no commit is `UNKN`, never
`PASS`; a tag naming a commit this checkout does not know is `UNKN`, never `PASS`. Only a *wrong*
tag on the *right*-looking commit would be believed, and nothing in the deploy path can produce one
by accident.

## Where it runs

- **By hand**, before a rehearsal: `bash scripts/preflight/check-deployed-build.sh`.
- **As the Demo validator's first assertion.** `e2e/deployedBuild.ts` is the suite's `globalSetup`,
  so the build is dated before a browser opens and a drifted deployment stops the run instead of
  producing seven beats about another commit. See [../demo-validator.md](../demo-validator.md).

It is deliberately **not** a spec and **not** a Playwright project. Either would work and both
quietly delete the **Recorded fallback**: the walkthrough reporter refuses to replace the recording
for a multi-project run, and refuses one in which any beat produced no video — which a check that
drives no browser never does.

There is one way past it, `E2E_SKIP_BUILD_CHECK=1`, and it exists for the **Stage driver**. That is
what the presenter falls back to when clicking through the walkthrough by hand goes wrong, and a
refusal to start over a one-commit drift, mid-demonstration, is the check doing more harm than the
drift. A skipped run prints what it did not prove.

## What it answers, as well as whether it passed

`--json` renders the verdict for a machine rather than a reader, and carries three things the text
report cannot be asked for:

| Field | Why |
| --- | --- |
| `deployedBuild` | The one commit every application host runs, or `null` when they do not agree on one datable commit. It is what the **rehearsal**'s ledger records, so ten green runs can name the build they were ten green runs *of* (#54). |
| `report` | The rendered human report. It travels *with* the verdict so `globalSetup` gets the presenter's text and the commit from one `az` read, and `format_report` is never given a second implementation in TypeScript. |
| `checks` | Each check's name, three-state status and detail. |

`deployedBuild` is `null` on exactly the states the checks call `UNKN` or `FAIL` for disagreement —
an image on `latest`, three hosts on two commits, no container apps at all — for ADR-018's reason
seen from the other side: a build that cannot be named has not been proved, and the name is the
whole point of recording it.

## The failure this closes

Recorded twice, in two shapes:

- **2026-08-13 (#44).** `macae-flw-v1` was found 42 commits behind, serving substantially the stock
  accelerator, while every declared feedback loop was green — because every loop runs against fakes
  and none of them observes a deployment.
- **2026-08-14 (#50).** An integration branch was gated by the Demo validator while the deployment
  served `macaefrontend:a96b44815f80`, nine commits behind and predating the fix being gated. The
  beat went red, correctly, with `expect(locator).toBeHidden() failed` — a message that cannot be
  told apart from a regression in the code under review. The diagnosis took a day. Beside it, a beat
  whose red named its own defect and its issue number was actionable on sight.

The second is the one that shaped the check's placement. A suite that runs its beats and then
explains itself in the failure of one of them has already cost the reader the diagnosis.

## Follow-ups

- **`deploy-main.yml` does not run this check.** It could — the workflow's checkout *is* the commit
  it tagged, so the verdict would be green by construction and would catch a build step that
  silently tagged something else. It needs `fetch-depth: 0` first: `actions/checkout` clones shallow
  by default, `git rev-list` between two commits fails in a shallow clone, and the check would
  correctly report `UNKN` and fail the deploy.
- **A stamp inside the image** — an OCI `org.opencontainers.image.revision` label, read back through
  the registry — would close the "a tag is a claim" gap above. It costs a `LABEL` in three
  Dockerfiles, a `--build-arg` in the workflow, and a config-blob read the check does not currently
  need permission for.
