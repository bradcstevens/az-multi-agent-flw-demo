import { expect, test } from '@playwright/test';

import { honestMiss, quickTaskNamed, sopProvenance } from '../authored';
import { PlanSurface } from '../pages/PlanSurface';
import { StoreSurface } from '../pages/StoreSurface';

/**
 * Beat 2 — the honest miss, on purpose.
 *
 * The presenter frames it before it happens: *Store 223 has no car wash, so
 * there is no procedure for this. I want you to see what it does when it does
 * not know.* The claim is that the assistant is **grounded, not
 * generative-with-confidence** — and it is what makes beat 1 believable, since
 * the same surface that answered SOP-102 refuses to invent this one.
 *
 * Which makes this beat's failure mode the inverse of every other one here. The
 * outcome it grades — *nothing came back* — is also what a broken deployment
 * produces. From the browser, four things look alike:
 *
 * 1. the rail did not render at all;
 * 2. the panel rendered and nothing ever reached it (**no signal**: the
 *    orchestrator did not call the SOP tool);
 * 3. the panel rendered, the SOP agent searched and honestly found nothing
 *    (**uncited**: the beat, working);
 * 4. the panel rendered and cited a document (the corpus grew a car wash
 *    procedure, and the rehearsed miss has quietly stopped being one).
 *
 * Only the third is this beat. An assertion phrased as *the citation list is
 * empty* passes on the first two, and the beat becomes a beat that cannot fail
 * for the reason it exists. So all four states are read in one pass and the
 * failure names which one happened.
 */

const { platform: SOP_PLATFORM } = sopProvenance();

/** Which of the Grounding panel's states this run actually landed in. */
interface Observed {
    /** The panel is on the page at all. */
    panelPresent: boolean;
    /** A `source_used` arrived: the platform badge is showing. */
    grounded: boolean;
    /** The panel is describing itself, because nothing reached it. */
    empty: boolean;
    /** The panel says the search came back with nothing. */
    miss: boolean;
    /** What it cited, which for this beat must be nothing. */
    citations: string[];
}

/** Which of the four the run landed in, as one line for the failure message. */
function stateOf(observed: Observed): string {
    if (!observed.panelPresent) return 'the Grounding panel is not on the page';
    if (observed.empty || !observed.grounded) {
        return (
            'the Grounding panel is empty — no source_used arrived, so the ' +
            'orchestrator never called the SOP tool'
        );
    }
    if (observed.citations.length > 0) {
        return (
            'the Grounding panel cited ' +
            `${observed.citations.join(' | ')} — the corpus now answers the ` +
            'question it was chosen for not answering'
        );
    }
    return 'the Grounding panel reported the honest miss';
}

test.describe('the honest miss', () => {
    test('says the library does not cover it, and says so on the panel', async ({
        page,
    }) => {
        const miss = honestMiss();
        const task = quickTaskNamed(miss.quickTask);

        // The corpus and the store pack are authored in different directories
        // by different tools, and this beat needs them to agree twice over:
        // the tap has to ask the question, and the question has to be the one
        // the corpus deliberately cannot answer.
        expect(task.prompt).toBe(miss.question);

        const store = new StoreSurface(page);
        await store.open();

        // The state this beat's own outcome has to be distinguishable from,
        // observed before anything is asked so that "the panel says nothing"
        // is known to be reachable on this deployment.
        await expect(store.rail.groundingEmpty).toBeVisible();

        await store.tapQuickTask(task.name);

        const plan = new PlanSurface(page);
        await plan.waitForArrival(120_000);

        // The **hop still happens** on a miss. `source_used` carries the
        // platform and the route whether or not anything came back, so waiting
        // on the badge here is waiting for the SOP agent to have answered —
        // and a run where the orchestrator never called the tool times out
        // rather than being graded as a miss it never made.
        const observed: Observed = {
            panelPresent: false,
            grounded: false,
            empty: false,
            miss: false,
            citations: [],
        };
        try {
            await plan.rail.waitForGrounding(270_000);
            observed.grounded = true;
        } finally {
            // Read whatever is there, including on the timeout above: a run
            // that never grounded still has a state worth naming, and reading
            // it only on the happy path attributes every failure to the wait.
            observed.panelPresent = await plan.rail.groundingPanel.isVisible();
            observed.empty = await plan.rail.groundingEmpty.isVisible();
            observed.miss = await plan.rail.honestMiss.isVisible();
            observed.citations = await plan.rail.citedDocuments();
            await test.info().attach('grounding-state', {
                body: JSON.stringify(observed, null, 2),
                contentType: 'application/json',
            });
        }

        // The hop, asserted the way beat 1 asserts it: the panel names the
        // platform. A miss that never left Foundry is not this beat.
        expect(observed.panelPresent, stateOf(observed)).toBe(true);
        expect(await plan.rail.platformNamed()).toBe(SOP_PLATFORM);

        // And the miss itself — **explicitly**, as the panel's own state,
        // rather than as the absence of a citation. The three ways of being
        // absent are told apart here and nowhere else in the suite.
        expect(
            observed.empty,
            `${stateOf(observed)}. The rehearsed miss is the SOP agent ` +
                'searching and finding nothing; an empty panel is nobody ' +
                'having searched. Only one of those is the beat.',
        ).toBe(false);
        expect(observed.miss, stateOf(observed)).toBe(true);
        expect(observed.citations, stateOf(observed)).toHaveLength(0);

        // And the assistant said something back. The corpus's rationale is
        // that the agent "must say plainly that it is not in the library
        // rather than improvise" — but *plainly* is the model's wording, and
        // this suite grades prose only for having arrived. A refusal that
        // renders as silence is the failure this catches; a refusal phrased
        // six different ways is not a failure at all.
        const turn = plan.latestAgentTurn;
        await expect(turn).toBeVisible({ timeout: 120_000 });
        const said = await plan.saidIn(turn);
        expect(
            [...said.spoken, ...said.asked].filter(
                (line) => line !== miss.question,
            ),
        ).not.toHaveLength(0);
    });
});
