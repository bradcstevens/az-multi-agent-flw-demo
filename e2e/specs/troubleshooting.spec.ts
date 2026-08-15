import { expect, test } from '@playwright/test';

import { troubleshootingTask } from '../authored';
import { attemptedSteps } from '../backend';
import { recordRehearsal } from '../evidence';
import { ChatSurface } from '../pages/ChatSurface';
import { StoreSurface } from '../pages/StoreSurface';

/**
 * Beat 3 — the assistant asks what this shift already tried.
 *
 * The authored replies are a public, deterministic signal: the exact choices
 * the associate can tap rather than type. The ticket beat proves their
 * server-side consequence after it follows this conversation forward.
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

test.describe('the troubleshooting beat', () => {
    test('offers the authored reply choices only while a clarification stands', async ({
        page,
    }) => {
        const task = troubleshootingTask();
        const store = new StoreSurface(page);
        await store.open();
        await store.tapQuickTask(task.name);

        const plan = new ChatSurface(page);
        await plan.waitForArrival(120_000);

        await expect(plan.rehearsedReplies).toBeVisible({ timeout: 240_000 });
        expect(await plan.rehearsedReplyLabels()).toEqual(
            task.rehearsedReplies,
        );

        await plan.tapRehearsedReply(task.rehearsedReplies[0]);
        await expect(plan.rehearsedReplies).toBeHidden({ timeout: 60_000 });

        // The browser always renders the answer it sent. The record is the
        // evidence that the troubleshooting context survives into its
        // follow-on, so read it back rather than believing the chat.
        await expect
            .poll(() => attemptedSteps(page), { timeout: 60_000 })
            .not.toHaveLength(0);
    });
});
