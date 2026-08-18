import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { FluentProvider, teamsLightTheme } from '@fluentui/react-components';

import ChatList from './ChatList';
import { Chat } from '@/models';
import { PlanStatus } from '../../models/enums';
import { NO_CHATS_MESSAGE, chatStateLabel } from '../../models/chatState';
import {
    CANCEL_DELETE_LABEL,
    CONFIRM_DELETE_LABEL,
    DELETE_CHAT_LABEL,
    DELETE_CHAT_WARNING,
    DELETE_FAILED_TITLE,
    END_AND_DELETE_LABEL,
    STILL_RUNNING_REASON,
    chatMenuLabel,
} from '../../models/chatDeletion';

const chat = (id: string, name: string, status: PlanStatus): Chat => ({
    id,
    planId: `${id}-latest`,
    name,
    status,
    date: '14 August 2026',
});

const completed = (id: string, name: string): Chat =>
    chat(id, name, PlanStatus.COMPLETED);

const MORNING = [
    completed('chat-1', 'How do I close the store?'),
    completed('chat-2', 'The register is frozen'),
];

const renderList = (chats: Chat[], props: Record<string, unknown> = {}) =>
    render(
        <FluentProvider theme={teamsLightTheme}>
            <ChatList
                chats={chats}
                onChatSelect={vi.fn()}
                onChatDelete={vi.fn()}
                {...props}
            />
        </FluentProvider>,
    );

/** Open a row's overflow menu the way a mouse does. */
const openMenuFor = (name: string) => {
    fireEvent.click(screen.getByRole('button', { name: chatMenuLabel(name) }));
};

const deleteItem = () => screen.getByRole('menuitem', { name: DELETE_CHAT_LABEL });

describe('the chat list', () => {
    it('shows the morning of rehearsals it has been given', () => {
        renderList(MORNING);

        expect(screen.getByText('How do I close the store?')).toBeInTheDocument();
        expect(screen.getByText('The register is frozen')).toBeInTheDocument();
    });

    it('says so rather than opening onto blank space when there is nothing to show', () => {
        renderList([]);

        expect(screen.getByText(NO_CHATS_MESSAGE)).toBeInTheDocument();
    });

    it('offers no control that hides a chat instead of deleting it', () => {
        /*
          ADR-026 supersedes ADR-022: the hide is gone rather than standing
          beside the delete. Two controls, one of which quietly leaves the
          record behind, is the ambiguity the delete label exists to remove.

          The menu is opened before looking. A hide reintroduced where it would
          now naturally go — beside the delete, as a `MenuItem` — is invisible
          to a check that only reads the closed row. Found by review.
        */
        renderList(MORNING);
        openMenuFor('How do I close the store?');

        expect(screen.getByRole('menu')).toBeInTheDocument();
        expect(screen.getAllByRole('menuitem')).toHaveLength(1);
        expect(
            screen.queryByRole('menuitem', { name: /hide|archive/i }),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByRole('button', { name: /hide|archive/i }),
        ).not.toBeInTheDocument();
    });
});

describe('the row‘s overflow menu', () => {
    /*
      The inverted guard (#75). ADR-022 removed a `Menu` carrying a
      `MenuTrigger` and no `MenuPopover`, having measured that on
      `@fluentui/react-components` 9.64 such a menu renders *nothing* — the
      trigger never reaches the DOM, so no test, no screen reader and no click
      could see it. That is why the old check was a source read. The pattern is
      live now, so every assertion here is against the DOM instead: build the
      menu wrong and the panel ships an invisible delete with the suite green.
    */

    it('puts a trigger on the row that the DOM can actually see', () => {
        renderList(MORNING);

        expect(
            screen.getByRole('button', { name: chatMenuLabel('How do I close the store?') }),
        ).toBeInTheDocument();
    });

    it('names each row‘s menu after its own chat', () => {
        // One of these per row. A screen reader offered several identically
        // named buttons cannot say which conversation it is about to destroy.
        renderList(MORNING);

        expect(
            screen.getByRole('button', { name: chatMenuLabel('The register is frozen') }),
        ).toBeInTheDocument();
    });

    it('opens from the keyboard, not only from a mouse', () => {
        // ArrowDown is the menu's own keyboard opener. Enter and Space reach it
        // through the click a browser synthesises on a focused `button`, which
        // jsdom does not — so this asserts the path Fluent implements itself
        // rather than one this environment cannot produce.
        renderList(MORNING);

        const trigger = screen.getByRole('button', {
            name: chatMenuLabel('How do I close the store?'),
        });
        trigger.focus();
        fireEvent.keyDown(trigger, { key: 'ArrowDown' });

        expect(deleteItem()).toBeInTheDocument();
    });

    it('reaches a delete item through a popover that renders', () => {
        renderList(MORNING);

        openMenuFor('How do I close the store?');

        expect(deleteItem()).toBeInTheDocument();
    });

    it('does not open the chat when the menu is used', () => {
        // The trigger sits inside the row, and the row is itself a button.
        const onChatSelect = vi.fn();
        renderList(MORNING, { onChatSelect });

        openMenuFor('How do I close the store?');

        expect(onChatSelect).not.toHaveBeenCalled();
    });
});

