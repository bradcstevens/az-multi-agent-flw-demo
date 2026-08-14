import { expect, test } from '@playwright/test';

import { boundaryProbe } from '../authored';
import { StoreSurface } from '../pages/StoreSurface';

/**
 * Beat 5 — the boundary.
 *
 * A personal question on a shared store device, refused by the **Identity
 * boundary gate**: deterministic code in the request path, before the lane
 * router and before orchestration. The presenter's line over it is *"that was
 * refused by code, before any agent ran and before a single token was
 * spent — the cheapest guardrail is the one that never reaches a model"*, and
 * both halves of that sentence are asserted here, separately, because a beat
 * can pass the first while the second quietly stopped being true.
 *
 * What makes this the most dangerous beat in the walkthrough to leave untested
 * is its failure mode: **silently answering**. A gate that stopped firing does
 * not go red anywhere — it produces a fluent, plausible, confidently wrong
 * answer about somebody's pay, on a shared device, in front of the audience
 * being asked to trust the architecture.
 */

/**
 * What the Token meter renders for a cost **nobody reported**.
 *
 * `models/meter.ts`: `null` renders `—` and `0` renders `0`, and "a refused
 * request adds nothing to the meter, and the row that proves it only proves it
 * if nothing is the only thing that looks like nothing". This beat is the only
 * place in the suite where that rule is worth a constant.
 */
const NOT_REPORTED = '—';

/** The meter the Identity boundary gate's row is on (`models/meter.ts`). */
const REFUSED = 'refused';

test.describe('the boundary', () => {
    test('refuses a personal question before any agent runs, for nothing', async ({
        page,
    }) => {
        const probe = boundaryProbe();

        const store = new StoreSurface(page);
        await store.open();

        // Nothing has been spent, and the meter says so rather than being
        // absent. The measured zero below is only a measurement if the panel
        // it lands on was already telling the truth about having no rows.
        await expect(store.rail.meterEmpty).toBeVisible();
        // Anonymous, which is the refusing state. A header naming somebody
        // here would mean a previous run's sign-in leaked into this one and
        // the question about to be asked is not the question the beat asks.
        await expect(store.identityAnonymous).toBeVisible();

        await store.tapQuickTask(probe.name);

        // Refused where the question was asked — not a toast, not the
        // Grounding panel, and not an error. A **Policy block** (ADR-014).
        await expect(store.policyBlock).toBeVisible({ timeout: 120_000 });

        // ...and no plan was raised. This is the "before any agent ran" claim
        // at its coarsest: a refusal that navigated is a refusal the
        // orchestrator had already been handed.
        expect(
            page.url(),
            'the refusal navigated to a plan, so the request reached the ' +
                'orchestrator before it was refused',
        ).not.toContain('/plan/');
        await expect(store.rail.groundingEmpty).toBeVisible();

        // The Token meter, whole. Reading only the gate's row proves the
        // refusal was recorded and assumes the rest of the table is empty —
        // and an orchestration that ran *and then* refused leaves the gate's
        // row reading a truthful zero beside agents that billed.
        const rows = await store.rail.meterRows();
        await test.info().attach('token-meter', {
            body: JSON.stringify(rows, null, 2),
            contentType: 'application/json',
        });

        expect(
            rows,
            'the Token meter billed more than the gate: ' +
                `${rows.map((row) => `${row.agent} (${row.billing})`).join(', ')}. ` +
                'The refusal is meant to happen before the lane router and ' +
                'before orchestration, so the gate should be the only row',
        ).toHaveLength(1);

        const [refusal] = rows;
        expect(refusal.billing).toBe(REFUSED);

        // The measurement itself. Two matchers per column, and neither is the
        // other: an em dash means the surface stopped telling *not reported*
        // apart from *nothing*, and a number means the gate billed something.
        // Different defects, different fixes, and one shared failure message
        // would send the reader to whichever came to mind first.
        for (const [column, value] of [
            ['tokens', refusal.tokens],
            ['credits', refusal.credits],
        ] as const) {
            expect(
                value,
                `the refusal's ${column} read as not reported. A refused ` +
                    'request is known to have cost nothing, and the panel has ' +
                    'stopped distinguishing that from a cost nobody told it ' +
                    'about — which is the distinction the row exists to make',
            ).not.toBe(NOT_REPORTED);
            expect(
                value,
                `the refusal's ${column} are not a measured zero`,
            ).toBe('0');
        }

        // It was reached, once. A row that recorded no call is a row somebody
        // rendered rather than a refusal somebody made.
        expect(refusal.calls).toBe('1');
    });
});
