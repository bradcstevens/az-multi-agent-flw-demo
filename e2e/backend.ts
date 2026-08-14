import { Page } from '@playwright/test';

/**
 * Read the attempted steps from the backend state the troubleshooting turn
 * writes. The conversation renders the answer either way; this is the seam
 * that proves it became context for the follow-on ticket.
 */
export async function attemptedSteps(page: Page): Promise<string[]> {
    const configured = await page.evaluate(
        () =>
            (
                window as unknown as { appConfig?: { API_URL?: string } }
            ).appConfig?.API_URL || '',
    );
    if (!configured) {
        throw new Error(
            'the surface has no API_URL in window.appConfig, so the ' +
                'troubleshooting record cannot be read',
        );
    }

    const base = configured.replace(/\/$/, '');
    const apiBase = base.includes('/api') ? base : `${base}/api`;
    const response = await page.request.get(
        `${apiBase}/v4/troubleshooting/attempted`,
    );
    if (!response.ok()) {
        throw new Error(
            `the attempted-steps route answered ${response.status()}`,
        );
    }

    const body = (await response.json()) as { attempted?: unknown };
    return Array.isArray(body.attempted)
        ? body.attempted.filter((step): step is string => typeof step === 'string')
        : [];
}
