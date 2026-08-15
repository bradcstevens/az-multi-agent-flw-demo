import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from '@fluentui/react-components';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { Send } from '@/commonComponents/imports/bundleicons';
import chatReducer, { setClarificationMessage } from '@/store/slices/chatSlice';
import progressReducer from '@/store/slices/progressSlice';

import PlanChatBody from './PlanChatBody';
import {
    ANSWER_THE_QUESTION,
    CONTINUE_THIS_CHAT,
    NOTHING_TO_CONTINUE,
    TURN_STILL_WORKING,
} from '@/models/resume';

const renderBody = (
    input: string,
    submitting = false,
    { pending = true, sessionId = 'session-223', turnInFlight = false }:
        { pending?: boolean; sessionId?: string | null; turnInFlight?: boolean } = {},
) => {
    const store = configureStore({
        reducer: { chat: chatReducer, progress: progressReducer },
    });
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
            <PlanChatBody
                planData={{ plan: { session_id: sessionId } }}
                input={input}
                setInput={() => {}}
                submittingChatDisableInput={submitting}
                turnInFlight={turnInFlight}
                OnChatSubmit={vi.fn()}
                {...({} as any)}
            />
        </Provider>,
    );
};

describe('the chat surface send control', () => {
    it('is named for what it does', () => {
        // The same unnamed icon as the home surface (#56), on the surface where
        // the conversation actually continues.
        renderBody('when does the safe close?');

        expect(
            screen.getByRole('button', { name: 'Send message' }),
        ).toBeInTheDocument();
    });

    it('is rendered as the primary action of the input', () => {
        renderBody('when does the safe close?');
        const rendered = new Set(
            screen.getByRole('button', { name: 'Send message' }).classList,
        );

        const { container, unmount } = render(
            <Button appearance="primary" icon={<Send />} aria-label="reference" />,
        );
        const primary = Array.from(container.querySelector('button')!.classList);
        unmount();

        expect(primary.every((c) => rendered.has(c))).toBe(true);
    });

    it('says it has nothing to send rather than only looking faded', () => {
        renderBody('   ');

        expect(screen.getByRole('button', { name: 'Send message' })).toHaveAttribute(
            'aria-disabled',
            'true',
        );
    });
});


describe('the chat surface message box outside a clarification', () => {
    /*
      The box is the **Clarification** seam's other half *and* the resume path
      (#77, ADR-027): with no question pending, a turn typed here continues
      this **Chat**'s **Session**. #68's rule survives that whole — a surface
      may say nothing, but it may not say something that is not so — so what
      the box invites has to change with what it is about to do, and the box
      may still only open over a submit path that has somewhere to send.
    */
    it('invites another turn in this chat rather than an answer', () => {
        renderBody('', false, { pending: false });

        expect(
            screen.getByPlaceholderText(CONTINUE_THIS_CHAT),
        ).toBeInTheDocument();
    });

    it('takes input, because there is now somewhere to send it', () => {
        renderBody('', false, { pending: false });

        expect(screen.getByRole('textbox')).not.toBeDisabled();
    });

    it('says nothing is waiting on a reply no longer, because that is not why the box is open', () => {
        renderBody('', false, { pending: false });

        expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });

    it('invites an answer, not another turn, while a clarification is pending', () => {
        // The placeholder is the only place the surface says which of the two
        // acts is about to happen, so the two may not read the same.
        renderBody('');

        expect(screen.getByPlaceholderText(ANSWER_THE_QUESTION)).toBeInTheDocument();
        expect(
            screen.queryByPlaceholderText(CONTINUE_THIS_CHAT),
        ).not.toBeInTheDocument();
    });

    it('opens on a question carrying no request id — as a resume, not as an answer', () => {
        // Nothing can be posted against an identifier the backend never sent,
        // so such a question is still not one this surface can answer. It is
        // no longer a reason to close the box, only a reason for what is typed
        // to be a new turn.
        const store = configureStore({
            reducer: { chat: chatReducer, progress: progressReducer },
        });
        store.dispatch(
            setClarificationMessage({
                request_id: '',
                question: 'What have you already tried?',
            } as never),
        );

        render(
            <Provider store={store}>
                <PlanChatBody
                    planData={{ plan: { session_id: 'session-223' } }}
                    input=""
                    setInput={() => {}}
                    submittingChatDisableInput={false}
                    OnChatSubmit={vi.fn()}
                    {...({} as any)}
                />
            </Provider>,
        );

        expect(
            screen.getByPlaceholderText(CONTINUE_THIS_CHAT),
        ).toBeInTheDocument();
        expect(screen.getByRole('textbox')).not.toBeDisabled();
    });
});

describe('the chat surface message box with no session to continue', () => {
    /*
      Fail-closed. A chat the surface cannot name a session for cannot be
      continued — resuming into a minted one would start a *new* conversation
      under an old heading, losing the **Attempted steps**, the **Lane** and
      the **Simulated ticket** that are the whole of what resume carries.
    */
    it('says why it cannot be used rather than only looking faded', () => {
        renderBody('', false, { pending: false, sessionId: null });

        expect(screen.getByRole('status')).toHaveTextContent(NOTHING_TO_CONTINUE);
    });

    it('withdraws the invitation to type rather than only dimming it', () => {
        renderBody('', false, { pending: false, sessionId: null });

        expect(
            screen.queryByPlaceholderText(CONTINUE_THIS_CHAT),
        ).not.toBeInTheDocument();
    });

    it('refuses input, so nothing typed can be dropped', () => {
        renderBody('', false, { pending: false, sessionId: null });

        expect(screen.getByRole('textbox')).toBeDisabled();
    });

    it('still answers a pending clarification, which needs no session', () => {
        renderBody('', false, { sessionId: null });

        expect(screen.queryByRole('status')).not.toBeInTheDocument();
        expect(screen.getByRole('textbox')).not.toBeDisabled();
    });
});


describe('while this chat is still working on the last turn', () => {
    /*
      `process_request` cancels whatever orchestration that user already had
      running before it schedules the next one, so a **Resume** turn typed over
      a working one does not queue behind it — it takes its place, and the
      answer the associate was waiting for never arrives. The box refuses.
    */
    it('does not invite a turn that would replace the one running', () => {
        renderBody('what about the safe?', false, { pending: false, turnInFlight: true });

        expect(screen.getByRole('button', { name: 'Send message' })).toHaveAttribute(
            'aria-disabled',
            'true',
        );
    });

    it('says it is a wait, not an unreachable chat', () => {
        renderBody('what about the safe?', false, { pending: false, turnInFlight: true });

        expect(screen.getByRole('status')).toHaveTextContent(TURN_STILL_WORKING);
        expect(screen.queryByText(NOTHING_TO_CONTINUE)).not.toBeInTheDocument();
    });

    it('still answers a Clarification, which is what the turn is waiting for', () => {
        // The spinner is up over a turn that cannot progress until the box is
        // used. Closing it here is the deadlock #68 already cost this surface.
        renderBody('I reset the reader', false, { pending: true, turnInFlight: true });

        expect(
            screen.getByRole('button', { name: 'Send message' }),
        ).not.toHaveAttribute('aria-disabled', 'true');
        expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });
});
