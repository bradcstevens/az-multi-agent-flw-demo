import { beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fireEvent, render, screen } from '@testing-library/react';
import { FluentProvider, teamsLightTheme } from '@fluentui/react-components';

import TaskList from './TaskList';
import { Task } from '@/models';
import {
    HIDDEN_COMPLETED_TASKS_KEY,
    HIDE_COMPLETED_LABEL,
    NO_COMPLETED_TASKS_MESSAGE,
    forgetHiddenCompletedTasks,
} from '../../models/hiddenCompletedTasks';

const completed = (id: string, name: string): Task => ({
    id,
    name,
    status: 'completed',
    date: '14 August 2026',
});

const MORNING = [
    completed('plan-1', 'How do I close the store?'),
    completed('plan-2', 'The register is frozen'),
];

const renderList = (completedTasks: Task[], props: Record<string, unknown> = {}) =>
    render(
        <FluentProvider theme={teamsLightTheme}>
            <TaskList
                completedTasks={completedTasks}
                onTaskSelect={vi.fn()}
                {...props}
            />
        </FluentProvider>,
    );

const hideControl = () => screen.getByRole('button', { name: HIDE_COMPLETED_LABEL });

beforeEach(() => {
    window.sessionStorage.clear();
    forgetHiddenCompletedTasks();
});

describe('the completed task list', () => {
    it('shows the morning of rehearsals it has been given', () => {
        renderList(MORNING);

        expect(screen.getByText('How do I close the store?')).toBeInTheDocument();
        expect(screen.getByText('The register is frozen')).toBeInTheDocument();
    });

    it('says so rather than opening onto blank space when there is nothing to show', () => {
        renderList([]);

        expect(screen.getByText(NO_COMPLETED_TASKS_MESSAGE)).toBeInTheDocument();
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
            join(__dirname, 'TaskList.tsx'),
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

        expect(screen.getByText(NO_COMPLETED_TASKS_MESSAGE)).toBeInTheDocument();
    });

    it('holds across a reload in the same tab', () => {
        const { unmount } = renderList(MORNING);
        fireEvent.click(hideControl());
        unmount();

        // What the panel would read on the other side of a refresh.
        expect(
            JSON.parse(window.sessionStorage.getItem(HIDDEN_COMPLETED_TASKS_KEY) ?? 'null'),
        ).toEqual(['plan-1', 'plan-2']);

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
        expect(screen.queryByText(NO_COMPLETED_TASKS_MESSAGE)).not.toBeInTheDocument();
    });
});
