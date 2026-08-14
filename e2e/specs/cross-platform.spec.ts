import { expect, test } from '@playwright/test';

import { quickTaskNamed, rehearsedHit } from '../authored';
import { PlanSurface } from '../pages/PlanSurface';
import { StoreSurface } from '../pages/StoreSurface';

/**
 * Beat 1 — the cross-platform hop.
 *
 * The claim the whole demonstration rests on: one question, asked on a Foundry
 * orchestrated surface, answered by a **Copilot Studio** agent out of
 * **Dataverse**, with the document it came from named on screen. If this beat
 * does not work, nothing else in the walkthrough is worth showing.
 *
 * What is graded is the **provenance**, never the prose. A fluent answer is
 * precisely what an ungrounded fallback produces, so an assertion on wording
 * would pass in exactly the case that matters — and go red on a paraphrase in
 * the case that does not.
 */

/** Where the platform badge's own attribute must land (`sop/provenance.py`). */
const SOP_PLATFORM = 'Copilot Studio';
const SOP_SOURCE = 'Dataverse';

test.describe('the cross-platform hop', () => {
    test('is answered by Copilot Studio out of Dataverse, citing the corpus', async ({
        page,
    }) => {
        const hit = rehearsedHit();
        const task = quickTaskNamed(hit.quickTask);

        // The corpus and the store pack are authored in different directories
        // by different tools, so the walkthrough's opening tap is only the
        // rehearsed hit for as long as they agree. Checked here rather than
        // assumed, because a drifted prompt asks a question the corpus never
        // guaranteed an answer to and the beat decays into the honest miss.
        expect(task.prompt).toBe(hit.question);

        const store = new StoreSurface(page);
        await store.open();

        // Nothing has been asked, so the panel asserts nothing. This is the
        // state the honest miss and a swallowed push both have to be
        // distinguishable from, so the beat starts by observing it.
        await expect(store.rail.groundingEmpty).toBeVisible();

        await store.tapQuickTask(task.name);

        const plan = new PlanSurface(page);
        await plan.waitForArrival(120_000);

        // The hop itself. The badge appears only when the backend emitted
        // `source_used`, which it does not do for a failed Direct Line reply —
        // so a fixed failure message wearing the agent's voice times out here
        // rather than passing.
        await plan.rail.waitForGrounding(240_000);
        expect(await plan.rail.platformNamed()).toBe(SOP_PLATFORM);
        await expect(plan.rail.route).toContainText(SOP_SOURCE);
        expect(await plan.rail.retrievalQuery()).toBe(hit.question);
        await test.info().attach('sop-tool-query', {
            body: JSON.stringify(
                {
                    toolQuery: await plan.rail.toolQuery(),
                    retrievalQuery: await plan.rail.retrievalQuery(),
                },
                null,
                2,
            ),
            contentType: 'application/json',
        });

        // The citation's document identifier, read out of the corpus manifest
        // rather than written down here. `[rehearsed_hit]` names the SOP-NNN
        // that answers the question precisely so that renaming the document
        // away goes red instead of quietly becoming an honest miss.
        //
        // The honest miss is checked first, and separately, because it is the
        // one way this beat fails that is not the harness's fault and not a
        // slow render: the SOP agent searched and found nothing for a question
        // the corpus rehearses. Asserting only on the citation reports that as
        // an empty string, which reads like a broken selector.
        expect(
            await plan.rail.honestMiss.isVisible(),
            'the Grounding panel reported an honest miss for the rehearsed ' +
                'question: the SOP agent searched Dataverse and found no ' +
                'matching procedure. The hop worked and the retrieval did not, ' +
                'so this is the demonstration being unreliable rather than the ' +
                'harness being wrong. Re-run it; if it persists, the corpus or ' +
                "the agent's index has drifted.",
        ).toBe(false);

        const cited = await plan.rail.citedDocuments();
        expect(cited.join(' | ')).toContain(hit.docId);

        // And the answer arrived — in the agent's own turn, not merely
        // somewhere on a page that also holds a turn from an agent this beat
        // never asked. This is the whole of what is asserted about anything a
        // model wrote: that there were words, and that they were not just the
        // presenter's own question read back.
        const turn = plan.latestAgentTurn;
        await expect(turn).toBeVisible({ timeout: 60_000 });
        const spoken = await plan.spokenIn(turn);
        expect(
            spoken.filter((paragraph) => paragraph !== hit.question),
        ).not.toHaveLength(0);
    });
});
