import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import ChatInput, {
    COUNTER_INFORMATIVE_FROM,
    MAX_MESSAGE_LENGTH,
} from './ChatInput';

const renderInput = (value: string) =>
    render(<ChatInput value={value} onChange={() => {}} />);

describe('the character counter', () => {
    it('says nothing beside the send control on an empty box', () => {
        // `0/5000` on a box nobody has typed into competes with the only
        // affordance that matters, and reports a limit that is 5000 characters
        // away (#56).
        renderInput('');

        expect(screen.queryByText(/\/5000/)).not.toBeInTheDocument();
    });

    it('appears in time to warn that the box is about to stop accepting input', () => {
        // Deferring it must not become deleting it: the textarea's `maxLength`
        // silently drops what is typed past the cap, and the counter is the
        // only thing that says so.
        renderInput('x'.repeat(COUNTER_INFORMATIVE_FROM));

        expect(
            screen.getByText(`${COUNTER_INFORMATIVE_FROM}/${MAX_MESSAGE_LENGTH}`),
        ).toBeInTheDocument();
    });
});
