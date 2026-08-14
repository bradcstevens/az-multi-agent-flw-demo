import { expect, test } from '@playwright/test';

import { boundaryProbe } from '../authored';
import { StoreSurface } from '../pages/StoreSurface';

/**
 * Beat 6 — the door in the wall.
 *
 * The demonstration's closing argument, and the one beat here whose two halves
 * only mean anything together: the same words, refused and then answered. It is
 * "the entire licensing and governance conversation in ten seconds" — anonymous
 * on the shared device is cheap, useful and strictly store-scoped; a named,
 * licensed identity is what buys a personal answer; and the boundary is a
 * **door**, not a wall.
 *
 * Three things about it are only observable in a browser, which is why they are
 * asserted here and cannot be asserted anywhere else in this repository:
 *
 * - the door is **inside** the refusal rather than beside it;
 * - the second asking is **the same words**, which nothing on screen shows,
 *   because the refusal cleared the box;
 * - a sign-in that signed nobody in does **not** re-ask — the fails-closed
 *   branch, which never runs on a healthy deployment and therefore has to be
 *   provoked.
 */

test.describe('the door in the wall', () => {
    test('asks the refused words again, and answers them', async ({ page }) => {
        const probe = boundaryProbe();

        const store = new StoreSurface(page);
        // Before the first tap: a request already sent cannot be read back.
        const asked = store.watchQuestionsAsked();
        await store.open();

        await store.tapQuickTask(probe.name);
        await expect(store.policyBlock).toBeVisible({ timeout: 120_000 });

        // The door, and where it is. One inside the refusal *and* one on the
        // whole page: the scoped count alone passes against a second button
        // in the header, and the page-wide count alone passes against a
        // separate login screen. The claim is that they are the same button.
        await expect(store.signInToContinue).toBeVisible();
        await expect(store.signInAnywhere).toHaveCount(1);

        expect(asked, 'the refused question was never asked').toHaveLength(1);
        const refusedWords = asked[0];
        expect(refusedWords).toBe(probe.prompt);

        await store.signInToContinue.click();

        // The same words, read off the request rather than off the surface.
        // `expect.poll` rather than a fixed wait: the re-ask goes out after a
        // sign-in round trip, and a beat that slept would be asserting the
        // sleep was long enough.
        await expect
            .poll(() => asked.length, { timeout: 120_000 })
            .toBeGreaterThan(1);
        expect(
            asked[1],
            'the sign-in asked something other than the words the gate ' +
                `refused. It refused ${JSON.stringify(refusedWords)} and ` +
                `then asked ${JSON.stringify(asked[1])}, so the audience is ` +
                'not watching a comparison',
        ).toBe(refusedWords);

        // And the answer landed where the refusal was. The **Personal answer**
        // replaces the **Policy block** rather than appearing under it, which
        // is what makes the before-and-after a before-and-after.
        await expect(store.personalAnswer).toBeVisible({ timeout: 120_000 });
        await expect(store.policyBlock).toBeHidden();

        // Carrying its simulated labelling, unconditionally. Every figure in
        // that record was authored for the walkthrough and no payroll system
        // was queried; a stakeholder who works that out afterwards has stopped
        // believing the panels that *are* connected.
        await expect(
            store.personalAnswer.getByTestId('simulated-badge').first(),
        ).toBeVisible();

        // The header gained a name, which is the other half of what the room
        // is watching. Asserted as the anonymous label being *gone* as well,
        // because a surface showing both has claimed and disclaimed an
        // identity at the same time.
        await expect(store.identityName).toBeVisible();
        await expect(store.identityAnonymous).toHaveCount(0);
    });

    test('does not re-ask when the sign-in signed nobody in', async ({
        page,
    }) => {
        const probe = boundaryProbe();

        const store = new StoreSurface(page);
        const asked = store.watchQuestionsAsked();

        // The **fails-closed** branch, provoked. `HomeInput` states it: asking
        // again anonymously would show the identical refusal a second time and
        // "read on stage as the tap having done nothing at all" — which is
        // worse than the tap doing nothing, because the audience has just been
        // told the boundary is a door.
        //
        // It runs only when the sign-in route fails, which a healthy
        // deployment never does. A beat that did not break it deliberately
        // would be asserting the requirement by reading the code that
        // implements it.
        await page.route('**/sign_in', (route) =>
            route.fulfill({
                status: 500,
                contentType: 'application/json',
                body: JSON.stringify({ detail: 'no identity was written' }),
            }),
        );

        await store.open();
        await store.tapQuickTask(probe.name);
        await expect(store.policyBlock).toBeVisible({ timeout: 120_000 });
        expect(asked).toHaveLength(1);

        await store.signInToContinue.click();

        // Nothing was asked again, and the refusal is still the refusal.
        // Given long enough to have gone wrong: a poll that resolved the
        // instant it was called would pass before a re-ask could have been
        // sent, which is the negative asserting its own timing.
        await expect(store.signInToContinue).toBeEnabled({ timeout: 60_000 });
        await page.waitForTimeout(5_000);
        expect(
            asked,
            `the surface asked ${JSON.stringify(asked.slice(1))} after a ` +
                'sign-in that signed nobody in. The second asking is ' +
                'anonymous, so it is refused again — and an identical refusal ' +
                'appearing twice reads as the button being broken',
        ).toHaveLength(1);
        await expect(store.policyBlock).toBeVisible();
        await expect(store.personalAnswer).toHaveCount(0);
        await expect(store.identityAnonymous).toBeVisible();
    });
});
