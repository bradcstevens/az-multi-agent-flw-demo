import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import React from 'react';

import PlanChat from './PlanChat';
import chatReducer, { setClarificationMessage } from '@/store/slices/chatSlice';
import transparencyReducer from '@/store/slices/transparencySlice';

const REPLY = 'I switched it off at the wall and back on again.';

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
        reducer: { chat: chatReducer, transparency: transparencyReducer },
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
                waitingForPlan={false}
                messagesContainerRef={ref as never}
                finalResultRef={ref as never}
                streamingMessageBuffer=""
                showBufferingText={false}
                agentMessages={[]}
                showProcessingPlanSpinner={false}
                processingElapsedSeconds={0}
                processingStatusMessage=""
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
});
