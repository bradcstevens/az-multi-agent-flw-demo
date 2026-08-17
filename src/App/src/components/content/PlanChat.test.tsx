import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import React from 'react';

import PlanChat from './PlanChat';
import chatReducer, { setClarificationMessage } from '@/store/slices/chatSlice';
import transparencyReducer from '@/store/slices/transparencySlice';
import progressReducer from '@/store/slices/progressSlice';

const REPLY = 'I switched it off at the wall and back on again.';
const FOLLOW_ON = {
    id: 'task-223-escalation',
    name: "I can't fix it",
    prompt: 'I have tried everything and I need someone to come out.',
    created: '',
    creator: '',
    logo: 'Document',
    lane: 'deliberate',
};

/**
 * The wiring, not the component (issue #26).
 *
 * `RehearsedReplies.test.tsx` renders the chips directly, so deleting the
 * element from the conversation leaves that suite green and the presenter back
 * to typing the one answer the six taps exist to remove. This is the seam
 * between them — the same class of gap `test_ticket_contract.py` closes for the
 * Simulated ticket.
 */
const renderChat = (
    props: Partial<React.ComponentProps<typeof PlanChat>> = {},
    { pending = true }: { pending?: boolean } = {},
) => {
    const store = configureStore({
        reducer: {
            chat: chatReducer,
            transparency: transparencyReducer,
            progress: progressReducer,
        },
    });
    if (pending) {
        store.dispatch(
            setClarificationMessage({
                request_id: 'req-1',
                question: 'What have you already tried?',
            } as never),
        );
    }

    const ref = React.createRef<HTMLDivElement>();
    return render(
        <Provider store={store}>
            <PlanChat
                planData={{ plan: { id: 'plan-1', initial_goal: 'the coffee brewer is down' } } as never}
                input=""
                setInput={vi.fn()}
                submittingChatDisableInput={false}
                loading={false}
                OnChatSubmit={vi.fn()}
                planApprovalRequest={null}
                messagesContainerRef={ref as never}
                finalResultRef={ref as never}
                streamingMessageBuffer=""
                showBufferingText={false}
                agentMessages={[]}
                showProcessingPlanSpinner={false}
                processingElapsedSeconds={0}
                showApprovalButtons={false}
                handleApprovePlan={vi.fn()}
                handleRejectPlan={vi.fn()}
                processingApproval={false}
                rehearsedReplies={[REPLY]}
                {...(props as Record<string, unknown>)}
            />
        </Provider>,
    );
};

describe('the conversation offers the rehearsed replies', () => {
    it('renders them while a clarification is pending', () => {
        renderChat();

        expect(screen.getByRole('button', { name: REPLY })).toBeInTheDocument();
    });

    describe('the conversation offers its follow-on task', () => {
        it('renders the follow-on without waiting for a clarification and submits it on tap', () => {
            const onFollowOnTask = vi.fn();
            renderChat({ followOnTask: FOLLOW_ON, onFollowOnTask }, { pending: false });

            fireEvent.click(screen.getByRole('button', { name: FOLLOW_ON.name }));

            expect(onFollowOnTask).toHaveBeenCalledWith(FOLLOW_ON);
        });
    });

    it('submits one through the same path a typed answer takes', () => {
        // Not a second route. What the clarification seam records as Attempted
        // steps (#21), and what the Simulated ticket then carries (#22), has to
        // be the same whether the presenter tapped or typed.
        const OnChatSubmit = vi.fn();
        renderChat({ OnChatSubmit });

        fireEvent.click(screen.getByRole('button', { name: REPLY }));

        expect(OnChatSubmit).toHaveBeenCalledWith(REPLY);
    });

    it('renders none when no clarification is pending', () => {
        renderChat({}, { pending: false });

        expect(screen.queryByTestId('rehearsed-replies')).not.toBeInTheDocument();
    });

    it('does not offer a ticket-status reply before this Chat raises a ticket', () => {
        renderChat(
            {
                ticketStatusReply: {
                    prompt: 'Ticket status',
                    lane: 'fast',
                },
                onTicketStatusReply: vi.fn(),
            },
            { pending: false },
        );

        expect(screen.queryByTestId('ticket-status-reply')).not.toBeInTheDocument();
    });

    it('sends a derived starter back with the Reviewable plan', () => {
        const handleRejectPlan = vi.fn();
        renderChat(
            {
                showApprovalButtons: true,
                handleRejectPlan,
                planApprovalRequest: {
                    id: 'review-1',
                    user_request: 'Swap Saturday',
                    facts: '',
                    steps: [
                        {
                            id: 1,
                            action: 'Ask Marcus Bell to take the shift',
                            assignee: {
                                kind: 'person',
                                name: 'Marcus Bell',
                                relation: 'peer',
                                simulated: true,
                            },
                        },
                    ],
                },
            } as never,
            { pending: false },
        );

        fireEvent.click(
            screen.getByRole('button', { name: 'Ask somebody other than Marcus Bell.' }),
        );
        fireEvent.click(screen.getByRole('button', { name: 'Send back with changes' }));

        expect(handleRejectPlan).toHaveBeenCalledWith('Ask somebody other than Marcus Bell.');
    });

    it('offers no verdict the associate has not written, and no third one', () => {
        // The box is empty, so there is nothing to send back yet — and there is
        // no control between approving and sending back (#108).
        renderChat(
            {
                showApprovalButtons: true,
                planApprovalRequest: {
                    id: 'review-1',
                    user_request: 'Swap Saturday',
                    facts: '',
                    steps: [{ id: 1, action: 'Check the rota', agent: 'Rota_Agent' }],
                },
            } as never,
            { pending: false },
        );

        expect(screen.getByRole('button', { name: 'Send back with changes' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Approve Task Plan' })).toBeEnabled();
        expect(screen.queryByRole('button', { name: /reject|cancel/i })).not.toBeInTheDocument();
    });

    it('says which revision this is and every change that produced it', () => {
        renderChat(
            {
                showApprovalButtons: true,
                planApprovalRequest: {
                    id: 'review-1',
                    user_request: 'Swap Saturday',
                    facts: '',
                    revision: 3,
                    revision_feedback: [
                        'Ask somebody other than Marcus Bell.',
                        'Ask Dana Reyes next.',
                    ],
                    steps: [{ id: 1, action: 'Check the rota', agent: 'Rota_Agent' }],
                },
            } as never,
            { pending: false },
        );

        expect(screen.getByTestId('plan-revision')).toHaveTextContent('Revision 3');
        expect(screen.getAllByTestId('plan-revision-feedback').map((item) => item.textContent)).toEqual([
            'You asked to change: Ask somebody other than Marcus Bell.',
            'You asked to change: Ask Dana Reyes next.',
        ]);
    });
});
