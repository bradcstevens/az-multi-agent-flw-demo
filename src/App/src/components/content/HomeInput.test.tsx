import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

vi.mock('../../store/TaskService', () => ({
    TaskService: { createPlan: vi.fn() },
}));

import HomeInput from './HomeInput';
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

describe('the home surface', () => {
    it('never asks the associate to pick a team', () => {
        // The accelerator's empty state told the user to "select a team",
        // which is a routing decision presented as a precondition. With one
        // assistant there is nothing to select, so there is nothing to say.
        renderInput(null);

        expect(screen.queryByText(/select a team/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/for this team/i)).not.toBeInTheDocument();
    });

    it('says the assistant is not loaded rather than blaming the associate', () => {
        renderInput(null);

        expect(screen.getByTestId('assistant-unavailable')).toHaveTextContent(ASSISTANT_NAME);
    });

    it('says nothing about availability once the assistant is loaded', () => {
        renderInput({ team_id: 'x', name: ASSISTANT_NAME, agents: [], starting_tasks: [] });

        expect(screen.queryByTestId('assistant-unavailable')).not.toBeInTheDocument();
    });
});
