import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

vi.mock('../../store/TaskService', () => ({
    TaskService: { createPlan: vi.fn() },
}));

import HomeInput from './HomeInput';
import { TaskService } from '../../store/TaskService';
import transparencyReducer from '@/store/slices/transparencySlice';
import { ASSISTANT_NAME } from '../../models/storeSurface';

const renderInput = (team: any) =>
    render(
        <Provider store={configureStore({ reducer: { transparency: transparencyReducer } })}>
            <MemoryRouter>
                <HomeInput selectedTeam={team} />
            </MemoryRouter>
        </Provider>,
    );

/**
 * The six Quick Tasks in the shape the backend sends them (issue #26). The
 * lanes and the prompts are the store pack's business — `test_store_pack.py`
 * is what holds those to the corpus and the routers. What is asserted here is
 * that whatever the pack declares, the surface renders all of it, badges it
 * with the lane it declared, and carries that declaration into the request.
 */
const SIX_TASKS = [
    { id: 'task-223-procedure', name: 'Close the store', prompt: 'How do I close the store?', created: '', creator: '', logo: 'BookMarked', lane: 'fast' },
    { id: 'task-223-honest-miss', name: 'Restart the car wash', prompt: 'How do I restart the car wash?', created: '', creator: '', logo: 'Search', lane: 'fast' },
    { id: 'task-223-troubleshooting', name: 'The coffee brewer is down', prompt: 'The coffee brewer is down.', created: '', creator: '', logo: 'Wrench', lane: 'fast' },
    { id: 'task-223-escalation', name: "I can't fix it", prompt: 'I have tried everything and I need someone to come out.', created: '', creator: '', logo: 'Document', lane: 'deliberate' },
    { id: 'task-223-identity', name: 'How much PTO do I have?', prompt: 'My name is Tanya, how much PTO do I have?', created: '', creator: '', logo: 'Shield', lane: 'fast' },
    { id: 'task-223-shift-tasks', name: 'What is due this shift?', prompt: 'What tasks are due on this shift?', created: '', creator: '', logo: '📋', lane: 'fast' },
];

const walkthrough = (tasks: any[] = SIX_TASKS) => ({
    team_id: '00000000-0000-0000-0000-000000000223',
    name: ASSISTANT_NAME,
    agents: [],
    starting_tasks: tasks,
});

const STYLESHEET = join(__dirname, '..', '..', 'styles', 'HomeInput.css');

beforeEach(() => {
    vi.mocked(TaskService.createPlan).mockReset();
    vi.mocked(TaskService.createPlan).mockResolvedValue({ plan_id: 'plan-1', lane: 'fast' } as any);
});

describe('the walkthrough as one-tap tasks', () => {
    it('renders every Quick Task the pack declares', () => {
        // The presenter runs the whole script without typing, so a task that
        // is not on screen is a beat that has to be typed — and a typo or an
        // autocorrect in a stakeholder meeting is the failure this exists to
        // remove.
        renderInput(walkthrough());

        for (const task of SIX_TASKS) {
            expect(screen.getByText(task.name)).toBeInTheDocument();
        }
    });

    it('lays the tasks out as the grid, not inside one cell of it', () => {
        // The trap: with two tasks a wrapper element between the grid and the
        // cards is invisible, because one column of two reads as a deliberate
        // layout. With six it is a single column that pushes the input box off
        // a phone screen. The grid's children have to be the cards.
        const { container } = renderInput(walkthrough());

        const grid = container.querySelector('.home-input-quick-tasks');
        expect(grid).not.toBeNull();
        expect(grid!.children).toHaveLength(SIX_TASKS.length);
    });

    it('badges each task with the lane it declared', () => {
        renderInput(walkthrough());

        const badges = screen.getAllByTestId('lane-badge');
        expect(badges).toHaveLength(SIX_TASKS.length);
        expect(badges.map((badge) => badge.getAttribute('data-lane'))).toEqual(
            SIX_TASKS.map((task) => task.lane),
        );
        expect(badges.every((badge) => badge.getAttribute('data-lane-variant') === 'declared')).toBe(true);
    });

    it('shows the deliberate task as the one that needs approving', () => {
        // The two-lane contrast, back to back on one screen. If every card
        // looked alike the presenter would have to assert the difference
        // rather than point at it.
        renderInput(walkthrough());

        const deliberate = screen
            .getAllByTestId('lane-badge')
            .filter((badge) => badge.getAttribute('data-lane') === 'deliberate');

        expect(deliberate).toHaveLength(1);
    });

    it('renders no badge for a task whose declaration it cannot read', () => {
        // A surface may say nothing. An unreadable declaration falls open to
        // the Deliberate lane in the backend's router, so a badge guessed here
        // would be the surface claiming a lane nothing chose.
        renderInput(walkthrough([{ ...SIX_TASKS[0], lane: 'fast lane' }]));

        expect(screen.queryByTestId('lane-badge')).not.toBeInTheDocument();
    });
});

describe('tapping a Quick Task', () => {
    const send = (container: HTMLElement) =>
        fireEvent.click(container.querySelector('.home-input-send-button')!);

    it('fills the box with the task prompt', () => {
        renderInput(walkthrough());

        fireEvent.click(screen.getByText('Close the store'));

        expect(screen.getByRole('textbox')).toHaveValue('How do I close the store?');
    });

    it('carries the declared lane into the request', async () => {
        // The declaration is the whole point of the metadata: the presenter's
        // scripted taps are routed by what the pack says, never by the wording
        // of the prompt.
        const { container } = renderInput(walkthrough());

        fireEvent.click(screen.getByText("I can't fix it"));
        send(container);

        await waitFor(() =>
            expect(TaskService.createPlan).toHaveBeenCalledWith(
                'I have tried everything and I need someone to come out.',
                '00000000-0000-0000-0000-000000000223',
                'deliberate',
            ),
        );
    });

    it('gives the declaration up once the presenter edits the prompt', async () => {
        // Edited text is free-typed input and belongs to the backend's keyword
        // fallback. A declaration that survived an edit would outrank the words
        // actually submitted.
        const { container } = renderInput(walkthrough());

        fireEvent.click(screen.getByText("I can't fix it"));
        fireEvent.change(screen.getByRole('textbox'), {
            target: { value: 'I have tried everything and I need someone to come out today.' },
        });
        send(container);

        await waitFor(() =>
            expect(TaskService.createPlan).toHaveBeenCalledWith(
                expect.stringContaining('today'),
                '00000000-0000-0000-0000-000000000223',
                undefined,
            ),
        );
    });
});

describe('six Quick Tasks on a phone-sized screen', () => {
    it('collapses the task grid at the same breakpoint the shell stacks at', () => {
        // 640px, as #25 fixed it. A second breakpoint somewhere else is a
        // surface that reflows twice, and the associate this is for is holding
        // a phone: six four-across cards at 390px are six unreadable slivers.
        const css = readFileSync(STYLESHEET, 'utf8');

        expect(css).toContain('@media (max-width: 640px)');
    });

    it('does not lay a grid out with flexbox rules', () => {
        // The accelerator's responsive rules set `flex-wrap` and `flex` on an
        // element declared `display: grid`, which does nothing at all. A
        // breakpoint that is present, correct and inert is the exact failure
        // #25 found in the shell's inline row.
        const css = readFileSync(STYLESHEET, 'utf8');
        const blocks = css.split('@media').slice(1);

        for (const block of blocks) {
            const scoped = block.slice(0, block.lastIndexOf('}'));
            if (!scoped.includes('.home-input-quick-tasks')) continue;
            expect(scoped).not.toMatch(/flex-wrap|flex:/);
        }
    });
});
