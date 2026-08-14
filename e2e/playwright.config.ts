import { defineConfig, devices } from '@playwright/test';

import { resolveTarget } from './target';

/**
 * The **Demo validator** (issue #47, ADR-016).
 *
 * TypeScript `@playwright/test` against this repository's Python loop
 * convention, for one reason: the suite's real user is a presenter who does not
 * know agent orchestration and who will be in the room alone. When a beat fails
 * at 11:40 on the morning of a demonstration, a stack trace is a request for an
 * expert. A trace with a DOM snapshot at every step, an HTML report that reads
 * as green rows or one red one, and a video of the run are not.
 *
 * Three things here are load-bearing rather than taste:
 *
 * - **The artefacts are unconditional.** `retain-on-failure` is the obvious
 *   setting and the wrong one: the recording is the demonstration's own
 *   last-resort fallback (#51), so the run that must produce it is the run that
 *   *passed*.
 * - **One `testDir`, one spec set, two targets.** The Stage driver (#51) is a
 *   second `projects` entry over these same specs and these same page objects.
 *   A second suite is a second description of the walkthrough, and the two will
 *   disagree.
 * - **No retries and one worker.** Every beat is a live conversation with an
 *   agent pool; a retried beat is a second conversation, and a beat that
 *   happens four runs in five is not a beat anybody should walk on stage with.
 */
const target = resolveTarget();

/** A generative answer that crosses to Copilot Studio and back is not fast. */
const BEAT_TIMEOUT = 5 * 60 * 1000;

export default defineConfig({
    testDir: './specs',
    outputDir: './artifacts/runs',
    timeout: BEAT_TIMEOUT,
    expect: { timeout: 60_000 },
    fullyParallel: false,
    workers: 1,
    retries: 0,
    forbidOnly: true,
    reporter: [
        ['list'],
        ['html', { outputFolder: 'artifacts/report', open: 'never' }],
    ],
    use: {
        baseURL: target.baseURL,
        video: 'on',
        trace: 'on',
        screenshot: 'on',
        actionTimeout: 60_000,
        navigationTimeout: 120_000,
    },
    projects: [
        {
            name: 'validator',
            use: { ...devices['Desktop Chrome'], viewport: { width: 1600, height: 1000 } },
        },
    ],
    metadata: { target: target.name, baseURL: target.baseURL },
});
