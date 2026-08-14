import { expect, test } from '@playwright/test';

import { quickTaskNamed, rehearsedHit } from '../authored';
import { outcomeOf, recordRehearsal } from '../evidence';
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

/**
 * What this run saw, for the evidence ledger (#54).
 *
 * Filled the moment the Grounding panel arrives rather than as each assertion
 * needs it, so a beat that goes red on the *first* assertion still records what
 * the panel said. Evidence gathered only up to the point of failure attributes
 * every failure to whatever is checked first.
 */
interface Observed {
    grounded: boolean;
    honestMiss: boolean;
    toolQuery: string | null;
    retrievalQuery: string | null;
    citations: string[];
    /**
     * Whether the visible turn asked the presenter a question back.
     *
     * The failure mode a grounded run can still have, and the one that looked
     * like a broken selector until it was recorded (#54): the SOP answer is
     * retrieved and cited in the Grounding panel while the conversation shows
     * the Troubleshooting Agent asking *"What is stopping Store 223 from
     * closing right now?"*. Everything about the hop worked; the presenter is
     * still standing in front of a question instead of an answer.
     */
    clarified: boolean;
}

let observed: Observed;

test.beforeEach(() => {
    observed = {
        grounded: false,
        honestMiss: false,
        toolQuery: null,
        retrievalQuery: null,
        citations: [],
        clarified: false,
    };
});

/**
 * One line per run, passing runs included.
 *
 * The intermittency this beat exists to catch is a property of a *sequence* of
 * runs, and the run in front of you cannot show it. `scripts/sop-rehearsal.sh`
 * reads the ledger back for the ten-consecutive-run proof and for the
 * attribution — which layer a red run implicates — and neither is answerable
 * from a green run's silence.
 */
test.afterEach(async () => {
    const info = test.info();
    const metadata = (info.config.metadata ?? {}) as Record<string, string>;
    recordRehearsal({
        target: metadata.target ?? 'unknown',
        baseURL: metadata.baseURL ?? 'unknown',
        passed: info.status === info.expectedStatus,
        outcome: outcomeOf(observed),
        toolQuery: observed.toolQuery,
        retrievalQuery: observed.retrievalQuery,
        citations: observed.citations,
    });
});

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
        //
        // Everything the panel says is read here, in one place, the moment it
        // says it: the whole of `source_used` arrives in one WebSocket frame
        // and renders in one pass, and reading it as each assertion needs it
        // would mean a run that failed the *first* assertion recorded nothing
        // about the rest — attributing every failure to whatever is checked
        // first.
        try {
            await plan.rail.waitForGrounding(270_000);
            observed.grounded = true;
            observed.toolQuery = await plan.rail.toolQuery();
            observed.retrievalQuery = await plan.rail.retrievalQuery();
            observed.honestMiss = await plan.rail.honestMiss.isVisible();
            observed.citations = await plan.rail.citedDocuments();
        } finally {
            await test.info().attach('sop-tool-query', {
                body: JSON.stringify(observed, null, 2),
                contentType: 'application/json',
            });
        }
        const { retrievalQuery, toolQuery } = observed;
        expect(await plan.rail.platformNamed()).toBe(SOP_PLATFORM);
        await expect(plan.rail.route).toContainText(SOP_SOURCE);

        // The retrieval query is **evidence**, and it is graded as the
        // invariant the backend guarantees rather than as a sentence.
        //
        // `_retrieval_query` is an *input alias, not an answer fallback*: it
        // rewrites the orchestrator's question to the corpus's own wording when
        // it recognises that question verbatim, and otherwise passes it
        // through. So exactly two values are correct here, and a third would
        // mean the backend answered from somewhere this beat never asked.
        //
        // What must **not** be asserted is that the alias fired. The
        // orchestrator writes the tool call, its wording is model prose, and
        // this file's governing rule — stated in `docs/demo-validator.md` — is
        // that model prose is asserted only to have arrived. Requiring the
        // corpus wording requires the orchestrator to have phrased itself in
        // one of a handful of rehearsed ways; it reported a run where the hop,
        // the route and SOP-102 all landed as a failed beat.
        // The evidence arrived at all. `getAttribute` returns null for a panel
        // that carries no such attribute, and the model maps a field the
        // backend omits to `''` — and both satisfy "one of two" below for
        // free. Without these two lines the beat passes against a deployment
        // that cannot say what it retrieved against.
        expect(toolQuery).toBeTruthy();
        expect(retrievalQuery).toBeTruthy();
        expect([hit.question, toolQuery]).toContain(retrievalQuery);

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
            observed.honestMiss,
            'the Grounding panel reported an honest miss for the rehearsed ' +
                'question: the SOP agent searched Dataverse and found no ' +
                'matching procedure. The hop worked and the retrieval did not, ' +
                'so this is the demonstration being unreliable rather than the ' +
                'harness being wrong. Re-run it; if it persists, the corpus or ' +
                "the agent's index has drifted.",
        ).toBe(false);

        expect(observed.citations.join(' | ')).toContain(hit.docId);

        // And the answer arrived — in the agent's own turn, not merely
        // somewhere on a page that also holds a turn from an agent this beat
        // never asked. This is the whole of what is asserted about anything a
        // model wrote: that there were words, and that they were not just the
        // presenter's own question read back.
        const turn = plan.latestAgentTurn;
        await expect(turn).toBeVisible({ timeout: 120_000 });
        const said = await plan.saidIn(turn);
        observed.clarified = said.asked.length > 0 && said.spoken.length === 0;

        // A question asked back is failed *by name*, before the emptiness it
        // also produces is reported (#54). The presenter taps "How do I close
        // the store?" and the surface asks "What is stopping Store 223 from
        // closing right now?" — while the Grounding panel behind it holds the
        // answer, cited. Every assertion above this line passes on that run,
        // so without this one the beat fails on "no paragraph rendered", which
        // reads as a slow surface or a broken selector and sends the reader to
        // the harness. It sent one there for a day.
        expect(
            observed.clarified,
            'the agent asked the presenter a question back instead of ' +
                `answering: ${said.asked.join(' / ')}. The SOP hop itself ` +
                'worked — the Grounding panel named Copilot Studio and cited ' +
                'the corpus — so this is the orchestrator routing a procedure ' +
                'lookup into a troubleshooting clarification, not a retrieval ' +
                'failure. See docs/sop-rehearsal.md.',
        ).toBe(false);

        expect(
            said.spoken.filter((paragraph) => paragraph !== hit.question),
        ).not.toHaveLength(0);
    });
});
