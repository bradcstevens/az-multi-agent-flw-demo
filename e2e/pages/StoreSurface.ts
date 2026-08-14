import { Locator, Page, expect } from '@playwright/test';

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

    /** The surface saying the store assistant never reached this deployment. */
    get assistantUnavailable(): Locator {
        return this.page.getByTestId('assistant-unavailable');
    }
}
