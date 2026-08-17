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

        const toggle = screen.getByRole('button', { name: 'Transparency panels' });
        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        expect(toggle).toHaveAttribute('aria-controls', 'transparency-rail');
        expect(screen.getByRole('heading', { name: 'Agent Team' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Grounding' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'What this cost' })).toBeInTheDocument();

        await userEvent.click(toggle);

        expect(toggle).toHaveAccessibleName('Transparency panels');
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        expect(screen.getByTestId('transparency-rail')).toHaveClass('transparency-rail--collapsed');
        expect(screen.queryByRole('heading', { name: 'Agent Team' })).not.toBeInTheDocument();
        expect(screen.queryByRole('heading', { name: 'Grounding' })).not.toBeInTheDocument();
        expect(screen.queryByRole('heading', { name: 'What this cost' })).not.toBeInTheDocument();
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

        expect(screen.queryByRole('button', { name: 'Transparency panels' })).not.toBeInTheDocument();
        expect(screen.getByTestId('transparency-rail')).not.toHaveClass('transparency-rail--collapsed');
        expect(screen.getByRole('heading', { name: 'Agent Team' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Grounding' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'What this cost' })).toBeInTheDocument();
    });
});
