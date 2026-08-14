import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

vi.mock('../store/TeamService', () => ({
    TeamService: {
        getUserTeams: vi.fn(),
        initializeTeam: vi.fn(),
        storageTeam: vi.fn(),
        clearStoredTeam: vi.fn(),
        getStoredTeam: vi.fn(() => null),
    },
}));

vi.mock('@/api/apiService', () => {
    const apiService = { getPlans: vi.fn(async () => []), approvePlan: vi.fn() };
    return { apiService, APIService: vi.fn(() => apiService) };
});

vi.mock('../store/PlanDataService', () => ({
    PlanDataService: { fetchPlanData: vi.fn() },
}));

import PlanPage from './PlanPage';
import { PlanDataService } from '../store/PlanDataService';
import { NO_ROSTER_MESSAGE } from '@/models/agentAvailability';
import { FakeSocket } from '@/testing/fakeSocket';

import planReducer from '@/store/slices/planSlice';
import chatReducer from '@/store/slices/chatSlice';
import appReducer from '@/store/slices/appSlice';
import teamReducer, { setSelectedTeam } from '@/store/slices/teamSlice';
import streamingReducer from '@/store/slices/streamingSlice';
import transparencyReducer from '@/store/slices/transparencySlice';
import ticketReducer from '@/store/slices/ticketSlice';

/**
 * The loading window, read off the **plan surface** rather than off the panel
 * (issue #65).
 *
 * `PlanPanelRight.test.tsx` proves the Agent Team panel names the roster when
 * it is handed `planData={null} loading`. That is the panel's half. This is the
 * other half, and it is the half the audience actually sees: the panel only
 * reaches the loading window because `PlanPage` renders it **outside** the
 * `loading || !planData` branch. Move it inside — the shape a reader would
 * assume from the rest of that render — and every panel-level assertion here
 * stays green while the window goes back to a spinner with nothing beside it.
 *
 * So the wait is rendered for real: the plan fetch is left in flight, which is
 * `planSlice`'s initial `loading: true`, and nothing but `selectedTeam` is put
 * in the store. No frame arrives on the socket during any of it.
 */

const STORE_ASSISTANT = {
    agents: [
        { input_key: '', type: '', name: 'TroubleshootingAgent', deployment_name: 'o4-mini' },
        { input_key: '', type: '', name: 'ShiftTasksAgent', deployment_name: 'gpt-4.1-mini' },
        { input_key: '', type: '', name: 'EscalationAgent' },
    ],
} as any;

const makeStore = () =>
    configureStore({
        reducer: {
            plan: planReducer,
            chat: chatReducer,
            app: appReducer,
            team: teamReducer,
            streaming: streamingReducer,
            transparency: transparencyReducer,
            ticket: ticketReducer,
        },
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware({ serializableCheck: false }),
    });

/** The plan surface with the fetch still in flight — the loading window. */
const renderLoadingWindow = (store = makeStore()) =>
    render(
        <Provider store={store}>
            <MemoryRouter initialEntries={['/plan/plan-1']}>
                <Routes>
                    <Route path="/plan/:planId" element={<PlanPage />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );

const holdingTheRoster = () => {
    const store = makeStore();
    store.dispatch(setSelectedTeam(STORE_ASSISTANT));
    return store;
};

beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
    window.appConfig = { API_URL: 'https://backend.example/api' } as never;
    // Never resolves: the window under test is the one before it does.
    vi.mocked(PlanDataService.fetchPlanData).mockReturnValue(new Promise(() => {}) as never);
});

describe('the plan surface while it is loading', () => {
    it('is in the loading window, not in a rendered conversation', async () => {
        // Guards every assertion below from passing against the loaded
        // surface. The spinner is the `loading || !planData` branch itself —
        // the rail beside it renders either way, which is the whole reason
        // this ticket exists.
        const { container } = renderLoadingWindow(holdingTheRoster());

        await waitFor(() =>
            expect(screen.getByText(/Loading plan data/i)).toBeInTheDocument(),
        );
        expect(container.querySelector('.plan-loading-spinner')).not.toBeNull();
    });

    it('names the specialists that are available while the presenter waits', async () => {
        renderLoadingWindow(holdingTheRoster());

        await waitFor(() =>
            expect(
                screen.getByTestId('agent-team-member-TroubleshootingAgent'),
            ).toBeInTheDocument(),
        );
        expect(screen.getByTestId('agent-team-member-ShiftTasksAgent')).toBeInTheDocument();
        expect(screen.getByTestId('agent-team-member-EscalationAgent')).toBeInTheDocument();
    });

    it('counts them in a heading over the names', async () => {
        renderLoadingWindow(holdingTheRoster());

        await waitFor(() =>
            expect(screen.getByTestId('agent-team-availability')).toHaveTextContent(
                '3 specialists available',
            ),
        );
        // A heading, not a styled span: the rail is skimmed by heading
        // navigation, and #57 is the ticket that made that true of every other
        // title on it.
        expect(screen.getByRole('heading', { name: /3 specialists available/i })).toBeInTheDocument();
    });

    it('no longer denies the roster it is holding two inches from the spinner', async () => {
        renderLoadingWindow(holdingTheRoster());

        await waitFor(() =>
            expect(screen.getByTestId('agent-team-panel')).toBeInTheDocument(),
        );
        expect(screen.queryByText(NO_ROSTER_MESSAGE)).not.toBeInTheDocument();
    });

    it('still says there is no roster when the app is holding none', async () => {
        // A deployment with no store assistant is a real state, and the panel
        // is right to say so. It may only not say it about a team the app has.
        renderLoadingWindow();

        await waitFor(() =>
            expect(screen.getByTestId('agent-team-empty')).toHaveTextContent(NO_ROSTER_MESSAGE),
        );
    });

    it('claims none of them took the question', async () => {
        // Nothing has been asked of anybody yet — the fetch has not returned.
        // On the boundary-probe beat the answer stays zero after it does: the
        // Identity boundary gate refuses above the Lane router, which is why
        // the Token meter renders a measured `0` on that row.
        renderLoadingWindow(holdingTheRoster());

        await waitFor(() =>
            expect(screen.getByTestId('agent-team-note')).toBeInTheDocument(),
        );
        expect(
            screen.queryByText(/identified|assigned|selected|chosen|working on/i),
        ).not.toBeInTheDocument();
    });
});
