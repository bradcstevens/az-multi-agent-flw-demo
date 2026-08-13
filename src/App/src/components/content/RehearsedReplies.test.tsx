import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

import RehearsedReplies from './RehearsedReplies';
import chatReducer, { setClarificationMessage } from '@/store/slices/chatSlice';

const REPLIES = [
    'I switched it off at the wall and back on again.',
    'I put a fresh paper filter in and rinsed the brew head.',
];

const renderReplies = (
    props: Partial<React.ComponentProps<typeof RehearsedReplies>> = {},
    { pending = true }: { pending?: boolean } = {},
) => {
    const store = configureStore({ reducer: { chat: chatReducer } });
    if (pending) {
        store.dispatch(
            setClarificationMessage({
                request_id: 'req-1',
                question: 'What have you already tried?',
            } as never),
        );
    }
    return render(
        <Provider store={store}>
            <RehearsedReplies replies={REPLIES} onReply={vi.fn()} disabled={false} {...props} />
        </Provider>,
    );
};

describe('answering a clarification without typing', () => {
    it('offers every rehearsed reply the Quick Task authored', () => {
        renderReplies();

        for (const reply of REPLIES) {
            expect(screen.getByRole('button', { name: reply })).toBeInTheDocument();
        }
    });

    it('submits the reply as the associate own words when tapped', () => {
        // Through the same submit path a typed answer takes. The clarification
        // seam (#21) records what arrives there as Attempted steps, and the
        // Simulated ticket (#22) carries them — a tap that took a different
        // route would be a beat whose record is empty two beats later.
        const onReply = vi.fn();
        renderReplies({ onReply });

        fireEvent.click(screen.getByRole('button', { name: REPLIES[1] }));

        expect(onReply).toHaveBeenCalledWith(REPLIES[1]);
    });

    it('offers nothing when no clarification is pending', () => {
        // The gate lives here rather than at the call site, so it cannot be
        // forgotten at a second one. Outside a clarification these chips are a
        // second way to start a turn, competing with the box.
        renderReplies({}, { pending: false });

        expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('offers nothing when the Quick Task authored none', () => {
        // Free-typed input, or any other beat. A surface may say nothing.
        renderReplies({ replies: [] });

        expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('stops offering them while an answer is in flight', () => {
        // One clarification takes one answer. A second tap while the first is
        // submitting is a second recorded step the associate never took, and
        // a recorded step is one the assistant will skip.
        renderReplies({ disabled: true });

        for (const reply of REPLIES) {
            expect(screen.getByRole('button', { name: reply })).toBeDisabled();
        }
    });
});
