import { expect, test } from '@playwright/test';

import { deliberateLane, escalationTask, notReported, ticketNumberPattern } from '../authored';
import { attemptedSteps, draftedTicket, laneTaken, sessionOfPlan } from '../backend';
import { PlanSurface } from '../pages/PlanSurface';
import { StoreSurface } from '../pages/StoreSurface';
import { recordWire } from '../wire';

/**
 * Beat 4 — the approval **is** the ticket being raised.
 *
 * One confirmation, not two, and nothing the associate already said asked for
 * again. Both halves are claims about things that do **not** happen, so both
 * are graded on the wire: a second confirmation would arrive as a second
 * `plan_approval_request` or as a `user_clarification_request` between the
 * approval and the card, and being asked for the troubleshooting history again
 * would arrive as a clarification at all.
 *
 * The **Lane** is read back from server-side session state rather than off the
 * badge. The badge is the browser's own recollection of what the router said,
 * and this beat's whole content is that the request *took* the approval path —
 * a surface rendering `Deliberate` over a request the router sent down the Fast
 * lane is exactly the failure the badge cannot see.
 *
 * Nothing here is asserted about anything a model wrote. The ticket's rows are
 * the template's, its number is a sha256 of the session and its label is a
 * property of the card.
 */

const APPROVAL = 'plan_approval_request';
const CLARIFICATION = 'user_clarification_request';
const TICKET = 'ticket_raised';

/** The plan the surface navigated to, from its own URL. */
function planIdFrom(url: string): string {
    const match = url.match(/\/plan\/([^/?#]+)/);
    if (!match) {
        throw new Error(`not a plan surface: ${url}`);
    }
    return match[1];
}

test.describe('the escalation beat', () => {
    test('takes the Deliberate lane, and approving the plan raises the ticket', async ({
        page,
    }) => {
        const task = escalationTask();
        const wire = recordWire(page);

        const store = new StoreSurface(page);
        await store.open();
        await store.tapQuickTask(task.name);

        const plan = new PlanSurface(page);
        await plan.waitForArrival(120_000);

        // The lane taken, from the state the request path wrote — not from the
        // badge, which is the browser's recollection of the same event.
        const session = await sessionOfPlan(page, planIdFrom(page.url()));
        expect(
            await laneTaken(page, session),
            'the escalation did not take the Deliberate lane server-side, so ' +
                'there is no approval step to be the confirmation',
        ).toBe(deliberateLane());

        // The gate opens. Waiting on the frame rather than on the button means
        // a request that quietly took the Fast lane fails saying so, instead of
        // timing out on a button that was never going to render.
        await wire.waitFor(APPROVAL, { timeout: 240_000 });
        await expect(plan.approveButton).toBeVisible({ timeout: 60_000 });

        // Nothing is raised before the associate confirms. A card already on
        // screen would mean the approval below confirms something that had
        // already left.
        await expect(plan.simulatedTicket).toHaveCount(0);

        const confirmation = wire.mark();
        await plan.approveButton.click();

        await wire.waitFor(TICKET, { from: confirmation, timeout: 240_000 });

        // One confirmation, not two. The approval is the whole of it: no second
        // gate and no question between the approval and the ticket.
        expect(
            wire.count(APPROVAL, confirmation),
            'a second approval prompt arrived after the plan was approved — ' +
                'the approval was not the confirmation',
        ).toBe(0);
        expect(
            wire.count(CLARIFICATION, confirmation),
            'the associate was asked something between approving the plan and ' +
                'the ticket being raised — that is the second confirmation ' +
                'TKT-001 says does not exist',
        ).toBe(0);

        // The card, and the two things on it that are not the model's: the
        // number an associate could read down a telephone, and the label that
        // says it means nothing outside this room.
        await expect(plan.simulatedTicket).toBeVisible({ timeout: 60_000 });
        await expect(plan.ticketNumber).toHaveText(ticketNumberPattern());
        await expect(plan.ticketSimulatedBadge).toBeVisible();

        // What the associate already said, carried. The record is read from the
        // container rather than from the chat, and the comparison is against
        // the ticket row the associate actually read.
        //
        // Total in both directions, which is the whole assertion: a ticket that
        // *invented* steps is as bad as one that dropped them — an engineer is
        // dispatched believing a repair was attempted. So a conversation with a
        // record must carry every step of it, and a conversation without one
        // must say so in the template's own words rather than in a model's.
        //
        // The second branch is reachable on the walkthrough as authored, and
        // that is a finding, not a hedge: the escalation Quick Task starts a
        // **new conversation**, the troubleshooting record is the memory of one
        // conversation, and the surface offers no way to continue the previous
        // one — the plan page's box submits clarifications only. So the steps
        // the associate tapped in beat 3 are in beat 3's record and beat 4's
        // ticket cannot reach them. See `docs/demo-validator.md`.
        const attempted = await attemptedSteps(page);
        const fields = await plan.ticketFields();
        const carried = fields.steps_attempted || '';
        if (attempted.length > 0) {
            expect(
                carried,
                'the ticket did not carry what the associate already reported — ' +
                    `it reads ${JSON.stringify(carried)}`,
            ).not.toBe(notReported());
            for (const step of attempted) {
                expect(carried).toContain(step);
            }
        } else {
            expect(
                carried,
                'this conversation recorded no attempted steps, so the ticket ' +
                    'may only say so — a step on a ticket nobody reported ' +
                    'sends an engineer out on a repair nobody tried',
            ).toBe(notReported());
        }

        // And they were never asked for a second time — not once in the whole
        // conversation, which is the requirement stated as an absence.
        expect(
            wire.count(CLARIFICATION),
            'the escalation asked the associate a question. Whatever it asked, ' +
                'the walkthrough now types what it already knows',
        ).toBe(0);
    });

    test('raises nothing when the plan is rejected', async ({ page }) => {
        // The branch this requirement fails silently in. A rejected plan that
        // raises a ticket anyway is an engineer dispatched against a repair the
        // associate declined — and nobody in the store finds out, because the
        // surface they are looking at has already navigated away.
        const task = escalationTask();
        const wire = recordWire(page);

        const store = new StoreSurface(page);
        await store.open();
        await store.tapQuickTask(task.name);

        const plan = new PlanSurface(page);
        await plan.waitForArrival(120_000);

        await wire.waitFor(APPROVAL, { timeout: 240_000 });
        await expect(plan.rejectButton).toBeVisible({ timeout: 60_000 });
        await plan.rejectButton.click();

        // The rejection returns the associate to the store surface. Waiting for
        // that is what makes the absence below an observation rather than a
        // race: the round trip the approval branch would have raised a ticket
        // on has completed.
        await page.waitForURL(/\/$/, { timeout: 120_000 });

        expect(
            wire.count(TICKET),
            'a ticket was raised on a plan the associate rejected',
        ).toBe(0);
        await expect(plan.simulatedTicket).toHaveCount(0);

        // And the container holds no submitted ticket either — the draft, if
        // the turn made one, is still a draft. The card can only be pushed
        // after a successful write, so the surface and the store must agree.
        const ticket = await draftedTicket(page);
        expect(
            ticket.fields.status || 'none',
            'the container holds a submitted ticket for a rejected plan',
        ).not.toBe('submitted');
    });
});
