import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from '@fluentui/react-components';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { Send } from '@/commonComponents/imports/bundleicons';
import chatReducer, { setClarificationMessage } from '@/store/slices/chatSlice';

import PlanChatBody, { NOTHING_TO_ANSWER, TYPE_YOUR_MESSAGE } from './PlanChatBody';

const renderBody = (
    input: string,
    submitting = false,
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
            <PlanChatBody
                planData={{}}
                input={input}
                setInput={() => {}}
                submittingChatDisableInput={submitting}
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
      The governing rule, applied to the one control on this surface (#68): a
      surface may say nothing, but it may not say something that is not so. The
      box answers a **Clarification** and nothing else, so with none pending it
      invited a message it would silently drop.
    */
    it('says why it cannot be used when nothing has asked a question', () => {
        renderBody('', false, { pending: false });

        expect(screen.getByRole('status')).toHaveTextContent(NOTHING_TO_ANSWER);
    });

    it('withdraws the invitation to type rather than only dimming it', () => {
        renderBody('', false, { pending: false });

        expect(
            screen.queryByPlaceholderText(TYPE_YOUR_MESSAGE),
        ).not.toBeInTheDocument();
    });

    it('refuses input, so nothing typed can be dropped', () => {
        renderBody('', false, { pending: false });

        expect(screen.getByRole('textbox')).toBeDisabled();
    });

    it('says nothing of the sort while a clarification is pending', () => {
        renderBody('');

        expect(screen.queryByRole('status')).not.toBeInTheDocument();
        expect(screen.getByRole('textbox')).not.toBeDisabled();
    });

    it('does not open on a question carrying no request id', () => {
        // Nothing can be posted against an identifier the backend never sent,
        // so such a question is not one this surface can answer — and not one
        // it opens the box for.
        const store = configureStore({ reducer: { chat: chatReducer } });
        store.dispatch(
            setClarificationMessage({
                request_id: '',
                question: 'What have you already tried?',
            } as never),
        );

        render(
            <Provider store={store}>
                <PlanChatBody
                    planData={{}}
                    input=""
                    setInput={() => {}}
                    submittingChatDisableInput={false}
                    OnChatSubmit={vi.fn()}
                    {...({} as any)}
                />
            </Provider>,
        );

        expect(screen.getByRole('status')).toHaveTextContent(NOTHING_TO_ANSWER);
        expect(screen.getByRole('textbox')).toBeDisabled();
    });
});
