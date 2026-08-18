import { describe, it, expect, beforeEach, vi } from 'vitest';
import React, { StrictMode } from 'react';
import { render, waitFor, act, screen, within } from '@testing-library/react';
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
import chatReducer from '@/store/slices/chatSlice';
import appReducer from '@/store/slices/appSlice';
import teamReducer from '@/store/slices/teamSlice';
import streamingReducer from '@/store/slices/streamingSlice';
import transparencyReducer from '@/store/slices/transparencySlice';
import ticketReducer from '@/store/slices/ticketSlice';
import verdictReducer from '@/store/slices/verdictSlice';
import { useAppSelector } from '@/store/hooks';
import {
    selectSettledReply,
    selectStreamedReply,
} from '@/store/slices/streamingSlice';
import { selectAgentMessages } from '@/store/slices/chatSlice';
import PlanChat from '@/components/content/PlanChat';

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
    const streamedReply = useAppSelector(selectStreamedReply);
    const settledReply = useAppSelector(selectSettledReply);
    const agentMessages = useAppSelector(selectAgentMessages);
    const ref = React.useRef<HTMLDivElement>(null);
    return (
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
            streamedReply={streamedReply}
            settledReply={settledReply}
            agentMessages={agentMessages}
            showProcessingPlanSpinner={showProcessingPlanSpinner}
            processingElapsedSeconds={0}
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
            verdict: verdictReducer,
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

describe('a streamed specialist reply in the conversation', () => {
    it('renders each chunk in the reply, then lets the complete result replace it and announce once', async () => {
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(
                frame('agent_message_streaming', {
                    agent_name: 'Store SOP Agent',
                    content: 'Begin by cashing up the tills.',
                    is_final: false,
                }),
            );
        });

        await screen.findByText('Begin by cashing up the tills.');
        expect(inFlightIndicators()).toHaveLength(0);
        expect(screen.queryByText('AI Thinking Process')).not.toBeInTheDocument();

        act(() => {
            socket.deliver(
                frame('agent_message_streaming', {
                    agent_name: 'Store SOP Agent',
                    content: '',
                    is_final: true,
                }),
            );
        });

        expect(store.getState().streaming.isReplyComplete).toBe(true);

        act(() => {
            socket.deliver(
                frame('final_result_message', {
                    content: 'Follow the complete store closing checklist.',
                    status: 'completed',
                }),
            );
        });

        await waitFor(() =>
            expect(screen.getAllByText('Follow the complete store closing checklist.')).not.toHaveLength(0),
        );
        expect(screen.queryByText('Begin by cashing up the tills.')).not.toBeInTheDocument();
        expect(
            screen.getAllByRole('status').filter(
                (element) => element.textContent === 'Follow the complete store closing checklist.',
            ),
        ).toHaveLength(1);
    });

    it('starts a new preview when the same specialist begins another completed stream', async () => {
        const { store } = renderHost('plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(
                frame('agent_message_streaming', {
                    agent_name: 'Store SOP Agent',
                    content: 'The first answer.',
                    is_final: true,
                }),
            );
        });
        await screen.findByText('The first answer.');

        act(() => {
            socket.deliver(
                frame('agent_message_streaming', {
                    agent_name: 'Store SOP Agent',
                    content: 'The next answer.',
                    is_final: false,
                }),
            );
        });

        await screen.findByText('The next answer.');
        expect(screen.queryByText('The first answer.')).not.toBeInTheDocument();
        expect(store.getState().streaming.isReplyComplete).toBe(false);
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

    it('shows person steps as requests in their declared order', async () => {
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(
                frame('plan_approval_request', {
                    plan: {
                        user_request: 'Swap my Saturday shift with Marcus Bell',
                        steps: [
                            {
                                id: 1,
                                action: 'Check the swap procedure',
                                assignee: { kind: 'agent', name: 'Workforce Agent' },
                                waitsOn: null,
                            },
                            {
                                id: 2,
                                action: 'Confirm the request',
                                assignee: {
                                    kind: 'person',
                                    name: 'You',
                                    relation: 'associate',
                                    simulated: false,
                                },
                                waitsOn: 1,
                            },
                            {
                                id: 3,
                                action: 'Ask Marcus Bell to take the shift',
                                assignee: {
                                    kind: 'person',
                                    name: 'Marcus Bell',
                                    relation: 'peer',
                                    simulated: true,
                                },
                                waitsOn: 2,
                            },
                            {
                                id: 4,
                                action: 'Ask Dana Reyes to approve the swap',
                                assignee: {
                                    kind: 'person',
                                    name: 'Dana Reyes',
                                    relation: 'manager',
                                    simulated: true,
                                },
                                waitsOn: 3,
                            },
                        ],
                    },
                }),
            );
        });

        await waitFor(() => {
            expect(screen.getAllByText('Person step')).toHaveLength(3);
            expect(screen.getByText('You are asked to confirm this request.')).toBeInTheDocument();
            expect(
                screen.getByText('Marcus Bell gets a message. Marcus Bell can say no.'),
            ).toBeInTheDocument();
            expect(
                screen.getByText('Dana Reyes gets a message. Dana Reyes can say no.'),
            ).toBeInTheDocument();
        });

        expect(screen.getAllByText(/is asked next/).map((element) => element.textContent)).toEqual([
            'Marcus Bell, the associate you named, is asked next.',
            'Dana Reyes, your shift lead, is asked next.',
        ]);
        expect(inFlightIndicators()).toHaveLength(0);
    });

    it('names every person the plan reaches inside the plan step list itself', async () => {
        // The **Demo validator** grades this beat by looking for the invented
        // colleagues by name, and the only honest place to look is the plan's
        // own steps. Searching the conversation column instead matches the
        // request line, the prose and every ancestor of each — a beat that goes
        // red for a reason that is not the beat.
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(
                frame('plan_approval_request', {
                    plan: {
                        user_request:
                            'Marcus Bell and I have agreed to swap our Saturday shifts. Start the swap.',
                        steps: [
                            {
                                id: 1,
                                action: 'Check the swap procedure for this store',
                                assignee: { kind: 'agent', name: 'Workforce Agent' },
                                waitsOn: null,
                            },
                            {
                                id: 2,
                                action: 'Confirm you want the agreed Saturday swap to proceed',
                                assignee: {
                                    kind: 'person',
                                    name: 'You',
                                    relation: 'associate',
                                    simulated: false,
                                },
                                waitsOn: 1,
                            },
                            {
                                id: 3,
                                action: 'Ask Marcus Bell to confirm the agreed swap',
                                assignee: {
                                    kind: 'person',
                                    name: 'Marcus Bell',
                                    relation: 'peer',
                                    simulated: true,
                                },
                                waitsOn: 2,
                            },
                            {
                                id: 4,
                                action: 'Ask Dana Reyes to approve the swap',
                                assignee: {
                                    kind: 'person',
                                    name: 'Dana Reyes',
                                    relation: 'manager',
                                    simulated: true,
                                },
                                waitsOn: 3,
                            },
                        ],
                    },
                }),
            );
        });

        const steps = await screen.findByTestId('reviewable-plan-steps');

        for (const person of ['You', 'Marcus Bell', 'Dana Reyes']) {
            expect(
                within(steps).getAllByText(new RegExp(person)),
                `the plan step list never names ${person}`,
            ).not.toHaveLength(0);
        }
    });
});

