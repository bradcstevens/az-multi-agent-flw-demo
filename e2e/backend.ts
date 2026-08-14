import { Page } from '@playwright/test';

/**
 * Read the attempted steps from the backend state the troubleshooting turn
 * writes. The conversation renders the answer either way; this is the seam
 * that proves it became context for the follow-on ticket.
 */
async function apiBase(page: Page): Promise<string> {
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
    return base.includes('/api') ? base : `${base}/api`;
}

async function read(page: Page, path: string): Promise<unknown> {
    const response = await page.request.get(`${await apiBase(page)}${path}`);
    if (!response.ok()) {
        throw new Error(`${path} answered ${response.status()}`);
    }
    return response.json();
}

export async function attemptedSteps(page: Page): Promise<string[]> {
    const body = (await read(page, '/v4/troubleshooting/attempted')) as {
        attempted?: unknown;
    };
    return Array.isArray(body.attempted)
        ? body.attempted.filter(
              (step): step is string => typeof step === 'string',
          )
        : [];
}

/** The session the current plan belongs to, from the application's own API. */
export async function sessionOfPlan(page: Page, planId: string): Promise<string> {
    const body = (await read(
        page,
        `/v4/plan?plan_id=${encodeURIComponent(planId)}`,
    )) as { plan?: { session_id?: string } };
    const sessionId = body.plan?.session_id;
    if (!sessionId) {
        throw new Error(`plan ${planId} came back with no session`);
    }
    return sessionId;
}

/** The Lane the request path persisted for a session. */
export async function laneTaken(
    page: Page,
    sessionId: string,
): Promise<string | null> {
    const body = (await read(
        page,
        `/v4/session_state/${encodeURIComponent(sessionId)}`,
    )) as { lane?: unknown };
    return typeof body.lane === 'string' ? body.lane : null;
}

/** A ticket the current conversation drafted, if it has one. */
export async function draftedTicket(
    page: Page,
): Promise<{ drafted: boolean; fields: Record<string, string> }> {
    const body = (await read(page, '/v4/escalation/ticket')) as {
        drafted?: unknown;
        fields?: unknown;
    };
    return {
        drafted: Boolean(body.drafted),
        fields:
            body.fields && typeof body.fields === 'object'
                ? (body.fields as Record<string, string>)
                : {},
    };
}
