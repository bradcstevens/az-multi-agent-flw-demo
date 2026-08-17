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
    selectPlanApprovalRequest,
    selectShowProcessingPlanSpinner,
    setContinueWithWebsocketFlow,
} from '@/store/slices/planSlice';
import progressReducer, { requestRouted, requestSent } from '@/store/slices/progressSlice';
import chatReducer, { selectAgentMessages } from '@/store/slices/chatSlice';
import appReducer from '@/store/slices/appSlice';
import teamReducer from '@/store/slices/teamSlice';
import streamingReducer from '@/store/slices/streamingSlice';
import transparencyReducer, { selectMeter } from '@/store/slices/transparencySlice';
import ticketReducer from '@/store/slices/ticketSlice';
import { useAppSelector } from '@/store/hooks';
import PlanChat from '@/components/content/PlanChat';
import TokenMeterPanel from '@/components/transparency/TokenMeterPanel';
import useTransparencySignals from '@/hooks/useTransparencySignals';

/**
 * The chat page's half of the connection lifecycle (issue #63, ADR-021).
 *
 * The connect is initiated on the `createPlan` response, so the chat page is no
 * longer the only way a socket gets opened — but it is still the only thing
 * that knows when the surface has finished with one, and it is the only connect
 * a reload of `/chat/:id` has, that path having no response to hang off.
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
    const showProcessingPlanSpinner = useAppSelector(selectShowProcessingPlanSpinner);
    const planApprovalRequest = useAppSelector(selectPlanApprovalRequest);
    const agentMessages = useAppSelector(selectAgentMessages);
    const meter = useAppSelector(selectMeter);
    useTransparencySignals();
    const ref = React.useRef<HTMLDivElement>(null);
    return (
        <>
            <PlanChat
                planData={{ plan: { id: planId ?? 'plan-1' } } as never}
                input=""
                setInput={() => {}}
                submittingChatDisableInput={false}
                loading={false}
                OnChatSubmit={() => {}}
                planApprovalRequest={planApprovalRequest}
                messagesContainerRef={ref as never}
                finalResultRef={ref as never}
                streamingMessageBuffer=""
                showBufferingText={false}
                agentMessages={agentMessages}
                showProcessingPlanSpinner={showProcessingPlanSpinner}
                processingElapsedSeconds={0}
                showApprovalButtons={false}
                handleApprovePlan={async () => {}}
                handleRejectPlan={async () => {}}
                processingApproval={false}
                rehearsedReplies={[]}
            />
            <TokenMeterPanel meter={meter} />
        </>
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
            progress: progressReducer,
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

describe('the chat page and a socket opened before it', () => {
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

    it('connects on a reload of /chat/:id, which has no response to hang off', async () => {
        const { store } = renderHost('plan-1');

        act(() => {
            store.dispatch(setContinueWithWebsocketFlow(true));
        });

        await waitFor(() => expect(FakeSocket.forPlan('plan-1')).toHaveLength(1));
    });
});

describe('the chat page mounted twice, as StrictMode mounts it', () => {
    it('still has a socket for the plan after the double invoke', async () => {
        // React 18 StrictMode runs every effect setup, then its cleanup, then
        // the setup again. A cleanup that disconnects a socket no setup opens
        // is therefore a socket closed on arrival — and the chat page's own
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

/**
 * The narration as the home surface arms it, before the navigation (ADR-023).
 *
 * `HomeInput` dispatches both: the POST going out, and the lane the response
 * reported. The chat page inherits the phase because one slice holds it — which
 * is the whole reason there is a slice.
 */
const askAQuestion = (store: ReturnType<typeof makeStore>, planId: string) => {
    act(() => {
        store.dispatch(requestSent());
        store.dispatch(requestRouted({ lane: 'fast', planId }));
    });
};

