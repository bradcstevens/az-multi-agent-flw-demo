import { Locator, Page, expect } from '@playwright/test';

import { TransparencyRail } from './TransparencyRail';

/**
 * The chat surface — where the answer, the approval gate and the ticket land,
 * and where the **Transparency rail** sits beside them.
 *
 * The prose is the one thing on this object that a model wrote, and the only
 * thing asserted about it is that it **arrived**. Everything a beat actually
 * grades is read off the rail.
 */
export class ChatSurface {
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

    /** The static-label disclosure that reveals navigation without reflowing the answer. */
    get chatHistoryToggle(): Locator {
        return this.page.getByRole('button', { name: 'Chat history' });
    }

    /** New chat stays in the content toolbar, whether chat history is open or closed. */
    get newChatButton(): Locator {
        return this.page.getByRole('button', { name: 'New chat' });
    }

    /** Chat history is a modal Panel drawer, not a column beside the conversation. */
    get chatHistoryDrawer(): Locator {
        return this.page.getByRole('dialog');
    }

    async openChatHistory(): Promise<void> {
        await this.chatHistoryToggle.click();
        await expect(this.chatHistoryDrawer).toBeVisible();
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

    /**
     * What one turn holds: what the agent **said**, and what it **asked**.
     *
     * `spokenIn` waits for a paragraph, which is right when a paragraph is
     * coming. A clarification is not: it renders as a list, so waiting for a
     * paragraph waits out the full timeout and then reports "no paragraph
     * rendered" — a slow-surface story for a turn that arrived promptly and
     * asked a question (#54). This waits for **either**, and says which came.
     *
     * Still returned rather than asserted, for `spokenIn`'s reason: the words
     * are model prose, and what a spec may say about them is narrow.
     */
    async saidIn(
        turn: Locator,
        timeout = 60_000,
    ): Promise<{ spoken: string[]; asked: string[] }> {
        const clean = (texts: string[]) =>
            texts.map((text) => text.trim()).filter(Boolean);

        await turn
            .locator('p, li')
            .first()
            .waitFor({ state: 'visible', timeout });

        return {
            spoken: clean(await turn.locator('p').allInnerTexts()),
            asked: clean(await turn.locator('li').allInnerTexts()),
        };
    }

    /** Wait for the surface the question navigated to. */
    async waitForArrival(timeout: number): Promise<void> {
        // `/chat/<plan id>` since #73: a Chat is the unit of the surface
        // (ADR-025) while the id in the route is still a Plan's.
        await this.page.waitForURL(/\/chat\//, { timeout });
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

    /** The authored task that continues the conversation's initial Quick Task. */
    get followOnTask(): Locator {
        return this.page.getByTestId('follow-on-task');
    }

    /** The approval gate on a Deliberate-lane plan. */
    get approveButton(): Locator {
        return this.page.getByRole('button', { name: 'Approve Task Plan' });
    }

    /**
     * The **Reviewable plan**'s own step list.
     *
     * The one region where a person's name means *the plan reaches this
     * person*. The conversation column is not: it holds the request line and
     * the prose too, so a name looked up there resolves to several elements and
     * fails the beat in strict mode — a red run that says nothing about the
     * surface.
     */
    get reviewablePlanSteps(): Locator {
        return this.page.getByTestId('reviewable-plan-steps');
    }

    /** The other half of the approval gate. */
    get rejectButton(): Locator {
        return this.page.getByRole('button', { name: 'Cancel', exact: true });
    }

    /** The **Simulated ticket** an approved escalation raises (#50's beat). */
    get simulatedTicket(): Locator {
        return this.page.getByTestId('simulated-ticket');
    }

    /** The simulated identifier an associate can read from the ticket card. */
    get ticketNumber(): Locator {
        return this.page.getByTestId('simulated-ticket-id');
    }

    /** The badge that makes the ticket's simulated nature explicit. */
    get ticketSimulatedBadge(): Locator {
        return this.simulatedTicket.getByTestId('simulated-badge');
    }

    /** The authored choices for the clarification that is currently pending. */
    async rehearsedReplyLabels(): Promise<string[]> {
        return this.rehearsedReplies.getByRole('button').allInnerTexts();
    }

    /** Answer the current clarification through its authored one-tap choice. */
    async tapRehearsedReply(answer: string): Promise<void> {
        await this.rehearsedReplies
            .getByRole('button', { name: answer })
            .click();
    }

    /** Continue the conversation with its authored follow-on task. */
    async tapFollowOnTask(name: string): Promise<void> {
        await this.followOnTask.getByRole('button', { name }).click();
    }

    /** The ticket's deterministic field rows, keyed by TKT-001 field name. */
    async ticketFields(): Promise<Record<string, string>> {
        const rows = this.simulatedTicket.locator('.simulated-ticket__row');
        const fields: Record<string, string> = {};
        for (let index = 0; index < (await rows.count()); index += 1) {
            const row = rows.nth(index);
            fields[(await row.locator('dt').innerText()).trim()] = (
                await row.locator('dd').innerText()
            ).trim();
        }
        return fields;
    }
}
