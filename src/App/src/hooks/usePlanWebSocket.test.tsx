import { describe, it, expect, beforeEach, vi } from 'vitest';
import { StrictMode } from 'react';
import { render, waitFor, act, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

import usePlanWebSocket from './usePlanWebSocket';
import webSocketService from '@/store/WebSocketService';
import { FakeSocket, frame } from '@/testing/fakeSocket';
import { WebsocketMessageType } from '@/models';
import planReducer, {
    selectWaitingForPlan,
    setContinueWithWebsocketFlow,
} from '@/store/slices/planSlice';
import chatReducer from '@/store/slices/chatSlice';
import appReducer from '@/store/slices/appSlice';
import teamReducer from '@/store/slices/teamSlice';
import streamingReducer from '@/store/slices/streamingSlice';
import transparencyReducer from '@/store/slices/transparencySlice';
import ticketReducer from '@/store/slices/ticketSlice';
import { useAppSelector } from '@/store/hooks';
import { renderThinkingState } from '@/components/content/streaming/StreamingPlanState';

/**
 * The plan page's half of the connection lifecycle (issue #63, ADR-021).
 *
 * The connect is initiated on the `createPlan` response, so the plan page is no
 * longer the only way a socket gets opened — but it is still the only thing
 * that knows when the surface has finished with one, and it is the only connect
 * a reload of `/plan/:id` has, that path having no response to hang off.
 */
const Host = ({
    planId,
    scrollToBottom = () => {},
    scrollToFinalResult = () => {},
}: {
    planId?: string;
    scrollToBottom?: () => void;
    scrollToFinalResult?: () => void;
}) => {
    usePlanWebSocket({
        planId,
        scrollToBottom,
        scrollToFinalResult,
        formatErrorMessage: (content: string) => content,
        showToast: () => 0,
    });
    return renderThinkingState(useAppSelector(selectWaitingForPlan));
};

const makeStore = () =>
    configureStore({
        reducer: {
            plan: planReducer,
            chat: chatReducer,
            app: appReducer,
            team: teamReducer,
            streaming: streamingReducer,
            transparency: transparencyReducer,
            ticket: ticketReducer,
        },
        middleware: (getDefault) => getDefault({ serializableCheck: false }),
    });

const renderHost = (
    planId?: string,
    callbacks: Pick<React.ComponentProps<typeof Host>, 'scrollToBottom' | 'scrollToFinalResult'> = {},
) => {
    const store = makeStore();
    const rendered = render(
        <Provider store={store}>
            <Host planId={planId} {...callbacks} />
        </Provider>,
    );
    return { store, ...rendered };
};

/** The socket as `HomeInput` leaves it: opened on the response, before any navigation. */
const openedOnTheResponse = async (planId: string) => {
    const connecting = webSocketService.connect(planId);
    const socket = FakeSocket.latest()!;
    socket.open();
    await connecting;
    return socket;
};

beforeEach(() => {
    FakeSocket.instances = [];
    webSocketService.disconnect();
    vi.stubGlobal('WebSocket', FakeSocket);
    window.appConfig = { API_URL: 'https://backend.example/api' } as never;
});

describe('the plan page and a socket opened before it', () => {
    it('opens no second socket for a plan already connected', async () => {
        await openedOnTheResponse('plan-1');
        const { store } = renderHost('plan-1');

        act(() => {
            store.dispatch(setContinueWithWebsocketFlow(true));
        });

        await waitFor(() => expect(FakeSocket.forPlan('plan-1')).toHaveLength(1));
    });

    it('closes it on the way out even though the plan data never arrived', async () => {
        // `continueWithWebsocketFlow` is only set by `fetchPlanData.fulfilled`,
        // so a presenter who leaves before the GET lands used to take the whole
        // connect/disconnect effect with them — including the disconnect for a
        // socket the response had already opened.
        await openedOnTheResponse('plan-1');
        const { unmount } = renderHost('plan-1');

        unmount();

        expect(webSocketService.isConnected()).toBe(false);
    });

    it('connects on a reload of /plan/:id, which has no response to hang off', async () => {
        const { store } = renderHost('plan-1');

        act(() => {
            store.dispatch(setContinueWithWebsocketFlow(true));
        });

        await waitFor(() => expect(FakeSocket.forPlan('plan-1')).toHaveLength(1));
    });
});

describe('the plan page mounted twice, as StrictMode mounts it', () => {
    it('still has a socket for the plan after the double invoke', async () => {
        // React 18 StrictMode runs every effect setup, then its cleanup, then
        // the setup again. A cleanup that disconnects a socket no setup opens
        // is therefore a socket closed on arrival — and the plan page's own
        // connect cannot reopen it, because `continueWithWebsocketFlow` is
        // still false until the plan GET lands. That is #63 again, reachable
        // from the dev server, which is the surface the local Demo validator
        // target drives.
        await openedOnTheResponse('plan-1');
        const named: string[] = [];
        const unsub = webSocketService.on(
            WebsocketMessageType.AGENT_MESSAGE_STREAMING,
            (message: any) => named.push(message.data?.agent),
        );

        const store = makeStore();
        render(
            <StrictMode>
                <Provider store={store}>
                    <Host planId="plan-1" />
                </Provider>
            </StrictMode>,
        );

        const socket = FakeSocket.forPlan('plan-1').at(-1)!;
        if (socket.readyState !== FakeSocket.OPEN) socket.open();
        socket.deliver(
            frame('agent_message_streaming', {
                agent_name: 'Troubleshooting Agent',
                content: 'Let me check the closing procedure.',
                is_final: false,
            }),
        );
        unsub();

        expect(named).toEqual(['Troubleshooting Agent']);
    });
});

describe('a final result arriving on the socket', () => {
    const expectThinkingToStopAfter = async (status: string) => {
        renderHost('plan-1');
        const socket = await openedOnTheResponse('plan-1');

        expect(screen.getByText('Creating your plan...')).toBeInTheDocument();

        act(() => {
            socket.deliver(
                frame('final_result_message', {
                    content: 'The answer is ready.',
                    status,
                }),
            );
        });

        await waitFor(() =>
            expect(screen.queryByText('Creating your plan...')).not.toBeInTheDocument(),
        );
    };

    it('removes the in-flight indicator after a completed final result', async () => {
        const scrollToFinalResult = vi.fn();
        renderHost('plan-1', { scrollToFinalResult });
        const socket = await openedOnTheResponse('plan-1');

        expect(screen.getByText('Creating your plan...')).toBeInTheDocument();

        act(() => {
            socket.deliver(
                frame('final_result_message', {
                    content: 'The answer is ready.',
                    status: 'completed',
                }),
            );
        });

        await waitFor(() =>
            expect(screen.queryByText('Creating your plan...')).not.toBeInTheDocument(),
        );
        expect(scrollToFinalResult).toHaveBeenCalledOnce();
    });

    it('removes the in-flight indicator after an error final result', async () => {
        await expectThinkingToStopAfter('error');
    });

    it('removes the in-flight indicator after another terminal final result', async () => {
        await expectThinkingToStopAfter('failed');
    });
});
