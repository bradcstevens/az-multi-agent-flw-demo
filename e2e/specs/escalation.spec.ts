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
import { PlanSurface } from '../pages/PlanSurface';
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
    const match = url.match(/\/plan\/([^/?#]+)/);
    if (!match) {
        throw new Error(`not a plan surface: ${url}`);
    }
    return match[1];
}

async function followOnEscalation(page: Page): Promise<{
    plan: PlanSurface;
    reported: string;
    session: string;
}> {
    const troubleshooting = troubleshootingTask();
    const escalation = followOnTaskFor(troubleshooting);
    const store = new StoreSurface(page);
    await store.open();
    await store.tapQuickTask(troubleshooting.name);

    const troubleshootingPlan = new PlanSurface(page);
    await troubleshootingPlan.waitForArrival(120_000);
    const originalPlanUrl = page.url();

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
        (url) => /\/plan\//.test(url.pathname) && url.href !== originalPlanUrl,
        { timeout: 120_000 },
    );

    const plan = new PlanSurface(page);
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
        await expect(plan.ticketSimulatedBadge).toBeVisible();
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
