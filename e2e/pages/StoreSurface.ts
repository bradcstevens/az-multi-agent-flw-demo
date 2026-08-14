import { Locator, Page, expect } from '@playwright/test';

import { apiEndpoint } from '../authored';
import { TransparencyRail } from './TransparencyRail';

/**
 * The store surface, as the presenter meets it: a URL, anonymous, on a shared
 * store device.
 *
 * The demonstration opens **anonymous** on purpose — the shared device is the
 * licensing argument and the setup for the sign-in beat — so this page object
 * signs nobody in and sets no header. What it drives is what a finger on a
 * screen can drive.
 */
export class StoreSurface {
    readonly rail: TransparencyRail;

    constructor(readonly page: Page) {
        this.rail = new TransparencyRail(page);
    }

    async open(): Promise<void> {
        await this.page.goto('/');
        // The Quick Tasks come from the store pack in Cosmos rather than from
        // the image, so a surface that renders without them is a deployment
        // that has not been seeded — a different failure from a cold revision,
        // and one worth saying out loud rather than timing out on a card.
        await expect(this.page.getByText('Quick tasks')).toBeVisible({
            timeout: 60_000,
        });
    }

    /**
     * The **Quick Tasks region**, and nothing else on the surface.
     *
     * Load-bearing, not tidiness. The cards are named by the store pack's card
     * titles — "Close the store" — and every plan the walkthrough has ever
     * raised is listed in the task rail beside them under the question that
     * title asks: *How do I close the store?*. An accessible-name lookup
     * matches by substring, so a page-wide one resolves to one card on a fresh
     * deployment and to twenty-one elements after twenty runs. The loop would
     * rot by being run, and it did: the beat went red on a strict-mode
     * violation while the demonstration itself was working.
     *
     * Anchored on the surface's own layout class rather than a new
     * `data-testid`, for the reason `docs/demo-validator.md` states under
     * *Selectors*: an attribute this repository has just authored is not in the
     * image that is running, so it turns "the beat is broken" into "the image
     * is old". This class has named the region since the Quick Tasks landed
     * (#26), it is plain CSS in this repository rather than a Griffel hash, and
     * `test_e2e_wiring.py` fails if the surface stops using it.
     */
    get quickTasks(): Locator {
        return this.page.locator('.home-input-quick-tasks');
    }

    /** The Quick Task card carrying a given title, by its authored name. */
    quickTask(name: string): Locator {
        return this.quickTasks.getByRole('button', { name });
    }

    /** Tap a Quick Task, which asks its authored question in one interaction. */
    async tapQuickTask(name: string): Promise<void> {
        await this.quickTask(name).click();
    }

    /**
     * The **Policy block** — the Identity boundary gate refusing, rendered
     * where the question was asked. Beat 5's, and never the Grounding panel's.
     */
    get policyBlock(): Locator {
        return this.page.getByTestId('policy-block');
    }

    /**
     * The **door in the wall** (#27), looked up *through* the refusal.
     *
     * Scoped, and that is the assertion rather than tidiness. The runbook says
     * it out loud — "it is deliberately not a separate login screen" — because
     * the closing argument is the delta between one surface and the next: the
     * same words refused, then answered, in the same place. A sign-in in the
     * header is the same demonstration with that argument removed, and a
     * page-wide lookup cannot tell the two apart.
     */
    get signInToContinue(): Locator {
        return this.policyBlock.getByTestId('sign-in-to-continue');
    }

    /**
     * Every sign-in affordance on the page, wherever it is.
     *
     * The other half of the claim above: *inside the refusal* is proved only by
     * a scoped locator that finds one **and** a page-wide one that finds no
     * more. Without this, a second button beside the refusal is invisible.
     */
    get signInAnywhere(): Locator {
        return this.page.getByTestId('sign-in-to-continue');
    }

    /** The **Personal answer** — the refused question, answered (#27). */
    get personalAnswer(): Locator {
        return this.page.getByTestId('personal-answer');
    }

    /** The header naming an associate. Absent while the device is anonymous. */
    get identityName(): Locator {
        return this.page.getByTestId('store-identity-name');
    }

    /** The header saying nobody is signed in. The refusing state. */
    get identityAnonymous(): Locator {
        return this.page.getByTestId('store-identity-user');
    }

    /** The surface saying the store assistant never reached this deployment. */
    get assistantUnavailable(): Locator {
        return this.page.getByTestId('assistant-unavailable');
    }

    /**
     * Record the words the surface asks, in the order it asks them.
     *
     * The **Mocked unlock** (#27) is the one place in the walkthrough where the
     * same question is said twice, and *"the same question, unedited"* is the
     * whole of its claim: the audience has to watch one set of words refused
     * and the identical set answered. Nothing on screen shows the question
     * twice — the refusal clears the box, and the surface deliberately re-asks
     * from the words it kept rather than from anything a presenter could
     * retype — so the only place the claim is observable is the request.
     *
     * The route is read out of the surface's own endpoint table rather than
     * written down here: these are versioned and have moved before, and a
     * renamed route would leave this watching no traffic at all and reporting
     * it as *the surface did not re-ask*.
     *
     * Started before the first tap and returned live, because a request already
     * sent cannot be recovered afterwards.
     */
    watchQuestionsAsked(): string[] {
        const route = apiEndpoint('PROCESS_REQUEST');
        const asked: string[] = [];
        this.page.on('request', (request) => {
            if (request.method() !== 'POST') return;
            if (!request.url().includes(route)) return;
            try {
                const body = request.postDataJSON() as { description?: string };
                asked.push(body?.description ?? '');
            } catch {
                // A body that is not JSON is still a question having been
                // asked, and swallowing the count would make "it did not
                // re-ask" the reading of a malformed request.
                asked.push(request.postData() ?? '');
            }
        });
        return asked;
    }
}