describe('deleting one chat', () => {
    it('asks before it destroys anything', async () => {
        const onChatDelete = vi.fn();
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());

        expect(await screen.findByText(DELETE_CHAT_WARNING)).toBeInTheDocument();
        expect(onChatDelete).not.toHaveBeenCalled();
    });

    it('names the chat it is about to delete', async () => {
        // Two rows, one dialog. A confirmation that does not name the
        // conversation is a confirmation nobody can actually check.
        renderList(MORNING);

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());

        const dialog = await screen.findByRole('dialog');
        expect(dialog).toHaveTextContent('The register is frozen');
    });

    it('deletes the chat the menu was opened on, once confirmed', async () => {
        const onChatDelete = vi.fn().mockResolvedValue(undefined);
        renderList(MORNING, { onChatDelete });

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_LABEL }),
        );

        await waitFor(() =>
            expect(onChatDelete).toHaveBeenCalledWith(
                expect.objectContaining({ id: 'chat-2' }),
            ),
        );
    });

    it('destroys nothing when the confirmation is declined', async () => {
        const onChatDelete = vi.fn();
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CANCEL_DELETE_LABEL }),
        );

        await waitFor(() =>
            expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
        );
        expect(onChatDelete).not.toHaveBeenCalled();
    });

    it('leaves the confirmation open when the delete fails', async () => {
        // A dialog that closes on a rejected delete tells the associate the
        // chat is gone. It is still in Cosmos, and the row is about to come
        // back on the next load.
        const onChatDelete = vi.fn().mockRejectedValue(new Error('conflict'));
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_LABEL }),
        );

        await waitFor(() => expect(onChatDelete).toHaveBeenCalled());
        expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('says why the delete failed, where the associate is looking', async () => {
        /*
          Found by review. The panel holds a Fluent `useToastController`
          bound to a `Toaster` this application has never mounted, so a
          failure thrown to a toast is a failure nobody is told about — a
          confirmation that stays open with the button apparently doing
          nothing. The reason belongs in the dialog that is already on screen.
        */
        const onChatDelete = vi
            .fn()
            .mockRejectedValue(new Error(STILL_RUNNING_REASON));
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_LABEL }),
        );

        const said = await screen.findByRole('alert');
        expect(said).toHaveTextContent(DELETE_FAILED_TITLE);
        expect(said).toHaveTextContent(STILL_RUNNING_REASON);
    });

    it('forgets the failure when the confirmation is dismissed', async () => {
        // Otherwise the next chat's confirmation opens already carrying the
        // last one's error, which is the dialog reporting a delete that has
        // not been attempted.
        const onChatDelete = vi.fn().mockRejectedValue(new Error('conflict'));
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_LABEL }),
        );
        await screen.findByRole('alert');
        fireEvent.click(screen.getByRole('button', { name: CANCEL_DELETE_LABEL }));

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());

        expect(await screen.findByRole('dialog')).toBeInTheDocument();
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
});

