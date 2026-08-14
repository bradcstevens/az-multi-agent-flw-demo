import { Page } from '@playwright/test';

/**
 * What the **server** holds, asked for the way the surface asks.
 *
 * Issue #50. Two of this issue's claims are explicitly about server-side state
 * rather than about anything the browser is holding, and for the reason #20
 * already recorded: the **Lane** the router took survives a reload because it
 * is written into session state, and a browser that re-derived it would be a
 * second lane router with its own opinion. A validator that read the lane off
 * the badge would be grading that second opinion — it would pass on a surface
 * that renders `Deliberate` for a request the router sent down the Fast lane,
 * which is the one way this beat can be wrong and still look right.
 *
 * The same argument decides the **Attempted step**. A chip tap that records
 * nothing looks exactly like a tap that worked: the chat shows the associate's
 * words either way, because the browser put them there. Only the record can
 * tell the two apart, and the record is in Cosmos.
 *
 * Everything here goes through the app's **own** API base, read out of the
 * running page (`window.appConfig`), so the suite never carries a second copy
 * of where the backend is — the same rule `scripts/e2e-tests.sh` follows for
 * the frontend's ingress.
 */

/** The backend's `/api` base, as the running surface resolved it. */
export async function apiBase(page: Page): Promise<string> {
    const configured = await page.evaluate(
        () => (window as unknown as { appConfig?: { API_URL?: string } }).appConfig?.API_URL || '',
    );
    if (!configured) {
        throw new Error(
            'the surface has no API_URL in window.appConfig — it never loaded ' +
                '/config, so nothing on this page has a backend to talk to',
        );
    }
    // `api/config.tsx` normalises the same way. A deployment whose config
    // already carries the suffix and one whose config does not are the same
    // backend, and a validator that got this wrong would 404 on every read and
    // report it as missing state.
    const base = configured.replace(/\/$/, '');
    return base.includes('/api') ? base : `${base}/api`;
}

/**
 * The principal the surface presents, if it presents one.
 *
 * The demonstration opens anonymous on a shared store device, so
 * `window.activeUserId` is unset and the header is omitted — exactly as the
 * app's own `httpClient` omits it — and the backend resolves the same default
 * user for both. Read rather than assumed, so a signed-in beat reads the state
 * of the associate whose session it is.
 */
async function principalHeaders(page: Page): Promise<Record<string, string>> {
    const userId = await page.evaluate(
        () => (window as unknown as { activeUserId?: string }).activeUserId || '',
    );
    return userId ? { 'x-ms-client-principal-id': userId } : {};
}

async function read(page: Page, path: string): Promise<unknown> {
    const response = await page.request.get(`${await apiBase(page)}${path}`, {
        headers: await principalHeaders(page),
    });
    if (!response.ok()) {
        throw new Error(
            `${path} answered ${response.status()} — the backend is not ` +
                'holding the state this beat is about to grade',
        );
    }
    return response.json();
}

/** The session one plan belongs to. One conversation, one session (#22). */
export async function sessionOfPlan(page: Page, planId: string): Promise<string> {
    const body = (await read(page, `/v4/plan?plan_id=${encodeURIComponent(planId)}`)) as {
        plan?: { session_id?: string };
    };
    const sessionId = body?.plan?.session_id;
    if (!sessionId) {
        throw new Error(`plan ${planId} came back with no session`);
    }
    return sessionId;
}

/**
 * The **Lane** the router took, as it was written down server-side (#20).
 *
 * `null` when the session has no lane recorded, which is a real state — the
 * Identity boundary gate refuses above the router, so a refused request takes
 * no lane at all — and one a beat must be able to tell from *the wrong lane*.
 */
export async function laneTaken(page: Page, sessionId: string): Promise<string | null> {
    const state = (await read(
        page,
        `/v4/session_state/${encodeURIComponent(sessionId)}`,
    )) as { lane?: string | null };
    return typeof state?.lane === 'string' ? state.lane : null;
}

/**
 * The **Attempted steps** the record holds for the turn in flight.
 *
 * The route takes no session and no user: the backend resolves the turn itself
 * (`troubleshooting.turn`), which is the same refusal to let a caller carry an
 * identifier that the MCP container's tools ride. So this answers *for the
 * conversation the browser most recently started* — which is the one the beat
 * asking is in the middle of.
 */
export async function attemptedSteps(page: Page): Promise<string[]> {
    const record = (await read(page, '/v4/troubleshooting/attempted')) as {
        attempted?: unknown;
    };
    return Array.isArray(record?.attempted) ? (record.attempted as string[]) : [];
}

/** A ticket this conversation has drafted, if any, as the container holds it. */
export async function draftedTicket(
    page: Page,
): Promise<{ drafted: boolean; fields: Record<string, string> }> {
    const ticket = (await read(page, '/v4/escalation/ticket')) as {
        drafted?: boolean;
        fields?: Record<string, string>;
    };
    return { drafted: Boolean(ticket?.drafted), fields: ticket?.fields || {} };
}
