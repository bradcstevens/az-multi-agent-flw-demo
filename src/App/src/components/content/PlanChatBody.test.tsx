import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from '@fluentui/react-components';
import { Send } from '@/commonComponents/imports/bundleicons';

import PlanChatBody from './PlanChatBody';

const renderBody = (input: string, submitting = false) =>
    render(
        <PlanChatBody
            planData={{}}
            input={input}
            setInput={() => {}}
            submittingChatDisableInput={submitting}
            OnChatSubmit={vi.fn()}
            waitingForPlan={false}
            {...({} as any)}
        />,
    );

describe('the plan surface send control', () => {
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
