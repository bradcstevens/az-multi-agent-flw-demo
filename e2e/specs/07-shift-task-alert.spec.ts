import { expect, test } from '@playwright/test';

import {
    presenterAlertEndpoint,
    presenterChord,
    rehearsedAlert,
    shiftTaskProbe,
} from '../authored';
import { PlanSurface } from '../pages/PlanSurface';
import { StoreSurface } from '../pages/StoreSurface';

/**
 * Beat 7 — it reaches out first.
 *
 * The presenter asks what is due this shift, lets it answer, and then presses a
 * chord nobody in the room knows about while carrying on talking. An alert
 * arrives with the conversation already finished. *"Nobody asked it anything
 * just then."*
 *
 * Two claims, and they fail independently:
 *
 * - **the assistant is not only reactive** — a message arrived unasked;
 * - **a proactive message is visibly a different object from an answer** —
 *   which is the claim the card was built for and the one that quietly stops
 *   being true. Rendered among the replies it reads as an answer to whatever
 *   was asked last, and the audience is told the assistant answered a question
 *   nobody put to it.
 *
 * The chord's two suppressions are asserted here as well as in the frontend
 * loop, and the duplication is the point rather than an oversight. `CONTEXT.md`
 * records the finding this whole suite was built on: every transparency signal
 * was dropped in the browser while 223 frontend tests were green. A predicate
 * passing in jsdom says the rule was written. Only the running image says it is
 * deployed.
 */

const chord = presenterChord();
const alert = rehearsedAlert();
const ALERT_ROUTE = presenterAlertEndpoint();

test.describe('the shift-task alert', () => {
    test('arrives unasked, and is visibly not a reply', async ({ page }) => {
        const probe = shiftTaskProbe();

        const store = new StoreSurface(page);
        const plan = new PlanSurface(page);
        const fired = plan.watchPresenterAlertsFired();

        await store.open();
        await store.tapQuickTask(probe.name);
        await plan.waitForArrival(120_000);

        // The conversation has to be **finished** before the chord. The claim
        // is "nobody asked it anything just then", and an alert that lands
        // while an answer is still streaming is an alert nobody can tell from
        // the answer. It is also what the runbook instructs: let it answer,
        // then press.
        const turn = plan.latestAgentTurn;
        await expect(turn).toBeVisible({ timeout: 270_000 });
        const said = await plan.saidIn(turn);
        expect(
            [...said.spoken, ...said.asked].filter(
                (line) => line !== probe.prompt,
            ),
        ).not.toHaveLength(0);

        // Nothing has arrived unasked yet, which is what makes the card below
        // an arrival rather than something that was already on the page.
        await expect(plan.presenterAlerts).toHaveCount(0);

        await plan.pressPresenterChord(chord);

        await expect(plan.presenterAlerts).toHaveCount(1, { timeout: 60_000 });
        const card = plan.presenterAlerts.first();

        // **An alert, not a reply.** Both signals, because they are dropped
        // separately: the role is what a screen reader hears and the message
        // kind is what the DOM says it is. A card that kept its styling and
        // lost its role is a reply that looks like an alert.
        await expect(card).toHaveRole('alert');
        await expect(card).toHaveAttribute('data-message-kind', 'alert');
        await expect(card.getByTestId('presenter-alert-kind')).toBeVisible();

        // ...and it is outside the reply stream. An alert rendered among the
        // answers satisfies every attribute above while being, on screen,
        // exactly the thing the card exists not to be.
        await expect(
            plan.agentTurns.filter({ has: page.getByTestId('presenter-alert') }),
        ).toHaveCount(0);
        await expect(card.getByText('AI Agent', { exact: true })).toHaveCount(0);

        // The words are the **server's** — chosen from a rehearsed roster, not
        // written by a model — so unlike every other reply in this walkthrough
        // they can be asserted, and they are read out of the roster rather than
        // restated. The procedure it names is the point: an alert that names no
        // document is a proactive message with nowhere to go.
        await expect(card).toContainText(alert.title);
        await expect(card).toContainText(alert.docId);
        await expect(card.getByTestId('simulated-badge').first()).toBeVisible();

        expect(fired, 'the chord did not reach its route').toHaveLength(1);

        // ------------------------------------------------------------------
        // The chord's suppressions.
        //
        // Neither can be produced by driving a real keyboard: `repeat` is set
        // by the platform's auto-repeat and `AltGraph` is a modifier state no
        // key name asks for. So both are dispatched as synthetic events — and
        // a negative asserted through a mechanism that never works proves
        // nothing at all, so the **control** goes first: the same synthetic
        // event, without either flag, must fire.
        //
        // Without it, a build that ignored synthetic keydowns — a listener
        // moved onto a React root, an `isTrusted` check added — would pass both
        // negatives for the wrong reason and go on passing after the chord
        // itself broke.
        // ------------------------------------------------------------------

        // The control is fired against a stubbed route so it leaves no second
        // card on the surface. What is being proved is that the *listener*
        // reacts, and the alert this beat is about is already on screen.
        await page.route(`**${ALERT_ROUTE}`, (route) =>
            route.fulfill({
                status: 404,
                contentType: 'application/json',
                body: JSON.stringify({ detail: 'not delivered, deliberately' }),
            }),
        );

        await plan.dispatchPresenterChord(chord);
        await expect
            .poll(() => fired.length, { timeout: 30_000 })
            .toBeGreaterThan(1);
        const afterControl = fired.length;

        // An **auto-repeat is not a press.** Holding the chord a beat too long
        // would otherwise POST an alert every repeat interval, and a stack of
        // identical cards on stage reads as a bug rather than as a beat.
        await plan.dispatchPresenterChord(chord, { repeat: true });
        await page.waitForTimeout(2_000);
        expect(
            fired,
            'the chord fired on an auto-repeat: holding it a beat too long ' +
                'POSTs an alert every repeat interval, and a stack of ' +
                'identical cards on stage reads as a bug',
        ).toHaveLength(afterControl);

        // **AltGr is not the chord.** On Windows and several European layouts
        // AltGr is reported as Ctrl+Alt, so without this guard a presenter
        // typing an ordinary accented character into the question box fires
        // the beat mid-sentence — on the borrowed laptop, in front of the room.
        await plan.dispatchPresenterChord(chord, { altGraph: true });
        await page.waitForTimeout(2_000);
        expect(
            fired,
            'the chord fired under AltGraph, which Windows and several ' +
                'European layouts report as Ctrl+Alt: the presenter types an ' +
                'accented character and the beat goes off mid-sentence',
        ).toHaveLength(afterControl);

        await page.unroute(`**${ALERT_ROUTE}`);

        // And the surface still holds exactly the one alert the presenter
        // meant to send.
        await expect(plan.presenterAlerts).toHaveCount(1);
    });
});
