import { describe, it, expect, beforeEach, vi } from 'vitest';

import webSocketService from './WebSocketService';
import { WebsocketMessageType } from '@/models';
import { parseSourceUsed, parseTokenUsage, parsePresenterAlert } from '@/models/transparency';
import { FakeSocket, frame } from '@/testing/fakeSocket';

/**
 * What a listener actually receives when a frame arrives on the socket.
 *
 * This is the seam the transparency panels were dark behind (#47). The panels,
 * the slice, the parsers and the subscription each had tests, and every one of
 * them passed while the deployed surface showed nothing at all — because they
 * all agreed with each other about a shape that `WebSocketService` does not
 * produce. The subscription's own test mocks the service and calls its handler
 * with `{ type, data: payload }`; the service's `default` branch emits
 * `{ type, data: <the whole frame> }`, so what the reducer parsed was a
 * envelope wearing the payload's name, and every total parser correctly
 * returned `null`.
 *
 * So this suite feeds the **raw wire text** — copied from a live Direct Line
 * run against the deployed backend — through the real service, and asserts that
 * what comes out the other side is the payload the parsers were written for.
 */

async function connectedSocket(): Promise<FakeSocket> {
    const connecting = webSocketService.connect('plan-223');
    const socket = FakeSocket.latest()!;
    socket.open();
    await connecting;
    return socket;
}

describe('a transparency signal arriving on the socket', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        webSocketService.disconnect();
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
    });

    it('reaches the listener as the payload the Grounding panel parses', async () => {
        const socket = await connectedSocket();
        const received: unknown[] = [];
        webSocketService.on(WebsocketMessageType.SOURCE_USED, (message) =>
            received.push(message.data),
        );

        socket.deliver(
            frame('source_used', {
                platform: 'Copilot Studio',
                source: 'Dataverse',
                agent_name: 'Store SOP Assistant',
                citations: [
                    {
                        position: 1,
                        name: 'SOP-102 Store Closing Procedure.docx',
                        snippet: 'Closing procedure',
                        url: null,
                    },
                ],
                conversation_id: 'abc',
            }),
        );

        expect(parseSourceUsed(received[0])?.platform).toBe('Copilot Studio');
    });

    it('reaches the listener as the payload the Token meter parses', async () => {
        const socket = await connectedSocket();
        const received: unknown[] = [];
        webSocketService.on(WebsocketMessageType.TOKEN_USAGE, (message) =>
            received.push(message.data),
        );

        socket.deliver(
            frame('token_usage', {
                agent_name: 'Shift Tasks Agent',
                executor_id: 'ShiftTasksAgent',
                input_tokens: 3232,
                output_tokens: 1294,
                total_tokens: 4526,
            }),
        );

        expect(parseTokenUsage(received[0])?.totalTokens).toBe(4526);
    });

    it('reaches the listener as the payload the Presenter alert parses', async () => {
        const socket = await connectedSocket();
        const received: unknown[] = [];
        webSocketService.on(WebsocketMessageType.PRESENTER_ALERT, (message) =>
            received.push(message.data),
        );

        socket.deliver(
            frame('presenter_alert', {
                title: 'Shift task due',
                content: 'The coffee station deep clean is due before handover.',
                timestamp: '2026-08-13T09:00:00+00:00',
            }),
        );

        expect(parsePresenterAlert(received[0])?.title).toBe('Shift task due');
    });

    it('reaches the listener as the payload the Simulated ticket parses', async () => {
        const socket = await connectedSocket();
        const received: Record<string, unknown>[] = [];
        webSocketService.on(WebsocketMessageType.TICKET_RAISED, (message) =>
            received.push(message.data as Record<string, unknown>),
        );

        socket.deliver(
            frame('ticket_raised', {
                ticket_id: 'SIM-223-0041',
                status: 'submitted',
                fields: [],
            }),
        );

        expect(received[0].ticket_id).toBe('SIM-223-0041');
    });
});

/**
 * Two entry points, one socket (issue #63, ADR-021).
 *
 * The connect is initiated on the `createPlan` response, and the chat page
 * keeps its own for a reload of `/chat/:id`. So for a plan asked from the home
 * surface both run, the second one landing while the first is still
 * handshaking — the exact case the service used to reject outright, telling its
 * caller the connection had failed while the same connection was succeeding.
 */
describe('connecting twice for one plan', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        webSocketService.disconnect();
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
    });

    it('opens one socket rather than two', async () => {
        const fromTheResponse = webSocketService.connect('plan-223');
        const fromThePlanPage = webSocketService.connect('plan-223');

        FakeSocket.latest()!.open();
        await Promise.all([fromTheResponse, fromThePlanPage]);

        expect(FakeSocket.forPlan('plan-223')).toHaveLength(1);
    });

    it('leaves the frames arriving on the one socket', async () => {
        const received: unknown[] = [];
        webSocketService.on(WebsocketMessageType.SOURCE_USED, (message) =>
            received.push(message.data),
        );

        const fromTheResponse = webSocketService.connect('plan-223');
        const fromThePlanPage = webSocketService.connect('plan-223');
        const socket = FakeSocket.latest()!;
        socket.open();
        await Promise.all([fromTheResponse, fromThePlanPage]);

        socket.deliver(
            frame('source_used', {
                platform: 'Copilot Studio',
                source: 'Dataverse',
                agent_name: 'Store SOP Assistant',
                citations: [],
                conversation_id: 'abc',
            }),
        );

        expect(parseSourceUsed(received[0])?.source).toBe('Dataverse');
    });

    it('goes on deduping the handshake it started when another plan asks mid-flight', async () => {
        // A connect for a different plan is refused, and must leave the
        // handshake already in flight exactly as it found it. Book-keeping the
        // refusal as though it were the pending connect made the *next* caller
        // for the right plan look like a collision.
        const fromTheResponse = webSocketService.connect('plan-223');
        await expect(webSocketService.connect('plan-999')).rejects.toThrow();

        const fromThePlanPage = webSocketService.connect('plan-223');
        FakeSocket.latest()!.open();
        await Promise.all([fromTheResponse, fromThePlanPage]);

        expect(FakeSocket.forPlan('plan-223')).toHaveLength(1);
        expect(FakeSocket.forPlan('plan-999')).toHaveLength(0);
    });

    it('opens no second socket once the first is open', async () => {
        const connecting = webSocketService.connect('plan-223');
        FakeSocket.latest()!.open();
        await connecting;

        await webSocketService.connect('plan-223');

        expect(FakeSocket.forPlan('plan-223')).toHaveLength(1);
    });
});
