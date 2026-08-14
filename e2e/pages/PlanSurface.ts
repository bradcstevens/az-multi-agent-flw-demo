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

    /** The **Simulated ticket** an approved escalation raises (#50's beat). */
    get simulatedTicket(): Locator {
        return this.page.getByTestId('simulated-ticket');
    }
}
