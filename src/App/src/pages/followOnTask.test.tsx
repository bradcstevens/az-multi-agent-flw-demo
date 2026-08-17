import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

const { getChatTicket } = vi.hoisted(() => ({
    getChatTicket: vi.fn(),
}));

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
        getChatTicket,
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
    },
}));

vi.mock('../components/content/ChatPanelLeft', () => ({
    default: () => null,
}));

vi.mock('../components/content/PlanPanelRight', () => ({
    default: () => null,
}));

import ChatPage from './ChatPage';
import { PlanDataService } from '../store/PlanDataService';
import { TaskService } from '../store/TaskService';
import planReducer from '../store/slices/planSlice';
import chatReducer from '../store/slices/chatSlice';
import appReducer from '../store/slices/appSlice';
import teamReducer from '../store/slices/teamSlice';
import streamingReducer from '../store/slices/streamingSlice';
import transparencyReducer from '../store/slices/transparencySlice';
import ticketReducer, { ticketRaised } from '../store/slices/ticketSlice';
import progressReducer from '@/store/slices/progressSlice';
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
            follow_on: ['task-223-escalation', 'task-223-honest-miss'],
        },
        {
            id: 'task-223-escalation',
            name: "I can't fix it",
            prompt: 'I have tried everything and I need someone to come out.',
            created: '',
            creator: '',
            logo: 'Document',
            lane: 'deliberate',
            ticket_on_approval: true,
            ticket_status_reply: {
                prompt: "What's happening with my ticket?",
                lane: 'fast',
            },
        },
        {
            id: 'task-223-honest-miss',
            name: 'Restart the car wash',
            prompt: 'How do I restart the car wash?',
            created: '',
            creator: '',
            logo: 'Search',
            lane: 'fast',
        },
    ],
} satisfies TeamConfig;

const PLAN_DATA = {
    plan: {
        id: 'plan-troubleshooting',
        data_type: 'plan',
        initial_goal: 'The coffee brewer is down.',
        starting_task_id: 'task-223-troubleshooting',
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
} satisfies ProcessedPlanData;

const ESCALATION_RESPONSE = {
    status: 'accepted',
    session_id: 'session-223-troubleshooting',
    plan_id: 'plan-escalation',
    description: 'I have tried everything and I need someone to come out.',
    lane: 'deliberate',
} satisfies InputTaskResponse;

const TICKET_STATUS_PLAN_DATA = {
    ...PLAN_DATA,
    plan: {
        ...PLAN_DATA.plan,
        id: 'plan-escalation',
        plan_id: 'plan-escalation',
        initial_goal: ESCALATION_RESPONSE.description,
    },
} satisfies ProcessedPlanData;

const REOPENED_TICKET_STATUS_PLAN_DATA = {
    ...TICKET_STATUS_PLAN_DATA,
    plan: {
        ...TICKET_STATUS_PLAN_DATA.plan,
        id: 'plan-ticket-status',
        plan_id: 'plan-ticket-status',
        initial_goal: TICKET_STATUS_PLAN_DATA.team.starting_tasks[1].ticket_status_reply!.prompt,
    },
} satisfies ProcessedPlanData;

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
            progress: progressReducer,
        },
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware({ serializableCheck: false }),
    });
    return store;
};

const renderPlan = (planData: ProcessedPlanData = PLAN_DATA) => {
    const store = makeStore();
    vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(planData);
    const result = render(
        <Provider store={store}>
            <MemoryRouter initialEntries={['/chat/plan-troubleshooting']}>
                <Routes>
                    <Route path="/chat/:id" element={<ChatPage />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );
    return { store, ...result };
};

describe('the troubleshooting follow-on task', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
        vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(PLAN_DATA);
        vi.mocked(TaskService.createPlan).mockReset().mockResolvedValue(ESCALATION_RESPONSE);
        getChatTicket.mockReset().mockResolvedValue(null);
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
                'task-223-escalation',
            ),
        );
    });

    it('offers no Follow-on task for free-typed words matching an authored prompt', async () => {
        renderPlan({
            ...PLAN_DATA,
            plan: {
                ...PLAN_DATA.plan,
                starting_task_id: undefined,
            },
        } as ProcessedPlanData);

        expect(
            await screen.findByRole('textbox'),
        ).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: "I can't fix it" })).not.toBeInTheDocument();
    });

    it('continues the viewed session on the declared lane of each offered Quick Task', async () => {
        renderPlan();

        fireEvent.click(await screen.findByRole('button', { name: 'Restart the car wash' }));

        await waitFor(() =>
            expect(TaskService.createPlan).toHaveBeenCalledWith(
                'How do I restart the car wash?',
                'team-223',
                'fast',
                'session-223-troubleshooting',
                'task-223-honest-miss',
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

    it('does not let the box start a second turn while the card is creating one', async () => {
        /*
          Two continuation paths into one **Session**, and they must share one
          lock (#77). `process_request` cancels whatever orchestration that user
          already had running before it schedules the next, so a turn typed
          while the card's is in flight does not join it — it replaces it, and
          the escalation the presenter just tapped never arrives.
        */
        let resolveCreatePlan: () => void;
        vi.mocked(TaskService.createPlan).mockImplementation(
            () => new Promise((resolve) => {
                resolveCreatePlan = () => resolve(ESCALATION_RESPONSE);
            }),
        );
        renderPlan();

        fireEvent.click(await screen.findByRole('button', { name: "I can't fix it" }));

        const box = await screen.findByRole('textbox');
        fireEvent.change(box, { target: { value: 'Where is the filter stored?' } });
        fireEvent.keyDown(box, { key: 'Enter' });

        expect(TaskService.createPlan).toHaveBeenCalledTimes(1);
        resolveCreatePlan!();
    });

    it('continues the ticket Chat on the declared Fast lane when its status reply is tapped', async () => {
        const { store } = renderPlan(TICKET_STATUS_PLAN_DATA);
        await screen.findByRole('textbox');
        store.dispatch(
            ticketRaised({
                ticket_id: 'SIM-223-0001',
                status: 'submitted',
                fields: [{ name: 'status', value: 'submitted' }],
            }),
        );

        fireEvent.click(
            await screen.findByRole('button', { name: "What's happening with my ticket?" }),
        );

        await waitFor(() =>
            expect(TaskService.createPlan).toHaveBeenCalledWith(
                "What's happening with my ticket?",
                'team-223',
                'fast',
                'session-223-troubleshooting',
                undefined,
            ),
        );
    });

    it('restores the ticket-status reply when the raised-ticket Chat is reopened', async () => {
        getChatTicket.mockResolvedValue({
            ticket_id: 'SIM-223-0001',
            status: 'submitted',
            fields: [{ name: 'status', value: 'submitted' }],
        });
        renderPlan(REOPENED_TICKET_STATUS_PLAN_DATA);

        expect(
            await screen.findByRole('button', { name: "What's happening with my ticket?" }),
        ).toBeInTheDocument();
    });
});