describe('a declined Verdict arriving on the wire', () => {
    it('ends the approved plan and says the remaining steps did not proceed', async () => {
        const { store } = renderHost('plan-1');
        askAQuestion(store, 'plan-1');
        const socket = await openedOnTheResponse('plan-1');

        act(() => {
            socket.deliver(
                frame('plan_approval_request', {
                    plan: {
                        id: 'mplan-1',
                        user_request: 'Swap my Saturday shift with Marcus Bell',
                        steps: [
                            {
                                id: 3,
                                action: 'Ask Marcus Bell to take the shift',
                                assignee: {
                                    kind: 'person',
                                    name: 'Marcus Bell',
                                    relation: 'peer',
                                    simulated: true,
                                },
                            },
                            {
                                id: 4,
                                action: 'Ask Dana Reyes to approve the swap',
                                assignee: {
                                    kind: 'person',
                                    name: 'Dana Reyes',
                                    relation: 'manager',
                                    simulated: true,
                                },
                                waitsOn: 3,
                            },
                        ],
                    },
                }),
            );
        });
        await screen.findByRole('heading', { name: 'Plan Overview' });

        act(() => {
            store.dispatch(planApprovalAccepted());
            socket.deliver(
                frame('verdict_landed', {
                    m_plan_id: 'mplan-1',
                    step_id: 3,
                    assignee: {
                        kind: 'person',
                        name: 'Marcus Bell',
                        relation: 'peer',
                        simulated: true,
                    },
                    outcome: 'declined',
                    words: 'I cannot make the Saturday swap.',
                    provenance_line: 'No workforce management system was consulted.',
                }),
            );
        });

        await waitFor(() => {
            expect(screen.getByText('Marcus Bell declined')).toBeInTheDocument();
            expect(screen.getByTestId('verdict-plan-stopped')).toHaveTextContent(
                'The rest of this plan did not proceed.',
            );
            expect(inFlightIndicators()).toHaveLength(0);
            expect(selectShowProcessingPlanSpinner(store.getState())).toBe(false);
        });
    });
});
