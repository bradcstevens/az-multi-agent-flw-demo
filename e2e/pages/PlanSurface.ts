import { Locator, Page, expect } from '@playwright/test';

import { PresenterChord, presenterAlertEndpoint } from '../authored';
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

    /** The **Presenter alerts** on this surface, in the order they arrived. */
    get presenterAlerts(): Locator {
        return this.page.getByTestId('presenter-alert');
    }

    /**
     * Press the hidden chord the way the presenter does: real keys.
     *
     * The chord is matched on `event.code` rather than `event.key` — with Alt
     * held, several layouts compose a different character entirely — so this
     * presses the *physical* key, which is what `presenterChord()` resolves the
     * presenter's own label into.
     */
    async pressPresenterChord(chord: PresenterChord): Promise<void> {
        await this.page.keyboard.press(chord.press);
    }

    /**
     * Dispatch the chord as a **synthetic** keydown, carrying modifiers no
     * keyboard automation can produce.
     *
     * Two of the chord's rules are reachable no other way. `repeat` is set by
     * the platform's own auto-repeat and Playwright's keyboard never sets it;
     * `AltGraph` is a modifier state a European layout reports alongside
     * Ctrl+Alt and that no key name asks for. Both are why the chord has the
     * guards it has.
     *
     * The event goes to `window`, which is where `usePresenterChord` listens,
     * and it is dispatched into the **running image** — which is the whole
     * point of asserting here what a jsdom predicate already asserts.
     */
    async dispatchPresenterChord(
        chord: PresenterChord,
        init: { repeat?: boolean; altGraph?: boolean } = {},
    ): Promise<void> {
        await this.page.evaluate(
            ([keyChord, extra]) => {
                window.dispatchEvent(
                    new KeyboardEvent('keydown', {
                        code: keyChord.code,
                        key: keyChord.code.replace(/^Key/, ''),
                        ctrlKey: keyChord.ctrlKey,
                        altKey: keyChord.altKey,
                        shiftKey: keyChord.shiftKey,
                        repeat: extra.repeat ?? false,
                        modifierAltGraph: extra.altGraph ?? false,
                        bubbles: true,
                        cancelable: true,
                    }),
                );
            },
            [chord, init] as const,
        );
    }

    /**
     * Record every firing of the hidden chord's route, as it happens.
     *
     * What the chord *did*, rather than what the surface then showed. The two
     * come apart in the direction that matters: the backend answers 404 when
     * nobody is connected and the hook swallows it, so a chord that fired and
     * was not delivered looks on screen exactly like a chord that never fired.
     * Only the request can say a suppressed chord was suppressed **here**
     * rather than lost somewhere in the push.
     */
    watchPresenterAlertsFired(): string[] {
        const route = presenterAlertEndpoint();
        const fired: string[] = [];
        this.page.on('request', (request) => {
            if (request.method() !== 'POST') return;
            if (!request.url().includes(route)) return;
            fired.push(request.url());
        });
        return fired;
    }
}
