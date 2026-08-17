import { expect, test } from '@playwright/test';

import { agentHoldingToolbox, agentKey, quickTasks } from '../authored';
import { ChatSurface } from '../pages/ChatSurface';
import { StoreSurface } from '../pages/StoreSurface';

/**
 * Beat 8 — the fourth specialist.
 *
 * An agreed shift-swap transaction, answered by `WorkforceAgent`, so the
 * audience watches four specialists being chosen between rather than three.
 * [ADR-017](../../docs/ADR/017-workforce-agent-answers-process-never-record.md)
 * still draws the boundary: this agent follows a process and never reads an
 * individual's record, which stays the **Identity boundary gate**'s business.
 *
 * Two things are graded, and neither is prose:
 *
 * - the transaction was **admitted**. The gate's similarity tier is a live model
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

/**
 * The tool domain that makes an agent *this* specialist — the MCP server's own
 * `workforce` domain, which is what ADR-017 gave the fourth participant and the
 * one thing about it that a rename cannot move.
 *
 * Everything else about the agent is read off the pack from here: the roster
 * panel shows the pack's own name, and the **Token meter** shows the
 * **Agent display name**, which is that name with the suffix the column heading
 * already carries taken off (#70) — so the cost table is read through
 * `agentKey`, which compares the two without the presentation either of them
 * applies. This spec pinned `WorkforceAgent` against the meter's inner text,
 * which the backend humanises to `Workforce Agent` before the browser ever sees
 * it: an assertion that could not pass against any deployment, and nothing said
 * so because no workflow runs the validator.
 */
const WORKFORCE_TOOLBOX = 'workforce';

test.describe('the fourth specialist', () => {
    test('reviews the agreed shift swap, and the meter says the fourth specialist answered it', async ({
        page,
    }) => {
        const specialist = agentHoldingToolbox(WORKFORCE_TOOLBOX);

        const task = quickTasks().find((card) => card.id === SHIFT_SWAP_TASK);
        expect(
            task,
            `the store pack authors no Quick Task ${SHIFT_SWAP_TASK}: the ` +
                'beat has no card to tap',
        ).toBeTruthy();

        // The declaration earns the Reviewable plan. It is read from the pack,
        // not repeated here, so a transaction that loses approval goes red.
        expect(task!.lane).toBe('deliberate');

        const store = new StoreSurface(page);
        await store.open();

        // The roster, before anything is asked. The **Silent agent skip**
        // drops an agent whose model the environment does not allow with a
        // warning nobody reads, and the symptom is a specialist that never
        // speaks. Checked here so a short roster is reported as a short roster
        // rather than as a beat that timed out.
        await expect(
            store.rail.rosterMember(specialist.name),
            `${specialist.name} is not on the roster the surface shows. The ` +
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

        const plan = new ChatSurface(page);
        await plan.waitForArrival(120_000);
        await expect(plan.laneBadge).toContainText('Deliberate');
        await expect(plan.approveButton).toBeVisible({ timeout: 240_000 });

        const people = task!.planSteps
            .map((step) => step.assignee)
            .filter(
                (assignee): assignee is { kind?: string; name: string } =>
                    assignee?.kind === 'person' && typeof assignee.name === 'string',
            );
        expect(people.map((person) => person.name)).toHaveLength(3);
        for (const person of people) {
            await expect(plan.conversation.getByText(person.name, { exact: false })).toBeVisible();
        }

        await plan.approveButton.click();

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
            billed.map(agentKey),
            `the turn billed ${billed.join(', ') || 'nobody'}, and the beat ` +
                `is watching for ${specialist.name}. The question was ` +
                'answered by somebody other than the fourth specialist, ' +
                'which is the manager routing an HR process question into the ' +
                "store's own procedures — a fluent answer from the wrong " +
                'agent, and the reason this beat grades the cost table rather ' +
                'than the reply.',
        ).toContain(agentKey(specialist.name));

        // And named once. `agentKey` above answers *which* specialist was
        // billed, deliberately without the presentation either side applies —
        // but that tolerance is what would let the meter go back to repeating
        // the column heading in every cell (#70) with this beat still green.
        // So the presentation is asserted separately, and only the half #70
        // decided: the cell must not end in the noun the pack's own name ends
        // in, which is the suffix the heading already carries. Nothing here
        // restates how the backend humanises or cases a name — that is the
        // spelling `agentKey` exists not to have a fourth opinion about.
        const suffix = /\s*agents?$/i;
        if (suffix.test(specialist.name)) {
            const billedAs = billed.find(
                (cell) => agentKey(cell) === agentKey(specialist.name),
            );
            expect(
                billedAs,
                `the cost table bills the specialist as ${JSON.stringify(billedAs)}, ` +
                    `repeating the noun its own column heading carries. The pack ` +
                    `names it ${JSON.stringify(specialist.name)} and the meter is the ` +
                    'one panel that drops the suffix (#70) — the roster panel and ' +
                    'the prose keep it. A meter reading it back means the panel ' +
                    'stopped going through the shared display-name helper, and the ' +
                    'name no longer fits the column.',
            ).not.toMatch(suffix);
        }

        // And words arrived. That is the whole of what is asserted about
        // anything a model wrote.
        expect([...said.spoken, ...said.asked]).not.toHaveLength(0);
    });
});