describe('a running chat is a door rather than a wall', () => {
    const RUNNING = chat('chat-running', 'The register is frozen', PlanStatus.IN_PROGRESS);

    it('offers the delete rather than refusing it', () => {
        // #122, ADR-031 §5. The turn a walk-away destroyed leaves a row at
        // `in_progress` for ever, and a refusal is the only thing the surface
        // ever said about it. The way out is to end the turn, never to loosen
        // the guard — so the control is offered and says what it will do.
        renderList([RUNNING]);

        openMenuFor('The register is frozen');

        expect(deleteItem()).not.toHaveAttribute('aria-disabled', 'true');
    });

    it('says the turn ends first, in the words the route answers with', () => {
        renderList([RUNNING]);

        openMenuFor('The register is frozen');

        expect(screen.getByText(STILL_RUNNING_REASON)).toBeInTheDocument();
    });

    it('names the act on the button that performs it', async () => {
        // ADR-033's discipline at the confirmation: the associate is about to
        // end an answer in progress, so the button says so rather than
        // repeating the label of a delete that takes nothing else with it.
        renderList([RUNNING]);

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());

        expect(
            await screen.findByRole('button', { name: END_AND_DELETE_LABEL }),
        ).toBeInTheDocument();
        expect(
            screen.queryByRole('button', { name: CONFIRM_DELETE_LABEL }),
        ).not.toBeInTheDocument();
    });

    it('states what is ended as well as what is destroyed', async () => {
        renderList([RUNNING]);

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());

        const confirmation = await screen.findByRole('dialog');
        expect(confirmation).toHaveTextContent(STILL_RUNNING_REASON);
        expect(confirmation).toHaveTextContent(DELETE_CHAT_WARNING);
    });

    it('deletes the chat the confirmation named', async () => {
        const onChatDelete = vi.fn().mockResolvedValue(undefined);
        renderList([RUNNING], { onChatDelete });

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: END_AND_DELETE_LABEL }),
        );

        await waitFor(() => expect(onChatDelete).toHaveBeenCalledWith(RUNNING));
    });

    it('is the same door for a state no label can be read from', () => {
        // Fail-closed, still: a status this build does not know is a chat
        // something may still be happening to, so the way through it is the
        // one that ends a turn first rather than the one that assumes none.
        renderList([{ ...RUNNING, status: 'archived' as PlanStatus }]);

        openMenuFor('The register is frozen');

        expect(deleteItem()).not.toHaveAttribute('aria-disabled', 'true');
    });

    it('says nothing about ending a turn for a chat that already settled', async () => {
        // The offer is about the turn in flight. Made over a finished chat it
        // would be the surface describing an act it is not performing.
        renderList(MORNING);

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());

        const confirmation = await screen.findByRole('dialog');
        expect(confirmation).not.toHaveTextContent(STILL_RUNNING_REASON);
        expect(
            screen.getByRole('button', { name: CONFIRM_DELETE_LABEL }),
        ).toBeInTheDocument();
    });
});

describe('the list holds chats in every state', () => {
    // #74. `GET /plans` filtered to `completed`, so the chat most worth
    // resuming — the one that did not finish — never reached this panel.
    const RUNNING = chat('chat-running', 'The register is frozen', PlanStatus.IN_PROGRESS);
    const FAILED = chat('chat-failed', 'How do I swap a shift?', PlanStatus.FAILED);
    const DONE = completed('chat-done', 'How do I close the store?');

    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('shows a chat that is still running', () => {
        renderList([RUNNING]);

        expect(screen.getByText('The register is frozen')).toBeInTheDocument();
    });

    it('shows a failed chat', () => {
        renderList([FAILED]);

        expect(screen.getByText('How do I swap a shift?')).toBeInTheDocument();
    });

    it('states each row‘s state, so a broken chat need not be opened to find out', () => {
        renderList([RUNNING, FAILED, DONE]);

        // Anchored: the row's accessible name begins with the chat's name,
        // while its menu trigger's is *"More options for …"*.
        const stateOf = (name: RegExp) =>
            screen.getByRole('button', { name }).textContent ?? '';

        expect(stateOf(/^The register is frozen/)).toContain(
            chatStateLabel(PlanStatus.IN_PROGRESS),
        );
        expect(stateOf(/^How do I swap a shift\?/)).toContain(
            chatStateLabel(PlanStatus.FAILED),
        );
        expect(stateOf(/^How do I close the store\?/)).toContain(
            chatStateLabel(PlanStatus.COMPLETED),
        );
    });

    it('lets the rehearsal debris go, which is why deletion followed #74', () => {
        renderList([FAILED]);

        openMenuFor('How do I swap a shift?');

        expect(deleteItem()).not.toHaveAttribute('aria-disabled', 'true');
    });
});
