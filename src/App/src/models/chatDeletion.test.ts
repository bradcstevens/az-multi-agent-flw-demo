import { describe, expect, it } from 'vitest';

import { PlanStatus } from './enums';
import {
    CONFIRM_DELETE_LABEL,
    DELETE_CHAT_LABEL,
    DELETE_CHAT_TITLE,
    DELETE_CHAT_WARNING,
    STILL_RUNNING_REASON,
    canDeleteChat,
    chatMenuLabel,
} from './chatDeletion';

describe('which chats may be deleted', () => {
    it('lets a finished chat go', () => {
        expect(canDeleteChat(PlanStatus.COMPLETED)).toBe(true);
    });

    it('lets the rehearsal debris go', () => {
        // Failed and canceled chats are what #74 put on screen, and clearing
        // them is why ADR-026 followed it.
        expect(canDeleteChat(PlanStatus.FAILED)).toBe(true);
        expect(canDeleteChat(PlanStatus.CANCELED)).toBe(true);
    });

    it('keeps a chat something may still be happening to', () => {
        // Not only `in_progress`. A plan the orchestrator has been handed and
        // has not started is as live as one it is halfway through.
        expect(canDeleteChat(PlanStatus.IN_PROGRESS)).toBe(false);
        expect(canDeleteChat(PlanStatus.CREATED)).toBe(false);
        expect(canDeleteChat(PlanStatus.APPROVED)).toBe(false);
    });

    it('keeps a chat whose state it cannot read', () => {
        // Fail-closed, matching the backend's own rule: *cannot tell* is not
        // *safe to delete*, and the panel offering a delete the route will
        // refuse is the surface claiming an action it does not have.
        expect(canDeleteChat('archived')).toBe(false);
        expect(canDeleteChat(undefined)).toBe(false);
        expect(canDeleteChat('')).toBe(false);
    });
});

describe('the words the control says', () => {
    it('says delete, because that is what happens now', () => {
        // ADR-026 supersedes ADR-022: the record really goes, so the label
        // that would have been a lie is now the only true one.
        expect(DELETE_CHAT_LABEL).toBe('Delete chat');
    });

    it('names the chat in the menu that opens it, so two rows are two menus', () => {
        expect(chatMenuLabel('How do I close the store?')).toContain(
            'How do I close the store?',
        );
    });

    it('says the deletion cannot be undone before it happens', () => {
        // Irreversible, three feet from a live audience (ADR-022's own worry,
        // which ADR-026 accepts rather than dismisses). The confirmation is
        // where that is said.
        expect(DELETE_CHAT_TITLE.toLowerCase()).toContain('delete');
        expect(DELETE_CHAT_WARNING.toLowerCase()).toContain('undone');
    });

    it('names the delete on the confirming button rather than saying "Yes"', () => {
        expect(CONFIRM_DELETE_LABEL.toLowerCase()).toContain('delete');
    });

    it('says why a running chat is kept', () => {
        expect(STILL_RUNNING_REASON.toLowerCase()).toContain('running');
    });
});
