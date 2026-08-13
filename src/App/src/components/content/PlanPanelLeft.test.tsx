import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

vi.mock('@/api', () => ({
    apiService: { getPlans: vi.fn().mockResolvedValue([]) },
}));

import PlanPanelLeft from './PlanPanelLeft';
import appReducer from '../../store/slices/appSlice';
import { ASSISTANT_NAME } from '../../models/storeSurface';

const renderPanel = (props: Record<string, unknown> = {}) =>
    render(
        <Provider store={configureStore({ reducer: { app: appReducer } })}>
            <MemoryRouter>
                <PlanPanelLeft
                    reloadTasks={false}
                    onNewTaskButton={() => undefined}
                    {...props}
                />
            </MemoryRouter>
        </Provider>,
    );

describe('the store surface has one assistant', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('is branded as the store assistant, not as the accelerator', async () => {
        renderPanel();

        expect(await screen.findByText(ASSISTANT_NAME)).toBeInTheDocument();
        expect(screen.queryByText(/contoso/i)).not.toBeInTheDocument();
    });

    it('offers no team picker, because the associate has no basis for the choice', async () => {
        // Routing between specialists is the orchestrator's job and the lane
        // router's job. Asking an associate mid-shift to pick a team makes a
        // decision they cannot make into a precondition of getting an answer.
        renderPanel();

        await waitFor(() => {
            expect(screen.queryByText(/current team/i)).not.toBeInTheDocument();
        });
        expect(screen.queryByRole('button', { name: /team/i })).not.toBeInTheDocument();
        expect(screen.queryByText(/select a team/i)).not.toBeInTheDocument();
    });

    it('offers no team upload either — a picker with one entry is still a picker', async () => {
        renderPanel();

        await screen.findByText(ASSISTANT_NAME);
        expect(screen.queryByText(/upload/i)).not.toBeInTheDocument();
    });
});
