import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

import AgentTeamPanel from './AgentTeamPanel';
import TransparencyRail from './TransparencyRail';
import TransparencyRailToggle from './TransparencyRailToggle';
import transparencyReducer, { transparencyRailToggled } from '@/store/slices/transparencySlice';
import {
    TRANSPARENCY_PANELS_LABEL,
    TRANSPARENCY_RAIL_PINNED_CLOSED_DESCRIPTION,
} from '@/models/storeSurface';
import {
    TRANSPARENCY_RAIL_COLLAPSED_CLASS,
    TRANSPARENCY_RAIL_ID,
} from '@/models/panelDrawer';

/**
 * The **Transparency rail** as a **Panel drawer** (issue #127, ADR-035).
 *
 * The rail is read *beside* the answer it explains, so its drawer **pushes**:
 * closing it hands the width back to the conversation. Which means collapsed
 * has to be zero width *and* the panels gone — a heading a non-visual user
 * skims to and finds nothing behind is #78's defect one step further on.
 */

const TEAM = {
    agents: [{ input_key: '', type: '', name: 'ShiftTasksAgent', deployment_name: 'gpt-4.1-mini' }],
} as any;

const makeStore = () => configureStore({ reducer: { transparency: transparencyReducer } });

const renderDisclosure = (store = makeStore()) =>
    render(
        <Provider store={store}>
            <TransparencyRailToggle />
            <TransparencyRail team={TEAM}>
                <AgentTeamPanel available={TEAM} availableCount={1} />
            </TransparencyRail>
        </Provider>,
    );

describe('the transparency rail disclosure', () => {
    afterEach(() => vi.unstubAllGlobals());

    it('keeps one accessible name while closing the rail and unmounting its headings', async () => {
        renderDisclosure();

        const toggle = screen.getByRole('button', { name: TRANSPARENCY_PANELS_LABEL });
        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        expect(toggle).toHaveAttribute('aria-controls', TRANSPARENCY_RAIL_ID);
        expect(screen.getByRole('heading', { name: 'Agent Team' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Grounding' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'What this cost' })).toBeInTheDocument();

        await userEvent.click(toggle);

        expect(toggle).toHaveAccessibleName(TRANSPARENCY_PANELS_LABEL);
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        expect(screen.getByTestId('transparency-rail')).toHaveClass(
            TRANSPARENCY_RAIL_COLLAPSED_CLASS,
        );
        expect(screen.queryByRole('heading', { name: 'Agent Team' })).not.toBeInTheDocument();
        expect(screen.queryByRole('heading', { name: 'Grounding' })).not.toBeInTheDocument();
        expect(screen.queryByRole('heading', { name: 'What this cost' })).not.toBeInTheDocument();
        expect(toggle).toHaveAttribute(
            'aria-description',
            TRANSPARENCY_RAIL_PINNED_CLOSED_DESCRIPTION,
        );
    });

    it('reopens the rail, and gives the conversation its width back in between', async () => {
        renderDisclosure();

        const toggle = screen.getByRole('button', { name: TRANSPARENCY_PANELS_LABEL });
        await userEvent.click(toggle);
        await userEvent.click(toggle);

        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByTestId('transparency-rail')).not.toHaveClass(
            TRANSPARENCY_RAIL_COLLAPSED_CLASS,
        );
        expect(screen.getByRole('heading', { name: 'Grounding' })).toBeInTheDocument();
    });

    it('only describes the rail as pinned while the presenter has left it closed', async () => {
        renderDisclosure();

        const toggle = screen.getByRole('button', { name: TRANSPARENCY_PANELS_LABEL });
        await userEvent.click(toggle);
        expect(toggle).toHaveAttribute(
            'aria-description',
            TRANSPARENCY_RAIL_PINNED_CLOSED_DESCRIPTION,
        );

        await userEvent.click(toggle);
        expect(toggle).not.toHaveAttribute('aria-description');
    });

    it('says which way it will go in its glyph rather than in its name', async () => {
        // The name is a constant, so on a projector the only thing left to
        // report the state is the icon — and a control offering to *contract* a
        // rail that is already closed is the surface arguing with itself in
        // front of the room. `aria-expanded` says it to everyone else.
        renderDisclosure();

        const toggle = screen.getByRole('button', { name: TRANSPARENCY_PANELS_LABEL });
        const glyph = () => toggle.querySelector('svg path')?.getAttribute('d');
        const open = glyph();
        expect(open, 'the control has no glyph at all').toBeTruthy();

        await userEvent.click(toggle);

        expect(glyph(), 'the same glyph offers to open and to close').not.toBe(open);
    });

    it('keeps the rail expanded and removes its control below the stacking breakpoint', () => {
        vi.stubGlobal('matchMedia', () => ({
            matches: false,
            addEventListener: () => undefined,
            removeEventListener: () => undefined,
        }));
        const store = makeStore();
        store.dispatch(transparencyRailToggled());

        renderDisclosure(store);

        expect(
            screen.queryByRole('button', { name: TRANSPARENCY_PANELS_LABEL }),
        ).not.toBeInTheDocument();
        expect(screen.getByTestId('transparency-rail')).not.toHaveClass(
            TRANSPARENCY_RAIL_COLLAPSED_CLASS,
        );
        expect(screen.getByRole('heading', { name: 'Agent Team' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Grounding' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'What this cost' })).toBeInTheDocument();
    });
});
