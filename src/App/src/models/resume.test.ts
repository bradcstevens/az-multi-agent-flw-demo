import { describe, expect, it } from 'vitest';

import {
    ANSWER_THE_QUESTION,
    CANNOT_CONTINUE,
    CONTINUE_THIS_CHAT,
    NOTHING_TO_CONTINUE,
    TURN_STILL_WORKING,
    placeholderFor,
    turnModeFor,
} from './resume';

/**
 * What a turn typed into the chat surface's box is (#77, ADR-027).
 *
 * Stated once, because two places need the answer and they had already
 * disagreed: `PlanChatBody` decides whether the box may be used at all, and
 * `ChatPage` decides where what was typed is sent. The box being open while
 * the submit path had nowhere to send from is exactly the shape of #68 —
 * a clarification posted against an empty `request_id` — read from the other
 * side.
 */
describe('what a turn typed into this chat is', () => {
    it('answers the Clarification the backend asked, when one is pending', () => {
        expect(turnModeFor('req-1', 'session-223')).toBe('clarification');
    });

    it('continues this chat when nothing has asked a question', () => {
        // ADR-027: a turn sent from inside a Chat carries *that* Chat's
        // `session_id` rather than minting a new one, which is what makes the
        // persisted troubleshooting record, identity, lane and ticket survive.
        expect(turnModeFor(null, 'session-223')).toBe('resume');
    });

    it('answers the clarification even when the session is unknown', () => {
        // A clarification is posted against a `request_id` and a `plan_id`,
        // never against a session, so a chat whose session this build cannot
        // read can still answer the question it was asked.
        expect(turnModeFor('req-1', undefined)).toBe('clarification');
    });

    it('does neither when there is no session to continue', () => {
        // Fail-closed, the rule this surface's irreversible and
        // identity-bearing paths already run on: a chat the surface cannot
        // name a session for is one it cannot continue, and minting a fresh
        // session here would silently start a *new* conversation under the
        // heading of an old one.
        expect(turnModeFor(null, undefined)).toBe('none');
        expect(turnModeFor('', '')).toBe('none');
        expect(turnModeFor(null, '   ')).toBe('none');
    });
});

describe('what the box invites', () => {
    it('invites an answer while a question is pending', () => {
        expect(placeholderFor('clarification')).toBe(ANSWER_THE_QUESTION);
    });

    it('invites another turn in this chat when none is', () => {
        expect(placeholderFor('resume')).toBe(CONTINUE_THIS_CHAT);
        expect(CONTINUE_THIS_CHAT).not.toBe(ANSWER_THE_QUESTION);
    });

    it('invites nothing it cannot carry', () => {
        // A placeholder is an invitation, and a box that cannot send is a box
        // that must not extend one — the quieter half of #68's fault.
        expect(placeholderFor('none')).toBe('');
    });

    it('is total, so a mode added later cannot render a blank invitation', () => {
        const modes = ['clarification', 'resume', 'none'] as const;
        modes.forEach((mode) => expect(typeof placeholderFor(mode)).toBe('string'));
    });
});

describe('what the surface says while a turn is working', () => {
    it('is a wait, and not the unreachable chat', () => {
        // Two different reasons a box is closed. Saying "this conversation
        // cannot be continued" over a chat that is merely busy is the surface
        // reporting a permanent state for a momentary one.
        expect(TURN_STILL_WORKING).not.toBe(NOTHING_TO_CONTINUE);
        expect(TURN_STILL_WORKING).toMatch(/\S/);
    });
});

describe('what the surface says when it cannot continue', () => {
    it('says why the box is closed rather than only dimming it', () => {
        expect(NOTHING_TO_CONTINUE).toMatch(/\S/);
    });

    it('says a submitted turn could not be continued in different words', () => {
        // The closed box and the refused submit are different events — one is
        // a state the associate reads, the other is a thing that just failed —
        // so they are not the same sentence.
        expect(CANNOT_CONTINUE).not.toBe(NOTHING_TO_CONTINUE);
        expect(CANNOT_CONTINUE).toMatch(/\S/);
    });
});
