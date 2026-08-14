/**
 * The **Stage driver**'s pacing (issue #51).
 *
 * The driver is the Demo validator's own specs and page objects, run headed and
 * slowly enough to narrate over — a `projects` entry, not a second suite
 * (ADR-016). What it needs that the validator does not is a *tempo*, and this
 * is the one place that tempo is written down.
 *
 * The number is the presenter's, not the harness's, so it is a knob rather than
 * a constant: a rehearsal runs faster than a room, and a room where the
 * presenter is also answering questions runs slower than a rehearsal.
 *
 *   bash scripts/e2e-tests.sh --stage                  # the room's default
 *   E2E_PACE_MS=2000 bash scripts/e2e-tests.sh --stage # slower, for a first read
 *   E2E_PACE_MS=0 bash scripts/e2e-tests.sh --stage    # headed, unpaced
 *
 * Pacing is `slowMo` and nothing else. A `waitForTimeout` sprinkled through the
 * specs would pace the driver by slowing the validator down too, and the
 * validator's runs are already minutes long because every beat is a live
 * conversation with an agent pool.
 */

/**
 * How long the driver dwells on each browser action, in milliseconds.
 *
 * 1200ms is a beat of silence — long enough for "watch the Grounding panel" to
 * land before the panel lights, short enough that the walkthrough does not
 * become a slideshow. The waits that actually dominate the run are the model's,
 * and no setting here shortens those.
 */
export const DEFAULT_PACE_MS = 1200;

export function resolvePaceMs(env: NodeJS.ProcessEnv = process.env): number {
    const configured = (env.E2E_PACE_MS || '').trim();
    if (!configured) {
        return DEFAULT_PACE_MS;
    }

    const pace = Number(configured);
    if (!Number.isFinite(pace) || pace < 0) {
        throw new Error(
            `E2E_PACE_MS must be a non-negative number of milliseconds, not ${JSON.stringify(
                configured,
            )}`,
        );
    }
    return pace;
}

/**
 * The window the walkthrough is presented in — and, because Playwright records
 * what the viewport shows, the shape of the recording that becomes the
 * fallback. Shared by both projects, so the validator's recording and the
 * driver's are the same artefact.
 *
 * Fixed rather than maximised. A recording whose dimensions depend on the
 * laptop that produced it is a recording that letterboxes differently every
 * time it is made, and the Transparency rail is the part that gets cropped.
 *
 * The video is recorded at this size rather than at Playwright's default, which
 * fits the frame inside 800×800 and halves it. Halved, the **Grounding panel**
 * is a grey smudge — and the panel is the whole claim the fallback exists to
 * show. A larger file is the right trade for a recording somebody projects.
 */
export const RECORDED_VIEWPORT = { width: 1600, height: 1000 } as const;
