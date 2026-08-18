import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
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
    const apiService = {
        getPlans: vi.fn(async () => []),
        approvePlan: vi.fn(async () => ({})),
        getSessionState: vi.fn(async () => ({})),
        getChatTicket: vi.fn(async () => null),
    };
    return { apiService, APIService: vi.fn(() => apiService) };
});

vi.mock('../store/PlanDataService', () => ({
    PlanDataService: { fetchPlanData: vi.fn(), submitClarification: vi.fn() },
}));

vi.mock('../store/TaskService', () => ({
    TaskService: {
        createPlan: vi.fn(),
        transformPlansToChats: vi.fn(() => []),
        cleanTextToSpaces: vi.fn((value: string) => value.replace(/_/g, ' ')),
    },
}));

vi.mock('../components/content/ChatPanelLeft', () => ({ default: () => null }));
vi.mock('../components/content/PlanPanelRight', () => ({ default: () => null }));

import ChatPage from './ChatPage';
import { apiService } from '@/api/apiService';
import { PlanDataService } from '../store/PlanDataService';
import planReducer, { approvalRequestReceived } from '../store/slices/planSlice';
import chatReducer from '../store/slices/chatSlice';
import appReducer from '../store/slices/appSlice';
import teamReducer from '../store/slices/teamSlice';
import streamingReducer from '../store/slices/streamingSlice';
import transparencyReducer from '../store/slices/transparencySlice';
import ticketReducer from '../store/slices/ticketSlice';
import progressReducer from '@/store/slices/progressSlice';
import { FakeSocket } from '@/testing/fakeSocket';
import { MPlanData, PlanStatus, ProcessedPlanData, TeamConfig } from '../models';

const TEAM = {
    id: 'team-config-223',
    team_id: 'team-223',
    name: 'Store Assistant',
    description: '',
    status: 'visible',
    created: '',
    created_by: '',
    logo: '',
    plan: '',
    agents: [],
    starting_tasks: [],
} satisfies TeamConfig;

const PLAN_DATA = {
    plan: {
        id: 'plan-shift-swap',
        data_type: 'plan',
        initial_goal: 'I need Saturday off.',
        session_id: 'session-223-shift-swap',
        timestamp: '',
        plan_id: 'plan-shift-swap',
        user_id: 'user-223',
        overall_status: PlanStatus.IN_PROGRESS,
    },
    team: TEAM,
    messages: [],
    mplan: null,
    streaming_message: null,
} satisfies ProcessedPlanData;

const REVIEWABLE_PLAN = {
    id: 'mplan-shift-swap',
    status: 'awaiting_approval',
    user_request: 'I need Saturday off.',
    team: ['Rota_Agent'],
    facts: '',
    steps: [
        {
            id: 1,
            action: 'Ask Marcus Bell to take the Saturday shift',
            assignee: {
                kind: 'person' as const,
                name: 'Marcus Bell',
                relation: 'peer' as const,
                simulated: true,
            },
        },
        { id: 2, action: 'Update the rota', agent: 'Rota_Agent', waitsOn: 1 },
    ],
    context: { task: 'I need Saturday off.', participant_descriptions: {} },
} satisfies MPlanData;

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
            progress: progressReducer,
        },
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware({ serializableCheck: false }),
    });

