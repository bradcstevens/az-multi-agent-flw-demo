# The Stage driver and the recorded fallback

Issue #51, decided in [ADR-016](ADR/016-typescript-playwright-for-the-demo-validator.md). The
**Demo validator**'s own specs and page objects, run headed and paced — for rehearsal, and as a way
to present the walkthrough if clicking through it by hand goes wrong. Plus the recording that a
passing run leaves behind, which is the demonstration's last-resort fallback.

Not a second suite. A second suite is a second description of the walkthrough, and the two will
disagree. The driver is a `projects` entry in `e2e/playwright.config.ts` and one switch on the loop
script; everything it runs is the validator's.

## Running it

```bash
bash scripts/e2e-tests.sh --stage                    # the deployed surface, headed and paced
bash scripts/e2e-tests.sh --stage --target local     # a local `npm run dev` on :3001
E2E_PACE_MS=2000 bash scripts/e2e-tests.sh --stage   # slower, for a first read-through
E2E_PACE_MS=0 bash scripts/e2e-tests.sh --stage      # headed, unpaced
```

`--stage` is the whole of the difference. It composes with `--target`, bootstraps the same
toolchain, and resolves the deployed frontend's FQDN the same way — see
[docs/demo-validator.md](demo-validator.md).

The pace is `launchOptions.slowMo`, defined once in `e2e/stage.ts` and defaulting to **1200ms** per
browser action: a beat of silence, long enough for *"watch the Grounding panel"* to land before the
panel lights. It is a knob rather than a constant because the number belongs to the presenter — a
rehearsal runs faster than a room. Pacing is `slowMo` and nothing else; a `waitForTimeout` sprinkled
through the specs would slow the validator down too, and the validator's runs are already minutes
long because every beat is a live conversation with an agent pool.

The window is fixed at 1600×1000 rather than maximised, and the video is recorded at that same size
rather than at Playwright's default (which fits the frame inside 800×800 and halves it). Playwright
records what the viewport shows, so a recording whose dimensions depend on the laptop that produced
it letterboxes differently every time it is made — with the **Transparency rail** as the part that
gets cropped. Halved, the **Grounding panel** is a grey smudge, and the panel is the whole claim the
fallback exists to show. A larger file is the right trade for a recording somebody projects.

## The recorded fallback

The presenter will be alone in the room, their primary access is a URL, and *"the Container App is
cold"* is not a situation they can recover from. A recording of the real system, produced by the run
that proved it works, is the floor under that.

A run in which **every beat passed** leaves:

```
e2e/artifacts/walkthrough/
  walkthrough.html      the beats in order, one after another, in any browser
  walkthrough.json      what was recorded, from which target and commit, and when
  01-<beat>.webm        one video per beat, in the order they were run
```

Copy that directory anywhere — a memory stick, a laptop that has never seen this repository — and
open `walkthrough.html`. It has no stylesheet, no script tag pointing anywhere and no dependency on
Playwright's report viewer, because the machine it has to work on is not this one. The videos play
on their own too.

`e2e/reporters/walkthrough.ts` produces it, and it is registered for **both** projects: the run that
must leave a recording is a run that passed, and the validator passes far more often than the driver
is run.

### Three rules, all of them the point

**Only a run in which every beat passed replaces it.** A fallback made of the demonstration failing
is worse than no fallback, because the presenter finds out what is on it in front of the customer. A
red run leaves the last good recording exactly where it was and says so on stdout; that run's video
is still under `artifacts/runs/` and in the HTML report, where a debugging artefact belongs.

**The beats are read off the run, never from a list.** A roster inside the reporter stops covering
the beat added after it was written, and nothing goes red — the recording just quietly becomes
partial. `onTestEnd` sees whatever ran, in the order it ran.

**A filtered or multi-project run does not qualify.** `--grep`, a bare positional (every one of them
is a file-path regular expression to `playwright test`, so `cross-platform` narrows a run as surely
as `--grep` does), a shard or a run of both projects each produce something that is not the
walkthrough while looking exactly like one. The filter is detected from `process.argv`, not from
`FullConfig.grep`: Playwright applies `--grep` to the suite and leaves the config's own value at its
default, so a config-only check reports one beat out of four as the complete walkthrough. That was
observed, not assumed. Filters are found by elimination — skip the flags and the values they consume
— and the elimination is biased towards refusing: an unrecognised flag that takes a value makes the
run *look* filtered, and being wrong that way costs a recording rather than publishing a subset
under the walkthrough's name.

The replacement itself is a swap, not a rewrite: the beats are assembled in a staging directory
carrying the run's pid, the recording being replaced is moved aside rather than deleted, and it is
put back if the swap fails. The state that must never exist is *no fallback at all*.

`filteredBy` is exercised rather than read — `src/tests/ci/test_stage_driver.py` runs it under
`node --experimental-strip-types` and skips where there is no node — and the switch is exercised by
running the loop script itself against a stubbed `npx`. What is only read as text is the rest of the
reporter, whose behaviour needs a browser and is proved by running it.

## Dropping this leaves the validator working

Deliberately. The driver is presenter-facing and the first thing to cut if time runs out. It is a
`projects` entry, a `--stage` branch in the script and a reporter; the validator's default is
`validator`, so an unattended run never opens a browser window on somebody's screen.

The CI-runnable half of all this is `src/tests/ci/test_stage_driver.py`, the same seam and the same
reason as `test_e2e_wiring.py`: the browser suite needs a running deployment and CI has none. Where
it can, it *exercises* rather than reads — the loop script is run against a stubbed `npx` to see the
command line it actually builds, and the filter detection is run under node — and where it cannot,
it reads the harness as text with the comments stripped.
