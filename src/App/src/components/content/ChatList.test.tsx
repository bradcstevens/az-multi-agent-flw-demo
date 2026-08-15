import { beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fireEvent, render, screen } from '@testing-library/react';
import { FluentProvider, teamsLightTheme } from '@fluentui/react-components';

import ChatList from './ChatList';
import { Chat } from '@/models';
import { PlanStatus } from '../../models/enums';
import { NO_CHATS_MESSAGE, chatStateLabel } from '../../models/chatState';
import {
    HIDDEN_COMPLETED_TASKS_KEY,
    HIDE_COMPLETED_LABEL,
    forgetHiddenCompletedTasks,
} from '../../models/hiddenCompletedTasks';

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
                {...props}
            />
        </FluentProvider>,
    );

const hideControl = () => screen.getByRole('button', { name: HIDE_COMPLETED_LABEL });

beforeEach(() => {
    window.sessionStorage.clear();
    forgetHiddenCompletedTasks();
});

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

    it('carries no button on the row, because on stage someone will click it', () => {
        // The live half of the guard: any button a row grows from here has to
        // earn its name, and this fails when one appears unnamed.
        renderList(MORNING);

        const rowButtons = screen
            .getAllByRole('button')
            .filter(
                (button) =>
                    !button.classList.contains('task-tab') &&
                    button.closest('.task-tab'),
            );

        expect(rowButtons).toHaveLength(0);
    });

    it('carries no `MenuTrigger` the DOM cannot see', () => {
        // Measured while removing it: on `@fluentui/react-components` 9.64 a
        // `Menu` with a `MenuTrigger` and no `MenuPopover` renders *nothing* —
        // the trigger never reaches the DOM. So the dead button this ticket
        // removes was invisible to the assertion above, and to a screen reader,
        // and to a click. A DOM guard for it would be inert, which is the
        // failure #25 already found once; the file itself is the only place the
        // pattern is visible.
        const source = readFileSync(
            join(__dirname, 'ChatList.tsx'),
            'utf-8',
        ).replace(/\/\*[\s\S]*?\*\//g, '');

        expect(source).not.toMatch(/<MenuTrigger/);
    });
});

describe('hiding the completed tasks', () => {
    it('offers a control named for what it does', () => {
        // ADR-022: it hides, it does not delete, and the label is the whole
        // reason that is honest rather than a lie the audience cannot check.
        renderList(MORNING);

        expect(hideControl()).toBeInTheDocument();
        expect(
            screen.queryByRole('button', { name: /delete|remove|clear|archive/i }),
        ).not.toBeInTheDocument();
    });

    it('hides every currently-completed task from view', () => {
        renderList(MORNING);

        fireEvent.click(hideControl());

        expect(screen.queryByText('How do I close the store?')).not.toBeInTheDocument();
        expect(screen.queryByText('The register is frozen')).not.toBeInTheDocument();
    });

    it('leaves the empty state behind, which is true whether empty or hidden', () => {
        renderList(MORNING);

        fireEvent.click(hideControl());

        expect(screen.getByText(NO_CHATS_MESSAGE)).toBeInTheDocument();
    });

    it('holds across a reload in the same tab', () => {
        const { unmount } = renderList(MORNING);
        fireEvent.click(hideControl());
        unmount();

        // What the panel would read on the other side of a refresh.
        expect(
            JSON.parse(window.sessionStorage.getItem(HIDDEN_COMPLETED_TASKS_KEY) ?? 'null'),
        ).toEqual(['chat-1', 'chat-2']);

        renderList(MORNING);
        expect(screen.queryByText('How do I close the store?')).not.toBeInTheDocument();
    });

    it('is gone in a fresh tab, which is a fresh demonstration', () => {
        renderList(MORNING);

        fireEvent.click(hideControl());

        expect(window.localStorage.getItem(HIDDEN_COMPLETED_TASKS_KEY)).toBeNull();
        expect(window.localStorage.length).toBe(0);
    });

    it('still shows a task that completes after the clear', () => {
        // A set of plan ids, not a global flag. "Stay hidden until I unhide" is
        // a different feature and is deliberately not this one.
        const { unmount } = renderList(MORNING);
        fireEvent.click(hideControl());
        unmount();

        renderList([...MORNING, completed('plan-3', 'How do I swap a shift?')]);

        expect(screen.getByText('How do I swap a shift?')).toBeInTheDocument();
        expect(screen.queryByText('How do I close the store?')).not.toBeInTheDocument();
    });

    it('keeps its place in the tab order when there is nothing left to hide', () => {
        // A natively-disabled control leaves the tab order, so the only
        // affordance on this panel would vanish for a keyboard user instead of
        // saying why it cannot be used (#56's finding, same shape).
        renderList([]);

        expect(hideControl()).toHaveAttribute('aria-disabled', 'true');
        expect(hideControl()).not.toHaveAttribute('disabled');
    });

    it('does nothing when there is nothing left to hide', () => {
        renderList([]);

        fireEvent.click(hideControl());

        expect(window.sessionStorage.getItem(HIDDEN_COMPLETED_TASKS_KEY)).toBeNull();
    });

    it('is not offered while the list is still loading', () => {
        // Hiding what has not arrived hides nothing and reads as a broken
        // control.
        renderList([], { loading: true });

        expect(
            screen.queryByRole('button', { name: HIDE_COMPLETED_LABEL }),
        ).not.toBeInTheDocument();
        expect(screen.queryByText(NO_CHATS_MESSAGE)).not.toBeInTheDocument();
    });
});

