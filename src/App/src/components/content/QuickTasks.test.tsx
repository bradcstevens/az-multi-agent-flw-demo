import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
 * The seven Quick Tasks in the shape the backend sends them (issues #26, #52).
 * lanes and the prompts are the store pack's business — `test_store_pack.py`
 * is what holds those to the corpus and the routers. What is asserted here is
 * that the surface renders every task the home screen offers, badges it with
 * the lane it declared, and carries that declaration into the request.
 */
const SEVEN_TASKS = [
    { id: 'task-223-procedure', name: 'Close the store', prompt: 'How do I close the store?', created: '', creator: '', logo: 'BookMarked', lane: 'fast' },
    { id: 'task-223-honest-miss', name: 'Restart the car wash', prompt: 'How do I restart the car wash?', created: '', creator: '', logo: 'Search', lane: 'fast' },
    { id: 'task-223-troubleshooting', name: 'The coffee brewer is down', prompt: 'The coffee brewer is down.', created: '', creator: '', logo: 'Wrench', lane: 'fast', follow_on: 'task-223-escalation' },
    { id: 'task-223-escalation', name: "I can't fix it", prompt: 'I have tried everything and I need someone to come out.', created: '', creator: '', logo: 'Document', lane: 'deliberate' },
    { id: 'task-223-identity', name: 'How much PTO do I have?', prompt: 'My name is Tanya, how much PTO do I have?', created: '', creator: '', logo: 'Shield', lane: 'fast' },
    { id: 'task-223-shift-tasks', name: 'What is due this shift?', prompt: 'What tasks are due on this shift?', created: '', creator: '', logo: '📋', lane: 'fast' },
    { id: 'task-223-shift-swap', name: 'Swap a shift', prompt: 'How do I swap a shift with another associate?', created: '', creator: '', logo: 'People', lane: 'fast' },
];
const HOME_TASKS = SEVEN_TASKS.filter((task) => task.id !== 'task-223-escalation');

const walkthrough = (tasks: any[] = SEVEN_TASKS) => ({
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
    it('renders every Quick Task the home screen offers', () => {
        // The presenter runs the whole script without typing, so a task that
        // is not on screen is a beat that has to be typed — and a typo or an
        // autocorrect in a stakeholder meeting is the failure this exists to
        // remove.
        renderInput(walkthrough());

        for (const task of HOME_TASKS) {
            expect(screen.getByText(task.name)).toBeInTheDocument();
        }
        expect(screen.queryByText("I can't fix it")).not.toBeInTheDocument();
    });

    it('lays the tasks out as the grid, not inside one cell of it', () => {
        // The trap: with two tasks a wrapper element between the grid and the
        // cards is invisible, because one column of two reads as a deliberate
        // layout. With six it is a single column that pushes the input box off
        // a phone screen. The grid's children have to be the cards.
        const { container } = renderInput(walkthrough());

        const grid = container.querySelector('.home-input-quick-tasks');
        expect(grid).not.toBeNull();
        expect(grid!.children).toHaveLength(HOME_TASKS.length);
    });

    it('badges each task with the lane it declared', () => {
        renderInput(walkthrough());

        const badges = screen.getAllByTestId('lane-badge');
        expect(badges).toHaveLength(HOME_TASKS.length);
        expect(badges.map((badge) => badge.getAttribute('data-lane'))).toEqual(
            HOME_TASKS.map((task) => task.lane),
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

        expect(deliberate).toHaveLength(0);
    });

    it('renders no badge for a task whose declaration it cannot read', () => {
        // A surface may say nothing. An unreadable declaration falls open to
        // the Deliberate lane in the backend's router, so a badge guessed here
        // would be the surface claiming a lane nothing chose.
        renderInput(walkthrough([{ ...SEVEN_TASKS[0], lane: 'fast lane' }]));

        expect(screen.queryByTestId('lane-badge')).not.toBeInTheDocument();
    });

    it('names the region, so a tap can be aimed at the cards alone', () => {
        // The **Demo validator** taps a card by the title the pack authors, and
        // an accessible-name lookup matches by substring: "Close the store" is
        // inside "How do I close the store?", which is what the task rail calls
        // every plan the walkthrough has ever raised. A page-wide tap is
        // therefore unambiguous only on a store nobody has ever asked anything,
        // and the loop rots by being run — which it did, on a strict-mode
        // violation against twenty completed tasks, while the demonstration
        // itself was working.
        //
        // The region is named by its layout class rather than a testid because
        // the validator's target is a *running image*, and this class has been
        // in every one of them since #26. Pinned here so that renaming it is a
        // failing test rather than a red beat on the morning of a walkthrough.
        const { container } = renderInput(walkthrough());

        const region = container.querySelector('.home-input-quick-tasks');
        expect(region).not.toBeNull();
        expect(
            within(region as HTMLElement).getAllByRole('button', {
                name: /Close the store/,
            }),
        ).toHaveLength(1);
    });
});

/**
 * The lane on the card that declares it (issue #16).
 *
 * The badge is the only thing on this grid that distinguishes the two lanes,
 * and the accelerator's sat inline beside the title where it had neither room
 * nor a fixed position: a grid column is ~237px at the surface's 728px, so a
 * two-word pill took most of what the padding left, the title wrapped a word at
 * a time, and the pill — vertically centred against a title of one line or two
 * — landed at a different height on every card. Six badges at six heights
 * cannot be compared at a glance, and comparing them at a glance is the entire
 * reason five cards say one thing and one says another.
 */
describe('where the lane sits on a Quick Task', () => {
    it('gives the badge a row of its own, ahead of the title', () => {
        renderInput(walkthrough());

        const card = screen.getByRole('button', { name: /Close the store/ });
        const badge = within(card).getByTestId('lane-badge');
        const title = within(card).getByText('Close the store');

        // Its own row: the title is not in it, so the two never contend for
        // the same width.
        expect(badge.parentElement!.contains(title)).toBe(false);
        // And it leads, so the lane is the first thing read on every card.
        expect(
            badge.compareDocumentPosition(title) &
                Node.DOCUMENT_POSITION_FOLLOWING,
        ).toBeTruthy();
    });

    it('starts the content of every card at the same corner', () => {
        // jsdom has no layout engine, so the property is asserted where it is
        // decided — and since #66 that is a Griffel class rather than the
        // `style` attribute. It cannot be read back with `getComputedStyle`:
        // Fluent's Button carries a monolithic *reset* class that also declares
        // `align-items`, Griffel's atomic dedup cannot cancel a reset rule, and
        // jsdom resolves the resulting tie by stylesheet order rather than by
        // Griffel's bucket order — so it reports Fluent's value where a real
        // browser renders the card's. What is asserted instead is the
        // declaration the card actually carries.
        //
        // Fluent's Button centres its children on both axes; in a column that
        // is a content block only as wide as its own longest line, floated to
        // the middle of whatever height the grid row stretched the card to.
        // Either one moves the badge, and a badge that moves is a badge nobody
        // can scan down a column.
        renderInput(walkthrough());

        const cards = screen
            .getAllByTestId('lane-badge')
            .map((badge) => badge.closest('button')!);

        expect(cards).toHaveLength(HOME_TASKS.length);
        for (const card of cards) {
            expect(declares(card, 'align-items')).toContain('stretch');
            expect(declares(card, 'justify-content')).toContain('flex-start');
        }
    });
});

describe('tapping a Quick Task', () => {
    it('submits the task prompt and its declared lane in one pointer interaction', async () => {
        renderInput(walkthrough());

        fireEvent.click(screen.getByText('Close the store'));

        await waitFor(() =>
            expect(TaskService.createPlan).toHaveBeenCalledWith(
                'How do I close the store?',
                '00000000-0000-0000-0000-000000000223',
                'fast',
            ),
        );
    });

    it('submits from a semantic button when activated with the keyboard', async () => {
        renderInput(walkthrough());

        const quickTask = screen.getByRole('button', { name: /Close the store/ });
        quickTask.focus();
        await userEvent.keyboard('{Enter}');

        await waitFor(() =>
            expect(TaskService.createPlan).toHaveBeenCalledWith(
                'How do I close the store?',
                '00000000-0000-0000-0000-000000000223',
                'fast',
            ),
        );
    });
});

describe('six Quick Tasks on a phone-sized screen', () => {
    it('shows a focus indicator when a Quick Task is reached by keyboard', () => {
        const css = readFileSync(STYLESHEET, 'utf8');

        expect(css).toContain('.home-input-quick-tasks .fui-Button:focus-visible');
    });

    it('collapses the task grid on a phone-sized screen', () => {
        // At 640px six four-across cards on a phone are six unreadable slivers.
        const css = readFileSync(STYLESHEET, 'utf8');

        expect(css).toContain('@media (max-width: 640px)');
    });

    it('does not lay a grid out with flexbox rules', () => {
        // The accelerator's responsive rules set `flex-wrap` and `flex` on an
        // element declared `display: grid`, which does nothing at all. A
        // breakpoint that is present, correct and inert is the exact failure
        // #25 found in the shell's inline row.
        //
        // The block is read to its **matching** brace, not to the last one in
        // the file: anything declared after the last media query is not inside
        // it, and reading it as though it were makes this test fail on rules it
        // was never about.
        const css = readFileSync(STYLESHEET, 'utf8');

        for (const block of mediaBlocks(css)) {
            if (!block.includes('.home-input-quick-tasks')) continue;
            expect(block).not.toMatch(/flex-wrap|flex:/);
        }
    });
});

/** Each `@media` block's body, read to its matching close brace. */
const mediaBlocks = (css: string): string[] => {
    const blocks: string[] = [];

    for (const match of css.matchAll(/@media[^{]*\{/g)) {
        let depth = 1;
        let index = match.index! + match[0].length;
        const start = index;
        while (index < css.length && depth > 0) {
            if (css[index] === '{') depth += 1;
            if (css[index] === '}') depth -= 1;
            index += 1;
        }
        blocks.push(css.slice(start, index - 1));
    }

    return blocks;
};

/**
 * Every value `element`'s own classes declare for `property`.
 *
 * Griffel writes one atomic rule per declaration, so a class list is a set of
 * declarations and this reads them back. Used where `getComputedStyle` cannot
 * be trusted: Fluent's reset classes declare the same properties, and jsdom
 * breaks the resulting single-class-specificity tie by stylesheet order rather
 * than by the bucket order a browser actually applies.
 */
const declares = (element: Element, property: string): string[] => {
    const selectors = new Set(Array.from(element.classList, (c) => `.${c}`));
    const found: string[] = [];

    for (const sheet of Array.from(document.styleSheets)) {
        let rules: CSSRule[];
        try {
            rules = Array.from(sheet.cssRules);
        } catch {
            continue;
        }
        for (const rule of rules) {
            if (!(rule instanceof CSSStyleRule) || !selectors.has(rule.selectorText)) continue;
            const value = rule.style.getPropertyValue(property);
            if (value) found.push(value.trim());
        }
    }

    return found;
};
