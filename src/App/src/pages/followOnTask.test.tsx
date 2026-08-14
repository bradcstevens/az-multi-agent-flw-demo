import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
        approvePlan: vi.fn(),
        getSessionState: vi.fn(async () => ({})),
    };
    return { apiService, APIService: vi.fn(() => apiService) };
});

vi.mock('../store/PlanDataService', () => ({
    PlanDataService: { fetchPlanData: vi.fn(), submitClarification: vi.fn() },
}));

vi.mock('../store/TaskService', () => ({
    TaskService: {
        createPlan: vi.fn(),
        transformPlansToTasks: vi.fn(() => ({ inProgress: [], completed: [] })),
    },
}));

vi.mock('../components/content/PlanPanelLeft', () => ({
    default: () => null,
}));

vi.mock('../components/content/PlanPanelRight', () => ({
    default: () => null,
}));

import PlanPage from './PlanPage';
import { PlanDataService } from '../store/PlanDataService';
import { TaskService } from '../store/TaskService';
import planReducer from '../store/slices/planSlice';
import chatReducer from '../store/slices/chatSlice';
import appReducer from '../store/slices/appSlice';
import teamReducer from '../store/slices/teamSlice';
import streamingReducer from '../store/slices/streamingSlice';
import transparencyReducer from '../store/slices/transparencySlice';
import ticketReducer from '../store/slices/ticketSlice';
import { FakeSocket } from '@/testing/fakeSocket';
import {
    InputTaskResponse,
    PlanStatus,
    ProcessedPlanData,
    TeamConfig,
} from '../models';

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
    starting_tasks: [
        {
            id: 'task-223-troubleshooting',
            name: 'The coffee brewer is down',
            prompt: 'The coffee brewer is down.',
            created: '',
            creator: '',
            logo: 'Wrench',
            lane: 'fast',
            follow_on: 'task-223-escalation',
        },
        {
            id: 'task-223-escalation',
            name: "I can't fix it",
            prompt: 'I have tried everything and I need someone to come out.',
            created: '',
            creator: '',
            logo: 'Document',
            lane: 'deliberate',
        },
    ],
} satisfies TeamConfig;

const PLAN_DATA = {
    plan: {
        id: 'plan-troubleshooting',
        data_type: 'plan',
        initial_goal: 'The coffee brewer is down.',
        session_id: 'session-223-troubleshooting',
        timestamp: '',
        plan_id: 'plan-troubleshooting',
        user_id: 'user-223',
        overall_status: PlanStatus.COMPLETED,
    },
    team: TEAM,
    messages: [],
    mplan: null,
    streaming_message: null,
    agents: [],
    steps: [],
} satisfies ProcessedPlanData;

const ESCALATION_RESPONSE = {
    status: 'accepted',
    session_id: 'session-223-troubleshooting',
    plan_id: 'plan-escalation',
    description: 'I have tried everything and I need someone to come out.',
    lane: 'deliberate',
} satisfies InputTaskResponse;

const makeStore = () => {
    const store = configureStore({
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
    return store;
};

const renderPlan = () =>
    render(
        <Provider store={makeStore()}>
            <MemoryRouter initialEntries={['/plan/plan-troubleshooting']}>
                <Routes>
                    <Route path="/plan/:planId" element={<PlanPage />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );

describe('the troubleshooting follow-on task', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
        vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(PLAN_DATA);
        vi.mocked(TaskService.createPlan).mockReset().mockResolvedValue(ESCALATION_RESPONSE);
    });

    it('continues the viewed troubleshooting session with the authored escalation', async () => {
        renderPlan();

        fireEvent.click(await screen.findByRole('button', { name: "I can't fix it" }));

        await waitFor(() =>
            expect(TaskService.createPlan).toHaveBeenCalledWith(
                'I have tried everything and I need someone to come out.',
                'team-223',
                'deliberate',
                'session-223-troubleshooting',
            ),
        );
    });

    it('submits the follow-on only once while it is being created', async () => {
        let resolveCreatePlan: () => void;
        vi.mocked(TaskService.createPlan).mockImplementation(
            () => new Promise((resolve) => {
                resolveCreatePlan = () => resolve(ESCALATION_RESPONSE);
            }),
        );
        renderPlan();

        const followOn = await screen.findByRole('button', { name: "I can't fix it" });
        fireEvent.click(followOn);
        fireEvent.click(followOn);

        expect(TaskService.createPlan).toHaveBeenCalledTimes(1);
        resolveCreatePlan!();
    });
});
