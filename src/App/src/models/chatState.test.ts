import { describe, expect, it } from 'vitest';

import { PlanStatus } from './enums';
import { NO_CHATS_MESSAGE, chatStateLabel } from './chatState';

describe('what a row says about the state it is in', () => {
    it('names every state a plan can be persisted in', () => {
        // #74 lists chats in every state, `failed` and `canceled` included, so
        // an associate can tell a broken chat from a good one without opening
        // it. A state the list can show and cannot name is the same fault it
        // fixes, one layer down.
        expect(
            Object.values(PlanStatus).map((status) => chatStateLabel(status)),
        ).not.toContain('');
    });

    it('says the ones the associate actually meets in their own words', () => {
        expect(chatStateLabel(PlanStatus.IN_PROGRESS)).toBe('In progress');
        expect(chatStateLabel(PlanStatus.COMPLETED)).toBe('Completed');
        expect(chatStateLabel(PlanStatus.FAILED)).toBe('Failed');
        expect(chatStateLabel(PlanStatus.CANCELED)).toBe('Canceled');
    });

    it('says a state it has never heard of as itself', () => {
        // Total, because the label is read while building every row and the
        // set of statuses lives in the backend. A status added there must
        // reach the panel as itself rather than as a blank row or a throw.
        expect(chatStateLabel('queued')).toBe('Queued');
        expect(chatStateLabel('needs_review')).toBe('Needs review');
    });

    it('claims no state when the record reports none', () => {
        // A row saying "Unknown" is a claim about the chat; a row saying
        // nothing is the absence of one, which is what this is.
        expect(chatStateLabel(undefined)).toBe('');
        expect(chatStateLabel('   ')).toBe('');
    });
});

describe('what the list says when it is empty', () => {
    it('speaks of chats, because it is no longer a completed-only list', () => {
        expect(NO_CHATS_MESSAGE.toLowerCase()).toContain('chat');
        expect(NO_CHATS_MESSAGE.toLowerCase()).not.toContain('completed');
    });

    it('says "to show", because a hidden chat is not a deleted one', () => {
        // ADR-022's reason, kept: every plan stays in Cosmos, so a bare "No
        // chats" would have the panel claiming the records are gone.
        expect(NO_CHATS_MESSAGE).toMatch(/to show$/);
    });
});
