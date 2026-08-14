import { Locator, Page, expect } from '@playwright/test';

/**
 * The **Transparency rail** — the Grounding panel and the Token meter.
 *
 * A page object rather than a set of selectors because the rail is on *both*
 * surfaces (the refusal happens where the question is asked and the answers
 * happen on the plan surface), so every beat reads it and none of them owns it.
 *
 * Everything here is a **deterministic transparency signal**. Nothing on this
 * object returns anything a model wrote: the platform is a backend constant,
 * the citation names are the SOP agent's own document metadata, and the meter's
 * rows are arithmetic. A validator that asserted a generated sentence would go
 * red on a paraphrase while the demonstration was fine, and a validator nobody
 * trusts is one nobody reads on the morning it matters.
 */
/**
 * One row of the Token meter, exactly as the panel rendered it.
 *
 * Every number is a string on purpose. See `meterRows()`.
 */
export interface MeterRowRead {
    agent: string;
    /** Which meter this row is on: `tokens`, `credits` or `refused`. */
    billing: string | null;
    calls: string;
    tokens: string;
    credits: string;
}

export class TransparencyRail {
    readonly root: Locator;

    constructor(private readonly page: Page) {
        this.root = page.getByTestId('transparency-rail');
    }

    get groundingPanel(): Locator {
        return this.page.getByTestId('grounding-panel');
    }

    /**
     * The platform badge — the Grounding panel's headline, and the claim R6
     * exists to make: *this one answer left Foundry*.
     */
    get platform(): Locator {
        return this.page.getByTestId('grounding-platform');
    }

    /** `Foundry orchestrator → Copilot Studio → Dataverse`. */
    get route(): Locator {
        return this.page.getByTestId('grounding-route');
    }

    /** The documents the answer came back with. */
    get citations(): Locator {
        return this.page.getByTestId('grounding-citations');
    }

    /**
     * The rehearsed out-of-corpus probe's own state: the route, and *nothing
     * came back*. Deliberately distinct from an empty panel, which is what a
     * swallowed push looks like.
     */
    get honestMiss(): Locator {
        return this.page.getByTestId('grounding-miss');
    }

    /** No `source_used` has arrived. The panel asserts nothing at all. */
    get groundingEmpty(): Locator {
        return this.page.getByTestId('grounding-empty');
    }

    get tokenMeter(): Locator {
        return this.page.getByTestId('token-meter-panel');
    }

    /**
     * Wait for a `source_used` signal to reach the panel.
     *
     * The wait is on the **platform badge**, not on prose: the badge appears
     * only when the backend emitted `source_used`, which it does not do for a
     * failed Direct Line reply. So this waits for the hop, and a hop that never
     * happened times out rather than passing on a fluent fallback.
     */
    async waitForGrounding(timeout: number): Promise<void> {
        await expect(this.platform).toBeVisible({ timeout });
    }

    /** The platform the panel names, as the badge's own data attribute. */
    async platformNamed(): Promise<string | null> {
        return this.platform.getAttribute('data-platform');
    }

    /** The query the orchestrator actually sent to the SOP tool. */
    async toolQuery(): Promise<string | null> {
        return this.groundingPanel.getAttribute('data-tool-query');
    }

    /** The query the SOP agent used to retrieve from the corpus. */
    async retrievalQuery(): Promise<string | null> {
        return this.groundingPanel.getAttribute('data-retrieval-query');
    }

    /**
     * Which agents the cost table billed for this turn.
     *
     * The measurement that told the three routing fixes apart (#54). The
     * outcome alone says the beat came back as a clarification; this says
     * *which specialist produced it*, and — on a green run — whether the one
     * that used to hijack the answer ran at all. Read off the panel the
     * presenter is looking at, so it is the same claim they can see.
     */
    async agentsBilled(): Promise<string[]> {
        const names = this.tokenMeter.getByTestId('meter-agent');
        if ((await names.count()) === 0) {
            return [];
        }
        return (await names.allInnerTexts()).map((name) => name.trim());
    }

    /** The document names the answer cited, in the order they came back. */
    async citedDocuments(): Promise<string[]> {
        if ((await this.citations.count()) === 0) {
            return [];
        }
        const names = await this.citations.locator('li').allInnerTexts();
        return names.map((name) => name.split('\n')[0].trim());
    }

    /** Nothing has been spent yet: the meter describes itself. */
    get meterEmpty(): Locator {
        return this.page.getByTestId('meter-empty');
    }

    /**
     * Every row on the Token meter, as the panel rendered them.
     *
     * The cells are read as **text**, never parsed into numbers, because the
     * distinction the meter exists to make is a rendering rule: `null` renders
     * `—` for a cost nobody reported and `0` renders `0` for a cost known to
     * be nothing (`models/meter.ts`). Parsing collapses the two — `Number('—')`
     * is `NaN` and `Number('')` is `0` — and a beat asserting a *measured* zero
     * against a parsed one is asserting nothing at all.
     *
     * A row is identified by the meter it is on rather than by the name in its
     * first column: the billing is the model's own field and the name is copy.
     */
    async meterRows(): Promise<MeterRowRead[]> {
        const rows = this.tokenMeter.locator('tbody tr');
        const read: MeterRowRead[] = [];
        const count = await rows.count();
        for (let index = 0; index < count; index += 1) {
            const row = rows.nth(index);
            const cell = async (testId: string) =>
                (await row.getByTestId(testId).innerText()).trim();
            read.push({
                agent: await cell('meter-agent'),
                billing: await row.getAttribute('data-billing'),
                calls: await cell('meter-calls'),
                tokens: await cell('meter-tokens'),
                credits: await cell('meter-credits'),
            });
        }
        return read;
    }
}