const renderPlanUnderReview = async () => {
    const store = makeStore();
    vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(PLAN_DATA);
    const result = render(
        <Provider store={store}>
            <MemoryRouter initialEntries={['/chat/plan-shift-swap']}>
                <Routes>
                    <Route path="/chat/:id" element={<ChatPage />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );
    await waitFor(() => expect(PlanDataService.fetchPlanData).toHaveBeenCalled());
    act(() => {
        store.dispatch(approvalRequestReceived(REVIEWABLE_PLAN));
    });
    await screen.findByRole('button', { name: 'Approve Task Plan' });
    return { store, ...result };
};

/**
 * The wire seam for a **Verdict** on a **Reviewable plan** (#108).
 *
 * The pure model in `models/reviewablePlan.ts` says what a verdict *means*;
 * this says what actually leaves the surface when the associate gives one,
 * asserted against the real `ChatPage` rather than a hand-built payload.
 */
describe('the verdict on a Reviewable plan', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
        vi.mocked(apiService.approvePlan).mockReset().mockResolvedValue({} as never);
    });

    it('approves the plan the associate is looking at', async () => {
        await renderPlanUnderReview();

        fireEvent.click(screen.getByRole('button', { name: 'Approve Task Plan' }));

        await waitFor(() =>
            expect(apiService.approvePlan).toHaveBeenCalledWith({
                m_plan_id: 'mplan-shift-swap',
                plan_id: 'plan-shift-swap',
                approved: true,
                feedback: 'Plan approved by user',
            }),
        );
    });

    it('leaves approval available to retry when its request fails', async () => {
        vi.mocked(apiService.approvePlan)
            .mockRejectedValueOnce(new Error('offline'))
            .mockResolvedValueOnce({} as never);
        await renderPlanUnderReview();

        fireEvent.click(screen.getByRole('button', { name: 'Approve Task Plan' }));
        await waitFor(() => expect(apiService.approvePlan).toHaveBeenCalledTimes(1));

        fireEvent.click(screen.getByRole('button', { name: 'Approve Task Plan' }));
        await waitFor(() => expect(apiService.approvePlan).toHaveBeenCalledTimes(2));
    });

    it('sends the plan back carrying what the associate would change', async () => {
        await renderPlanUnderReview();

        fireEvent.change(screen.getByLabelText('What would you change?'), {
            target: { value: 'Ask Priya, Marcus is on holiday.' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Send back with changes' }));

        await waitFor(() =>
            expect(apiService.approvePlan).toHaveBeenCalledWith({
                m_plan_id: 'mplan-shift-swap',
                plan_id: 'plan-shift-swap',
                approved: false,
                feedback: 'Ask Priya, Marcus is on holiday.',
            }),
        );
    });

    it('leaves send-back available to retry when its request fails', async () => {
        vi.mocked(apiService.approvePlan)
            .mockRejectedValueOnce(new Error('offline'))
            .mockResolvedValueOnce({} as never);
        await renderPlanUnderReview();

        fireEvent.change(screen.getByLabelText('What would you change?'), {
            target: { value: 'Ask Priya, Marcus is on holiday.' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Send back with changes' }));
        await waitFor(() => expect(apiService.approvePlan).toHaveBeenCalledTimes(1));

        fireEvent.click(screen.getByRole('button', { name: 'Send back with changes' }));
        await waitFor(() => expect(apiService.approvePlan).toHaveBeenCalledTimes(2));
    });

    it('stays in the conversation when the plan is sent back', async () => {
        // The revised plan comes back here. Returning to the home screen is
        // what the destroyed-plan path used to do, and it is what made a
        // disagreement the end of the conversation.
        await renderPlanUnderReview();

        fireEvent.change(screen.getByLabelText('What would you change?'), {
            target: { value: 'Ask Priya, Marcus is on holiday.' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Send back with changes' }));

        await waitFor(() => expect(apiService.approvePlan).toHaveBeenCalled());
        expect(screen.queryByRole('heading', { name: /how can i help/i })).not.toBeInTheDocument();
        expect(screen.getByText('I need Saturday off.')).toBeInTheDocument();
    });

    it('offers the starters derived from the plan on screen', async () => {
        await renderPlanUnderReview();

        fireEvent.click(
            screen.getByRole('button', { name: 'Ask somebody other than Marcus Bell.' }),
        );
        fireEvent.click(screen.getByRole('button', { name: 'Send back with changes' }));

        await waitFor(() =>
            expect(apiService.approvePlan).toHaveBeenCalledWith(
                expect.objectContaining({
                    approved: false,
                    feedback: 'Ask somebody other than Marcus Bell.',
                }),
            ),
        );
    });

    it('says nothing more once the plan is approved', async () => {
        // Approving is terminal. A second verdict on an approved plan reaches
        // the endpoint exactly once, however many times the control is pressed.
        const { store } = await renderPlanUnderReview();

        const approve = screen.getByRole('button', { name: 'Approve Task Plan' });
        fireEvent.click(approve);
        await waitFor(() => expect(apiService.approvePlan).toHaveBeenCalledTimes(1));

        act(() => {
            store.dispatch(approvalRequestReceived(REVIEWABLE_PLAN));
        });
        fireEvent.click(await screen.findByRole('button', { name: 'Approve Task Plan' }));

        await waitFor(() => expect(apiService.approvePlan).toHaveBeenCalledTimes(1));
    });
});
