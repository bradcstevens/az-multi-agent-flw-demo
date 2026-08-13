import { describe, expect, it } from 'vitest';

import reducer, { ticketRaised, ticketReset } from './ticketSlice';
import { conversationStarted, requestStarted } from './transparencySlice';

/**
 * The Simulated ticket's lifetime (issue #22).
 *
 * #24's lesson applied to a fourth surface: a value that was true when it was
 * rendered is not true forever, and the interesting question about every piece
 * of state on this surface is what clears it. A ticket's answer is *the
 * conversation* — a raised ticket is not a claim about the question in flight,
 * so a new question does not unraise it, but the next conversation is a
 * different fault and a different associate.
 */
const raised = (overrides: Record<string, unknown> = {}) => ({
    ticket_id: 'SIM-223-0041',
    status: 'submitted',
    fields: [
        { name: 'symptom', value: 'left head runs cold and slow' },
        { name: 'steps_attempted', value: 'Fitted a fresh paper filter' },
    ],
    ...overrides,
});

describe('the ticket slice', () => {
    it('starts with no ticket', () => {
        expect(reducer(undefined, { type: 'init' }).ticket).toBeNull();
    });

    it('holds the ticket the approval seam raised', () => {
        const state = reducer(undefined, ticketRaised(raised()));

        expect(state.ticket?.ticketId).toBe('SIM-223-0041');
    });

    it('carries the attempted steps the associate never re-typed', () => {
        const state = reducer(undefined, ticketRaised(raised()));

        expect(
            state.ticket?.fields.find((field) => field.name === 'steps_attempted')?.value,
        ).toBe('Fitted a fresh paper filter');
    });

    it('ignores a payload it cannot read rather than half-applying it', () => {
        const held = reducer(undefined, ticketRaised(raised()));

        const after = reducer(held, ticketRaised({ ticket_id: '' }));

        expect(after.ticket?.ticketId).toBe('SIM-223-0041');
    });

    it('survives a new question, because asking one does not unraise a ticket', () => {
        // The same reasoning the presenter alerts survive a new question on:
        // the ticket answered no question, so a new one does not make it
        // untrue. Only the Grounding panel's claim is about *this* answer.
        const held = reducer(undefined, ticketRaised(raised()));

        expect(reducer(held, requestStarted()).ticket?.ticketId).toBe('SIM-223-0041');
    });

    it('clears at the conversation boundary', () => {
        // The next conversation is a different fault. A ticket left on screen
        // across that boundary is a card describing equipment nobody is
        // looking at, quoting a number somebody could repeat.
        const held = reducer(undefined, ticketRaised(raised()));

        expect(reducer(held, conversationStarted()).ticket).toBeNull();
    });

    it('honours the transparency slice\'s boundary rather than declaring its own', () => {
        // The boundary is already dispatched from more than one place — the
        // `planId` effect and `resetPlanVariables`. A second action to
        // dispatch beside it is a second thing to forget at one of them, and
        // the symptom would be one conversation's ticket on the next
        // conversation's screen.
        const held = reducer(undefined, ticketRaised(raised()));

        expect(reducer(held, { type: conversationStarted.type }).ticket).toBeNull();
    });

    it('resets to claiming nothing', () => {
        const held = reducer(undefined, ticketRaised(raised()));

        expect(reducer(held, ticketReset()).ticket).toBeNull();
    });
});