describe('the agent that is responding, named from the frame that names it', () => {
    it('names the executor an agent_message_streaming frame carries', async () => {
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        expect(screen.getByText('Routed — Fast lane')).toBeInTheDocument();

        act(() => {
            socket.deliver(
                frame('agent_message_streaming', {
                    agent_name: 'Troubleshooting Agent',
                    content: 'Let me check the closing procedure.',
                    is_final: false,
                }),
            );
        });

        await waitFor(() =>
            expect(screen.getByText('Troubleshooting Agent is responding...')).toBeInTheDocument(),
        );
    });

    it('names the next specialist when the question is handed on', async () => {
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(
                frame('agent_message_streaming', { agent_name: 'shift_tasks_agent', content: 'a' }),
            );
        });
        await waitFor(() =>
            expect(screen.getByText('Shift Tasks Agent is responding...')).toBeInTheDocument(),
        );

        act(() => {
            socket.deliver(
                frame('agent_message_streaming', { agent_name: 'Troubleshooting Agent', content: 'b' }),
            );
        });

        await waitFor(() =>
            expect(screen.getByText('Troubleshooting Agent is responding...')).toBeInTheDocument(),
        );
    });

    it('says an agent is responding when the frame names none', async () => {
        // Generic only where the name cannot be resolved. "Assistant Agent" —
        // what the display-name pipeline returns for an empty string — would be
        // an agent nobody configured, on screen as though a frame had named it.
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(frame('agent_message_streaming', { content: 'a' }));
        });

        await waitFor(() =>
            expect(screen.getByText('An agent is responding...')).toBeInTheDocument(),
        );
    });
});

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
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        expect(inFlightIndicators()).not.toHaveLength(0);

        deliverFinalResult(socket, status);

        await waitFor(() => expect(inFlightIndicators()).toHaveLength(0));
    };

    it('names the specialist that answered and that the cost table bills', async () => {
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(
                frame('agent_message_streaming', {
                    agent_name: 'Troubleshooting Agent',
                    content: 'I found the closing procedure.',
                }),
            );
            socket.deliver(
                frame('token_usage', {
                    agent_name: 'Troubleshooting Agent',
                    executor_id: 'TroubleshootingAgent',
                    input_tokens: 3232,
                    output_tokens: 1294,
                    total_tokens: 4526,
                }),
            );
            socket.deliver(
                frame('final_result_message', {
                    content: 'Cash up the tills before the shutters come down.',
                    status: 'completed',
                }),
            );
        });

        await waitFor(() => {
            expect(
                screen.getByText('Cash up the tills before the shutters come down.'),
            ).toBeInTheDocument();
            expect(screen.getAllByText('Troubleshooting')).toHaveLength(2);
        });
    });

    it('keeps the reported executor when the socket reconnects before the answer', async () => {
        vi.useFakeTimers();
        try {
            const { store } = renderHost('plan-1');
            askAQuestion(store, 'plan-1');
            const socket = await openedOnTheResponse('plan-1');

            act(() => {
                socket.deliver(
                    frame('agent_message_streaming', {
                        agent_name: 'Troubleshooting Agent',
                        content: 'I found the closing procedure.',
                    }),
                );
                socket.onclose?.({ code: 1006 });
                vi.advanceTimersByTime(1000);
            });
            FakeSocket.latest()!.open();

            act(() => {
                FakeSocket.latest()!.deliver(
                    frame('final_result_message', {
                        content: 'Cash up the tills before the shutters come down.',
                        status: 'completed',
                    }),
                );
            });

            expect(screen.getAllByText('Troubleshooting')).toHaveLength(1);
        } finally {
            vi.useRealTimers();
        }
    });

    it('does not name a specialist when no streaming frame named one', async () => {
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(
                frame('token_usage', {
                    agent_name: 'Shift Tasks Agent',
                    executor_id: 'ShiftTasksAgent',
                    input_tokens: 3232,
                    output_tokens: 1294,
                    total_tokens: 4526,
                }),
            );
            socket.deliver(
                frame('final_result_message', {
                    content: 'Cash up the tills before the shutters come down.',
                    status: 'completed',
                }),
            );
        });

        await waitFor(() =>
            expect(
                screen.getByText('Cash up the tills before the shutters come down.'),
            ).toBeInTheDocument(),
        );
        expect(screen.getAllByText('Shift Tasks')).toHaveLength(1);
        expect(screen.queryByText('Group Chat Manager')).not.toBeInTheDocument();
        expect(screen.queryByText('Assistant')).not.toBeInTheDocument();
    });

    it('leaves nothing in flight on the Fast lane, which has no plan to approve', async () => {
        // ADR-013: no `plan_approval_request` arrives on this lane, so the final
        // result is the only thing that can ever stop the narration.
        const scrollToFinalResult = vi.fn();
        const { store } = renderHost('plan-1', { scrollToFinalResult });
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        expect(inFlightIndicators()).not.toHaveLength(0);

        deliverFinalResult(socket, 'completed');

        await waitFor(() => expect(inFlightIndicators()).toHaveLength(0));
        expect(scrollToFinalResult).toHaveBeenCalledOnce();
    });

    it('leaves nothing in flight once an approved plan has been running', async () => {
        // The Deliberate lane's second indicator, reached the way the lane
        // reaches it: the approval request settles the first request, and the
        // approval starts a second. A guard watching only the thinking state
        // sees an empty screen from here on either way.
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
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
        await waitFor(() => expect(inFlightIndicators()).toHaveLength(0));

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

    it('leaves nothing in flight after an error frame of its own', async () => {
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        expect(inFlightIndicators()).not.toHaveLength(0);

        act(() => {
            socket.deliver(frame('error_message', { content: 'The orchestration failed.' }));
        });

        await waitFor(() => expect(inFlightIndicators()).toHaveLength(0));
    });
});

describe('a plan approval arriving on the wire', () => {
    it('renders the approved plan once in the real conversation', async () => {
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(
                frame('plan_approval_request', {
                    plan: {
                        user_request: 'How do I close the store?',
                        steps: [{ id: 1, action: 'Read the closing checklist', agent: 'Shift Tasks Agent' }],
                    },
                }),
            );
        });

        await waitFor(() => {
            expect(screen.getByRole('heading', { name: 'Plan Overview' })).toBeInTheDocument();
            expect(screen.getAllByText('Read the closing checklist')).toHaveLength(1);
        });
        expect(screen.getAllByRole('heading', { name: 'Plan Overview' })).toHaveLength(1);
    });
});
