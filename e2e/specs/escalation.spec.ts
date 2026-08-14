import { expect, test } from '@playwright/test';

import { followOnTaskFor, troubleshootingTask } from '../authored';
import { attemptedSteps } from '../backend';
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

test.describe('the escalation beat', () => {
    test('continues troubleshooting and raises a simulated ticket on approval', async ({
        page,
    }) => {
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
        await troubleshootingPlan.tapRehearsedReply(
            troubleshooting.rehearsedReplies[0],
        );
        await expect
            .poll(() => attemptedSteps(page), { timeout: 60_000 })
            .not.toHaveLength(0);
        const reported = (await attemptedSteps(page))[0];

        await expect(troubleshootingPlan.followOnTask).toBeVisible();
        await troubleshootingPlan.tapFollowOnTask(escalation.name);
        await page.waitForURL(
            (url) => /\/plan\//.test(url.pathname) && url.href !== originalPlanUrl,
            { timeout: 120_000 },
        );

        const plan = new PlanSurface(page);
        await expect(plan.laneBadge).toContainText('Deliberate');
        await expect(plan.approveButton).toBeVisible({ timeout: 240_000 });
        await expect(plan.simulatedTicket).toHaveCount(0);

        await plan.approveButton.click();
        await expect(plan.simulatedTicket).toBeVisible({ timeout: 120_000 });
        expect((await plan.ticketFields()).steps_attempted).toContain(reported);
    });
});
