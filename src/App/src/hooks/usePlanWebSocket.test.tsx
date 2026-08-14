import { describe, it, expect, beforeEach, vi } from 'vitest';
import React, { StrictMode } from 'react';
import { render, waitFor, act, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

import usePlanWebSocket from './usePlanWebSocket';
import webSocketService from '@/store/WebSocketService';
import { FakeSocket, frame } from '@/testing/fakeSocket';
import { WebsocketMessageType } from '@/models';
import planReducer, {
    planApprovalAccepted,
    selectShowProcessingPlanSpinner,
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
import PlanChat from '@/components/content/PlanChat';

/**
 * The plan page's half of the connection lifecycle (issue #63, ADR-021).
 *
 * The connect is initiated on the `createPlan` response, so the plan page is no
 * longer the only way a socket gets opened — but it is still the only thing
 * that knows when the surface has finished with one, and it is the only connect
 * a reload of `/plan/:id` has, that path having no response to hang off.
 *
 * The host renders the **real** conversation, `PlanChat`, fed from the store the
 * way `PlanPage` feeds it. A stand-in that renders one of the two in-flight
 * indicators can only agree with itself about what is on screen, which is the
 * #47 finding one layer up: the guard below (#69) is a claim about the surface,
 * so it has to be made against the surface.
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
    const waitingForPlan = useAppSelector(selectWaitingForPlan);
    const showProcessingPlanSpinner = useAppSelector(selectShowProcessingPlanSpinner);
    const ref = React.useRef<HTMLDivElement>(null);
    return (
        <PlanChat
            planData={{ plan: { id: planId ?? 'plan-1' } } as never}
            input=""
            setInput={() => {}}
            submittingChatDisableInput={false}
            loading={false}
            OnChatSubmit={() => {}}
            planApprovalRequest={null}
            waitingForPlan={waitingForPlan}
            messagesContainerRef={ref as never}
            finalResultRef={ref as never}
            streamingMessageBuffer=""
            showBufferingText={false}
            agentMessages={[]}
            showProcessingPlanSpinner={showProcessingPlanSpinner}
            processingElapsedSeconds={0}
            processingStatusMessage="Processing your plan and coordinating with AI agents..."
            showApprovalButtons={false}
            handleApprovePlan={async () => {}}
            handleRejectPlan={async () => {}}
            processingApproval={false}
            rehearsedReplies={[]}
        />
    );
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

/**
 * Everything on the surface still claiming the request is in flight (#69).
 *
 * Asserted by **role**, not by copy. Both indicators the conversation can show
 * — the thinking state and the plan-execution message — are a Fluent `Spinner`,
 * which is a `progressbar`; and #64 rewrites every one of those strings, so a
 * guard pinned to the words is deleted along with the words, exactly when it is
 * needed. Nothing on this surface is a progressbar for any other reason.
 */
const inFlightIndicators = () => screen.queryAllByRole('progressbar');

describe('a final result arriving on the socket', () => {
    const deliverFinalResult = (socket: FakeSocket, status: string) => {
        act(() => {
            socket.deliver(
                frame('final_result_message', {
                    content: 'The answer is ready.',
                    status,
                }),
            );
        });
    };

    const expectNothingInFlightAfter = async (status: string) => {
        renderHost('plan-1');
        const socket = await openedOnTheResponse('plan-1');

        expect(inFlightIndicators()).not.toHaveLength(0);

        deliverFinalResult(socket, status);

        await waitFor(() => expect(inFlightIndicators()).toHaveLength(0));
    };

    it('leaves nothing in flight on the Fast lane, which has no plan to approve', async () => {
        // ADR-013: no `plan_approval_request` arrives on this lane, so the final
        // result is the only thing that can ever stop the narration.
        const scrollToFinalResult = vi.fn();
        renderHost('plan-1', { scrollToFinalResult });
        const socket = await openedOnTheResponse('plan-1');

        expect(inFlightIndicators()).not.toHaveLength(0);

        deliverFinalResult(socket, 'completed');

        await waitFor(() => expect(inFlightIndicators()).toHaveLength(0));
        expect(scrollToFinalResult).toHaveBeenCalledOnce();
    });

    it('leaves nothing in flight once an approved plan has been running', async () => {
        // The Deliberate lane's second indicator, reached the way the lane
        // reaches it: `approvalRequestReceived` clears the thinking state, and
        // the approval starts the plan-execution message. A guard watching only
        // the thinking state sees an empty screen from here on either way.
        const { store } = renderHost('plan-1');
        const socket = await openedOnTheResponse('plan-1');
        act(() => {
            socket.deliver(
                frame('plan_approval_request', {
                    plan: {
                        id: 'mplan-1',
                        user_request: 'How do I close the store?',
                        steps: [{ id: 1, action: 'Read the closing checklist', agent: 'Shift Tasks Agent' }],
                    },
                }),
            );
        });
        expect(inFlightIndicators()).toHaveLength(0);

        act(() => {
            store.dispatch(planApprovalAccepted());
        });

        expect(inFlightIndicators()).not.toHaveLength(0);

        deliverFinalResult(socket, 'completed');

        await waitFor(() => expect(inFlightIndicators()).toHaveLength(0));
    });

    it('leaves nothing in flight after an error final result', async () => {
        await expectNothingInFlightAfter('error');
    });

    it('leaves nothing in flight after another terminal final result', async () => {
        // The `status === 'completed'` guard's else branch: any other terminal
        // status hangs the indicator unless it clears them too.
        await expectNothingInFlightAfter('failed');
    });
});
