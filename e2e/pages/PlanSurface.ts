import { Locator, Page, expect } from '@playwright/test';

import { TransparencyRail } from './TransparencyRail';

/**
 * The plan surface — where the answer, the approval gate and the ticket land,
 * and where the **Transparency rail** sits beside them.
 *
 * The prose is the one thing on this object that a model wrote, and the only
 * thing asserted about it is that it **arrived**. Everything a beat actually
 * grades is read off the rail.
 */
export class PlanSurface {
    readonly rail: TransparencyRail;

    constructor(readonly page: Page) {
        this.rail = new TransparencyRail(page);
    }

    /**
     * The conversation column. Anchored on the shell's own layout classes,
     * which are plain CSS in this repository rather than build-time hashes.
     */
    get conversation(): Locator {
        return this.page.locator('.content .panelContent');
    }

    /**
     * One agent's turn — the message block its own name and "AI Agent" tag sit
     * in, not the whole conversation.
     *
     * Scoped, because the alternative is vacuous. Looking up the tag anywhere
     * and a paragraph anywhere and calling the pair "the answer arrived" passes
     * on a conversation where some *other* agent spoke and the one being graded
     * never did — and this deployment does exactly that: the same question has
     * been answered by the Group Chat Manager, by the Shift Tasks Agent, and
     * followed by a clarification from the Troubleshooting Agent.
     *
     * The ancestor step is structural rather than class-based on purpose. The
     * surface's classes are Griffel-generated hashes that change whenever the
     * style does; the nesting — tag text, tag, agent header, message content —
     * is the component's own shape.
     */
    get agentTurns(): Locator {
        return this.conversation
            .getByText('AI Agent', { exact: true })
            .locator('xpath=ancestor::div[2]');
    }

    /** The most recent agent turn, which is the one a beat has just provoked. */
    get latestAgentTurn(): Locator {
        return this.agentTurns.last();
    }

    /**
     * What was said in one turn, as text — waiting for the first paragraph to
     * render before reading.
     *
     * The wait is the point. The **Grounding panel** lights when the backend
     * pushed `source_used`, which is the moment the SOP agent replied, not the
     * moment the reply finished streaming into the DOM. Reading paragraphs the
     * instant the turn's container appears therefore reads an empty container
     * and calls the beat broken.
     *
     * Returned rather than asserted, because the assertion a spec is allowed to
     * make about it is narrow: that something arrived and was not empty. A
     * suite that asserted the sentence a model wrote goes red when the model
     * paraphrases and the demonstration was fine.
     */
    async spokenIn(turn: Locator, timeout = 60_000): Promise<string[]> {
        await turn.locator('p').first().waitFor({ state: 'visible', timeout });
        const texts = await turn.locator('p').allInnerTexts();
        return texts.map((text) => text.trim()).filter(Boolean);
    }

    /** Wait for the surface the question navigated to. */
    async waitForArrival(timeout: number): Promise<void> {
        await this.page.waitForURL(/\/plan\//, { timeout });
        await expect(this.rail.root).toBeVisible({ timeout });
    }

    /** The Lane the router actually took, as the badge reports it. */
    get laneBadge(): Locator {
        return this.page.getByTestId('lane-badge');
    }

    /** The one-tap answers to a Clarification (#50's beat). */
    get rehearsedReplies(): Locator {
        return this.page.getByTestId('rehearsed-replies');
    }

    /** The chips as the associate reads them, in the order they are offered. */
    async rehearsedReplyLabels(): Promise<string[]> {
        if ((await this.rehearsedReplies.count()) === 0) {
            return [];
        }
        const labels = await this.rehearsedReplies.getByRole('button').allInnerTexts();
        return labels.map((label) => label.trim()).filter(Boolean);
    }

    /** Tap one, which is the whole of the troubleshooting beat's interaction. */
    async tapRehearsedReply(reply: string): Promise<void> {
        await this.rehearsedReplies.getByRole('button', { name: reply, exact: true }).click();
    }

    /**
     * The approval gate the Deliberate lane opens.
     *
     * Located by the label the presenter reads, because the deployed image
     * carries no testid here and adding one makes the deployed target red until
     * the next roll — the confusion #48 exists to remove. The label is authored
     * in `StreamingPlanResponse.tsx` and is not anything a model wrote, so it is
     * as deterministic as an attribute would be; it is simply also visible.
     */
    get approveButton(): Locator {
        return this.page.getByRole('button', { name: 'Approve Task Plan' });
    }

    /** The other half of the same gate. Rejecting is a beat, not a cleanup. */
    get rejectButton(): Locator {
        return this.page.getByRole('button', { name: 'Cancel', exact: true });
    }

    /** The **Simulated ticket** an approved escalation raises (#50's beat). */
    get simulatedTicket(): Locator {
        return this.page.getByTestId('simulated-ticket');
    }

    /** The number an associate could read down a telephone. */
    get ticketNumber(): Locator {
        return this.page.getByTestId('simulated-ticket-id');
    }

    /** The label that says the ticket is invented, on the card that carries it. */
    get ticketSimulatedBadge(): Locator {
        return this.simulatedTicket.getByTestId('simulated-badge');
    }

    /**
     * The ticket's rows, keyed by TKT-001's own field names.
     *
     * Read off the card rather than out of the payload on purpose: what this
     * beat grades is what the associate was shown before they approved it, and
     * a payload carrying a field the card drops is a ticket nobody read.
     */
    async ticketFields(): Promise<Record<string, string>> {
        const rows = this.simulatedTicket.locator('.simulated-ticket__row');
        const fields: Record<string, string> = {};
        for (const row of await rows.all()) {
            const name = (await row.locator('dt').innerText()).trim();
            const value = (await row.locator('dd').innerText()).trim();
            fields[name] = value;
        }
        return fields;
    }
}
