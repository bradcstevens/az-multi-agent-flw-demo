import { expect, test } from '@playwright/test';

import { troubleshootingTask } from '../authored';
import { attemptedSteps } from '../backend';
import { PlanSurface } from '../pages/PlanSurface';
import { StoreSurface } from '../pages/StoreSurface';
import { recordWire } from '../wire';

/**
 * Beat 3 — the assistant remembers what you tried.
 *
 * The demonstration's strongest single claim, and the one the escalation beat
 * then spends: *it does not make you say it twice*. Three things have to be
 * true for that claim to mean anything, and only one of them is visible on the
 * page.
 *
 * The fault has to **provoke a question** — asserted on the wire, because a
 * clarification renders as an ordinary agent turn in prose a model wrote, and
 * "did it ask?" read off the page is a claim about wording.
 *
 * The **Rehearsed replies** have to be offered *only while that question
 * stands*. Outside a clarification they are a second way to start a turn,
 * competing with the box — and, worse, a one-tap answer to a question nobody
 * asked, carrying a request identifier the backend has already answered.
 *
 * And the tap has to **record something**. This is the assertion the beat
 * exists for: the chat shows the associate's words either way, because the
 * browser put them there. A tap that recorded nothing looks exactly like a tap
 * that worked, right up until the ticket four minutes later says *not
 * reported*.
 */

/** The clarification, in the vocabulary both ends of the socket share. */
const CLARIFICATION = 'user_clarification_request';

/**
 * What a red on the chips-go-with-the-question assertion means.
 *
 * Hiding them is the fix #50 made at `PlanChat`, so this assertion is the one
 * in the beat that a deployment can fail for its **age** rather than for its
 * behaviour: rolled before that commit, the chips outlive every question and
 * the beat is red on an image, not on the code. Playwright would otherwise
 * report only that a locator stayed visible for thirty seconds, which is "the
 * beat is broken" and "the image is old" arriving as the same red — the
 * confusion #48 exists to remove, and the one this beat produced first.
 */
const CHIPS_OUTLIVED_THE_QUESTION =
    'the rehearsed reply chips outlived the question they answered, so a ' +
    'one-tap answer is still on offer carrying a request_id the backend has ' +
    'already answered. Hiding them is the PlanChat fix of #50: check the ' +
    'running image tag against HEAD before reading this as a regression, ' +
    'because a deployment rolled before that commit is red here for the ' +
    'image rather than for the code (#48)';

test.describe('the troubleshooting beat', () => {
    test('asks what has already been tried, and a tap records it', async ({ page }) => {
        const task = troubleshootingTask();
        expect(
            task.rehearsedReplies.length,
            'the troubleshooting Quick Task authors no rehearsed replies',
        ).toBeGreaterThan(0);

        // Installed before the surface opens: the socket is opened as the plan
        // page mounts, and a recorder attached afterwards misses the frames of
        // the beat it was installed to watch.
        const wire = recordWire(page);

        const store = new StoreSurface(page);
        await store.open();
        await store.tapQuickTask(task.name);

        const plan = new PlanSurface(page);
        await plan.waitForArrival(120_000);

        // Nothing has been asked yet, so there is nothing to answer with one
        // tap. Checked against the wire as well as the surface: if the question
        // had already arrived, an empty chip row would be the *right* surface
        // for the wrong reason, and this beat would be grading a race.
        expect(
            wire.count(CLARIFICATION),
            'the clarification arrived before the beat could observe the ' +
                'surface without one — the assertion below is about the chips ' +
                'being absent while no question stands, so re-run it',
        ).toBe(0);
        await expect(plan.rehearsedReplies).toBeHidden();

        await wire.waitFor(CLARIFICATION, { timeout: 240_000 });

        // The question stands, so the answers are offered — all of them, in the
        // order the Quick Task authored them. A subset is a walkthrough where
        // the presenter reaches for the keyboard on the beat that exists to
        // show they never have to.
        await expect(plan.rehearsedReplies).toBeVisible();
        expect(await plan.rehearsedReplyLabels()).toEqual(task.rehearsedReplies);

        const answer = task.rehearsedReplies[0];
        await plan.tapRehearsedReply(answer);

        // The question has been answered, so the one-tap answers go with it.
        await expect(plan.rehearsedReplies, CHIPS_OUTLIVED_THE_QUESTION).toBeHidden({
            timeout: 30_000,
        });

        // And the tap left a record. Read out of the container the clarification
        // seam writes to, not out of the conversation the browser is holding:
        // the associate's words are on the page either way.
        await expect
            .poll(async () => (await attemptedSteps(page)).length, {
                timeout: 60_000,
                message:
                    'the tap recorded no attempted step. The words are in the ' +
                    'chat because the browser put them there; the record is ' +
                    'what the runbook skips on and what the ticket carries, ' +
                    'and it is empty',
            })
            .toBeGreaterThan(0);
    });
});
