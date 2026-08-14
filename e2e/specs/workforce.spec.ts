import { expect, test } from '@playwright/test';

import { quickTasks } from '../authored';
import { PlanSurface } from '../pages/PlanSurface';
import { StoreSurface } from '../pages/StoreSurface';

/**
 * Beat 8 — the fourth specialist.
 *
 * An **HR process question** — how an employment task is performed — answered
 * by `WorkforceAgent`, so the audience watches four specialists being chosen
 * between rather than three. [ADR-017](../../docs/ADR/017-workforce-agent-answers-process-never-record.md)
 * is why it exists and where its boundary is drawn: this agent answers *how a
 * thing is done* and never *an individual's record*, which stays the
 * **Identity boundary gate**'s business and is still answered with no agent at
 * all.
 *
 * Two things are graded, and neither is prose:
 *
 * - the question was **admitted**. The gate's similarity tier is a live model
 *   call, and ADR-017 records the risk out loud: a process question phrased
 *   near the personal probes can be refused on stage, on the run that matters.
 *   The **Guardrail corpus** measures that offline; this watches it live.
 * - the **fourth specialist** answered it, read off the cost table rather than
 *   off the reply. The manager choosing `ShiftTasksAgent` instead is the
 *   failure this beat exists to catch, and it produces a perfectly fluent
 *   answer — so an assertion on the wording would pass in exactly the case
 *   that matters.
 *
 * What is deliberately **not** asserted is that the answer quotes `WF-401`.
 * The workforce library is reached as a tool with no `source_used` behind it,
 * so the only place its identifier appears is inside prose a model wrote, and
 * `docs/demo-validator.md`'s rule is that model prose is asserted only to have
 * arrived. The limit is stated in `docs/store-content-pack.md`: this beat
 * proves the routing, not the grounding.
 */

/** The Quick Task the store pack authors for this beat. */
const SHIFT_SWAP_TASK = 'task-223-shift-swap';

/** The specialist the roster adds, and the meter has to bill. */
const WORKFORCE_AGENT = 'WorkforceAgent';

test.describe('the fourth specialist', () => {
    test('answers the HR process question, and the meter says it was the one that did', async ({
        page,
    }) => {
        const task = quickTasks().find((card) => card.id === SHIFT_SWAP_TASK);
        expect(
            task,
            `the store pack authors no Quick Task ${SHIFT_SWAP_TASK}: the ` +
                'beat has no card to tap',
        ).toBeTruthy();

        // The lane is metadata on the card, and it is asserted here because
        // the walkthrough's claim about this beat is that it is *fast* — an
        // approval step in front of a procedure lookup is the demonstration
        // getting slower for a reason the audience cannot see.
        expect(task!.lane).toBe('fast');

        const store = new StoreSurface(page);
        await store.open();

        // The roster, before anything is asked. The **Silent agent skip**
        // drops an agent whose model the environment does not allow with a
        // warning nobody reads, and the symptom is a specialist that never
        // speaks. Checked here so a short roster is reported as a short roster
        // rather than as a beat that timed out.
        await expect(
            store.rail.rosterMember(WORKFORCE_AGENT),
            `${WORKFORCE_AGENT} is not on the roster the surface shows. The ` +
                'upload can succeed and the agent factory still skip it with ' +
                'only a warning when its model is outside SUPPORTED_MODELS — ' +
                'run `python -m store_pack roster` against the deployment.',
        ).toBeVisible({ timeout: 60_000 });

        await store.tapQuickTask(task!.name);

        // The boundary, from the side ADR-017 had to argue for. A refusal
        // renders as the **Policy block** where the question was asked, so it
        // is watched for by name: without this the beat would wait out the
        // full arrival timeout and report a slow surface for a gate that
        // answered immediately and said no.
        await expect(
            store.policyBlock,
            'the Identity boundary gate refused the shift-swap question. It ' +
                'trips no keyword, so this is the similarity tier — the live ' +
                'model call ADR-017 named as the risk. Re-run the Guardrail ' +
                'corpus against the embedding deployment: the beat is not ' +
                'safe to show until it separates again.',
        ).toBeHidden();

        const plan = new PlanSurface(page);
        await plan.waitForArrival(120_000);

        const turn = plan.latestAgentTurn;
        await expect(turn).toBeVisible({ timeout: 180_000 });
        const said = await plan.saidIn(turn);

        // Read once, the moment the turn lands, and attached whether or not
        // what follows passes — the hop's beat learned that a run failing its
        // first assertion otherwise records nothing about the rest.
        const billed = await plan.rail.agentsBilled();
        await test.info().attach('workforce-beat', {
            body: JSON.stringify({ billed, said }, null, 2),
            contentType: 'application/json',
        });

        expect(
            billed,
            `the turn billed ${billed.join(', ') || 'nobody'}. The question ` +
                'was answered by somebody other than the fourth specialist, ' +
                'which is the manager routing an HR process question into the ' +
                "store's own procedures — a fluent answer from the wrong " +
                'agent, and the reason this beat grades the cost table rather ' +
                'than the reply.',
        ).toContain(WORKFORCE_AGENT);

        // And words arrived. That is the whole of what is asserted about
        // anything a model wrote.
        expect([...said.spoken, ...said.asked]).not.toHaveLength(0);
    });
});
