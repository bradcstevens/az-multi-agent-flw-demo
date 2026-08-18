import { expect, Page, test } from '@playwright/test';

import {
    deliberateLane,
    followOnTaskFor,
    ticketNumberPattern,
    troubleshootingTask,
} from '../authored';
import {
    attemptedSteps,
    draftedTicket,
    laneTaken,
    sessionOfPlan,
} from '../backend';
import { recordRehearsal } from '../evidence';
import { ChatSurface } from '../pages/ChatSurface';
import { StoreSurface } from '../pages/StoreSurface';

/**
 * Beat 4 — the approval is the ticket being raised.
 *
 * Escalation is deliberately not a home-screen card: it continues the
 * troubleshooting conversation that supplied the ticket's context.
 */
test.afterEach(() => {
    const info = test.info();
    const metadata = (info.config.metadata ?? {}) as Record<string, string>;

    recordRehearsal({
        target: metadata.target ?? 'unknown',
        baseURL: metadata.baseURL ?? 'unknown',
        passed: info.status === info.expectedStatus,
        outcome: 'unknown',
        toolQuery: null,
        retrievalQuery: null,
        citations: [],
        agentsBilled: [],
    });
});

function planIdFrom(url: string): string {
    // The route is `/chat/:id` (ADR-025, #73) and the id in it is a Plan's,
    // which is what the escalation beat has to read back out of Cosmos.
    const match = url.match(/\/chat\/([^/?#]+)/);
    if (!match) {
        throw new Error(`not a chat surface: ${url}`);
    }
    return match[1];
}

async function followOnEscalation(page: Page): Promise<{
    plan: ChatSurface;
    reported: string;
    session: string;
}> {
    const troubleshooting = troubleshootingTask();
    const escalation = followOnTaskFor(troubleshooting);
    const store = new StoreSurface(page);
    await store.open();
    await store.tapQuickTask(troubleshooting.name);

    const troubleshootingPlan = new ChatSurface(page);
    await troubleshootingPlan.waitForArrival(120_000);
    const originalChatUrl = page.url();

    await expect(troubleshootingPlan.rehearsedReplies).toBeVisible({
        timeout: 240_000,
    });
    await troubleshootingPlan.tapRehearsedReply(troubleshooting.rehearsedReplies[0]);
    await expect
        .poll(() => attemptedSteps(page), { timeout: 60_000 })
        .not.toHaveLength(0);
    const reported = (await attemptedSteps(page))[0];
    if (!reported) {
        throw new Error('the troubleshooting record became empty after it was observed');
    }

    await expect(troubleshootingPlan.followOnTask).toBeVisible();
    await troubleshootingPlan.tapFollowOnTask(escalation.name);
    await page.waitForURL(
        (url) => /\/chat\//.test(url.pathname) && url.href !== originalChatUrl,
        { timeout: 120_000 },
    );

    const plan = new ChatSurface(page);
    return {
        plan,
        reported,
        session: await sessionOfPlan(page, planIdFrom(page.url())),
    };
}

test.describe('the escalation beat', () => {
    test('continues troubleshooting and raises a simulated ticket on approval', async ({
        page,
    }) => {
        const { plan, reported, session } = await followOnEscalation(page);

        await expect(plan.laneBadge).toContainText('Deliberate');
        expect(await laneTaken(page, session)).toBe(deliberateLane());
        await expect(plan.approveButton).toBeVisible({ timeout: 240_000 });
        await expect(plan.simulatedTicket).toHaveCount(0);

        await plan.approveButton.click();
        await expect(plan.simulatedTicket).toBeVisible({ timeout: 120_000 });
        await expect(plan.ticketNumber).toHaveText(ticketNumberPattern());
        expect((await plan.ticketFields()).steps_attempted).toContain(reported);
    });

    test('raises no ticket when the follow-on plan is rejected', async ({ page }) => {
        const { plan } = await followOnEscalation(page);

        await expect(plan.rejectButton).toBeVisible({ timeout: 240_000 });
        await plan.rejectButton.click();
        await page.waitForURL(/\/$/, { timeout: 120_000 });

        await expect(plan.simulatedTicket).toHaveCount(0);
        expect((await draftedTicket(page)).fields.status || 'none').not.toBe(
            'submitted',
        );
    });
});