describe('the list holds chats in every state', () => {
    // #74. `GET /plans` filtered to `completed`, so the chat most worth
    // resuming — the one that did not finish — never reached this panel.
    const RUNNING = chat('chat-running', 'The register is frozen', PlanStatus.IN_PROGRESS);
    const FAILED = chat('chat-failed', 'How do I swap a shift?', PlanStatus.FAILED);
    const DONE = completed('chat-done', 'How do I close the store?');

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

        const stateOf = (name: string | RegExp) =>
            screen.getByRole('button', { name }).textContent ?? '';

        expect(stateOf(/register is frozen/)).toContain(
            chatStateLabel(PlanStatus.IN_PROGRESS),
        );
        expect(stateOf(/swap a shift/)).toContain(chatStateLabel(PlanStatus.FAILED));
        expect(stateOf(/close the store/)).toContain(
            chatStateLabel(PlanStatus.COMPLETED),
        );
    });

    it('hides only the completed chats, because that is what the control says', () => {
        // ADR-022's label is *"Hide completed tasks"*. With every state listed,
        // hiding whatever the list happens to hold would take a running chat
        // with it — the control claiming an action it was not given.
        renderList([RUNNING, DONE]);

        fireEvent.click(hideControl());

        expect(screen.getByText('The register is frozen')).toBeInTheDocument();
        expect(screen.queryByText('How do I close the store?')).not.toBeInTheDocument();
    });

    it('shows a hidden chat again the moment it is running', () => {
        // The hide is scoped to completed chats, and a chat's id is its
        // `session_id` while its state is its latest plan's (#71). A chat
        // hidden while finished and then resumed is a *running* chat, and a
        // control named for completed ones may not still be suppressing it —
        // the same rule as ADR-022's "a task that completes after the clear
        // still appears", read from the other side.
        const { unmount } = renderList([DONE]);
        fireEvent.click(hideControl());
        unmount();

        renderList([{ ...DONE, status: PlanStatus.IN_PROGRESS }]);

        expect(screen.getByText('How do I close the store?')).toBeInTheDocument();
    });

    it('says there is nothing to hide when nothing has finished', () => {
        renderList([RUNNING]);

        expect(hideControl()).toHaveAttribute('aria-disabled', 'true');
    });
});
