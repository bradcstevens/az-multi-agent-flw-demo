import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { Provider, useStore } from 'react-redux';
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

const { getPlanById } = vi.hoisted(() => ({ getPlanById: vi.fn() }));

vi.mock('@/api/apiService', () => {
    const apiService = {
        getPlans: vi.fn(async () => []),
        approvePlan: vi.fn(),
        getSessionState: vi.fn(async () => ({})),
        getChatTicket: vi.fn(async () => null),
        sendAgentMessage: vi.fn(async () => ({})),
        getPlanById,
    };
    return { apiService, APIService: vi.fn(() => apiService) };
});

/*
  Only what leaves the browser is stubbed, and it is stubbed at the browser's
  own edge — `getPlanById`, so the plan payload reaches the conversation
  through the *real* `processPlanData`. A suite that hands the surface an
  already-processed plan asserts a team object the surface never builds, and
  `convertTeamConfiguration` dropping `rehearsed_replies` is exactly the shape
  that hides in (#47): the card would yield its slot to chips the conversion
  had thrown away. The clarification parser stays real for the same reason —
  whether the agent is waiting on an answer is its verdict.
*/
vi.mock('../store/PlanDataService', async (importOriginal) => {
    const actual = await importOriginal<typeof import('../store/PlanDataService')>();
    class StubbedPlanDataService extends actual.PlanDataService {
        static submitClarification = vi.fn();
    }
    return { PlanDataService: StubbedPlanDataService };
});

vi.mock('../store/TaskService', async (importOriginal) => {
    const actual = await importOriginal<typeof import('../store/TaskService')>();
    class StubbedTaskService extends actual.TaskService {
        static createPlan = vi.fn();
        static transformPlansToChats = vi.fn(() => []);
    }
    return { TaskService: StubbedTaskService, default: StubbedTaskService };
});

vi.mock('../components/content/ChatPanelLeft', () => ({ default: () => null }));
vi.mock('../components/content/PlanPanelRight', () => ({ default: () => null }));

import ChatPage from './ChatPage';
import { PlanDataService } from '../store/PlanDataService';
import { TaskService } from '../store/TaskService';
import planReducer from '../store/slices/planSlice';
import chatReducer from '../store/slices/chatSlice';
import appReducer from '../store/slices/appSlice';
import teamReducer from '../store/slices/teamSlice';
import streamingReducer from '../store/slices/streamingSlice';
import transparencyReducer from '../store/slices/transparencySlice';
import ticketReducer from '../store/slices/ticketSlice';
import progressReducer from '@/store/slices/progressSlice';
import { FakeSocket, frame } from '@/testing/fakeSocket';
import type { RootState } from '../store/store';
import { InputTaskResponse, PlanStatus } from '../models';

/**
 * One control at a time (#131, ADR-033 decision 6).
 *
 * `task-223-troubleshooting` is the single **Quick Task** carrying both a
 * **Follow-on task** and **Rehearsed reply** chips, so the walkthrough's beats
 * 3 and 4 are where the two controls are live together. The card yields the
 * slot while the orchestration waits on a **Clarification**, the chips take it,
 * the tap answers, the chips go and the card returns — a tap on the card in
 * that moment starts a new turn and *strands the turn that asked*.
 *
 * Driven from the wire at both ends — the plan payload as the backend returns
 * it, and a `user_clarification_request` frame through `FakeSocket` into the
 * real conversation. Whether the agent is waiting on an answer is a claim about
 * what the backend asked, and which controls this Chat was authored is a claim
 * about the team it came back with; a suite that arranges either one in the
 * store can only agree with itself (#47).
 */

const REHEARSED_REPLY = 'I switched it off at the wall and back on again.';
const ESCALATION = "I can't fix it";

/** The team exactly as the plan payload carries it, before any conversion. */
const TEAM = {
    id: 'team-config-223',
    team_id: 'team-223',
    name: 'Store Assistant',
    description: '',
    status: 'visible',
    created: '',
    created_by: '',
    user_id: 'user-223',
    data_type: 'team_config',
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
            follow_on: ['task-223-escalation'],
            rehearsed_replies: [REHEARSED_REPLY],
        },
        {
            id: 'task-223-escalation',
            name: ESCALATION,
            prompt: 'I have tried everything and I need someone to come out.',
            created: '',
            creator: '',
            logo: 'Document',
            lane: 'deliberate',
        },
    ],
};

const PLAN_PAYLOAD = {
    plan: {
        id: 'plan-troubleshooting',
        data_type: 'plan',
        initial_goal: 'The coffee brewer is down.',
        starting_task_id: 'task-223-troubleshooting',
        session_id: 'session-223-troubleshooting',
        timestamp: '',
        plan_id: 'plan-troubleshooting',
        user_id: 'user-223',
        overall_status: PlanStatus.IN_PROGRESS,
    },
    team: TEAM,
    messages: [],
    m_plan: null,
    streaming_message: null,
};

const ESCALATION_RESPONSE = {
    status: 'accepted',
    session_id: 'session-223-troubleshooting',
    plan_id: 'plan-escalation',
    description: 'I have tried everything and I need someone to come out.',
    lane: 'deliberate',
} satisfies InputTaskResponse;

/**
 * What the narration already knew at each navigation.
 *
 * The seam records the routed plan **before** it navigates, and `planOpened`
 * resets a narration about any other plan — so a turn routed after the
 * navigation is a surface that falls silent on a request still in flight. A
 * state read only at the end cannot tell those apart.
 */
const navigations: { path: string; phase: string; planId: string | null }[] = [];

const NavigationProbe: React.FC = () => {
    const { pathname } = useLocation();
    const store = useStore<RootState>();
    const { phase, planId } = store.getState().progress;
    navigations.push({ path: pathname, phase, planId });
    return null;
};

const renderPlan = () => {
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
    return {
        store,
        ...render(
            <Provider store={store}>
                <MemoryRouter initialEntries={['/chat/plan-troubleshooting']}>
                    <NavigationProbe />
                    <Routes>
                        <Route path="/chat/:id" element={<ChatPage />} />
                    </Routes>
                </MemoryRouter>
            </Provider>,
        ),
    };
};

/** The question the orchestrator put to the associate, exactly as it reaches the browser. */
const ask = async (request_id = 'req-1') => {
    const socket = await waitFor(() => {
        const opened = FakeSocket.latest();
        expect(opened).toBeTruthy();
        return opened!;
    });
    act(() => {
        socket.open();
        socket.deliver(
            frame('user_clarification_request', {
                request_id,
                question: 'What have you already tried?',
            }),
        );
    });
};

/** The hop the previous answer left through, as the Grounding panel received it. */
const groundInCopilotStudio = () => {
    act(() => {
        FakeSocket.latest()!.deliver(
            frame('source_used', {
                platform: 'Copilot Studio',
                source: 'Dataverse',
                agent_name: 'Store SOP Assistant',
                citations: [],
            }),
        );
    });
};

describe('a suggestion while the agent is waiting on an answer', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        navigations.length = 0;
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
        getPlanById.mockReset().mockResolvedValue(PLAN_PAYLOAD);
        vi.mocked(PlanDataService.submitClarification)
            .mockReset()
            .mockResolvedValue({} as never);
        vi.mocked(TaskService.createPlan).mockReset().mockResolvedValue(ESCALATION_RESPONSE);
    });

    it('yields its slot to the rehearsed replies while a clarification is pending', async () => {
        renderPlan();
        expect(await screen.findByRole('button', { name: ESCALATION })).toBeInTheDocument();

        await ask();

        expect(screen.queryByTestId('follow-on-task')).not.toBeInTheDocument();
        expect(
            await screen.findByRole('button', { name: REHEARSED_REPLY }),
        ).toBeInTheDocument();
    });

    it('returns when the answer settles the question, and not merely when it is tapped', async () => {
        /*
          The question is settled by the answer *landing*, not by the tap — the
          orchestration is still waiting until the POST returns, and a card
          returning in that gap is tappable at the one moment it must not be.
          Settled from the wire at both ends: the question arrived on the
          socket, and the answer is held open here until it is released.
        */
        let answerLanded: () => void;
        vi.mocked(PlanDataService.submitClarification).mockImplementation(
            () => new Promise((resolve) => {
                answerLanded = () => resolve({} as never);
            }),
        );
        renderPlan();
        await screen.findByRole('button', { name: ESCALATION });
        await ask();

        fireEvent.click(await screen.findByRole('button', { name: REHEARSED_REPLY }));
        expect(screen.queryByTestId('follow-on-task')).not.toBeInTheDocument();

        await act(async () => {
            answerLanded!();
        });

        expect(
            await screen.findByRole('button', { name: ESCALATION }),
        ).toBeInTheDocument();
        expect(screen.queryByTestId('rehearsed-replies')).not.toBeInTheDocument();
    });

    it('lets the chip answer the question rather than start a turn', async () => {
        // A **Rehearsed reply** always submits an answer. Routing an authored
        // next-turn prompt into the clarification seam would run it through
        // `parse_attempted_steps` and write nonsense into the
        // **Troubleshooting record**; starting a turn here would strand the
        // question the orchestration is waiting on.
        renderPlan();
        await screen.findByRole('button', { name: ESCALATION });
        await ask();

        fireEvent.click(await screen.findByRole('button', { name: REHEARSED_REPLY }));

        await waitFor(() =>
            expect(PlanDataService.submitClarification).toHaveBeenCalledWith(
                expect.objectContaining({
                    request_id: 'req-1',
                    answer: REHEARSED_REPLY,
                }),
            ),
        );
        expect(TaskService.createPlan).not.toHaveBeenCalled();
    });

    it('starts the next turn through the one continuation seam, and answers nothing', async () => {
        /*
          A suggestion always submits a **new turn**, and through
          `submitTurnIntoSession` — the seam that keeps the previous answer's
          provenance dark, narrates the three beats and connects the socket
          before the navigation (ADR-021). It carries the authored **Lane** and
          the viewed plan's `session_id`, so the escalation joins the
          conversation it follows rather than starting one beside it. Asserted
          through what only that seam does, because a second caller of
          `createPlan` is a caller that quietly drops one of them.
        */
        const { store } = renderPlan();
        await screen.findByRole('button', { name: ESCALATION });
        groundInCopilotStudio();
        expect(store.getState().transparency.source).not.toBeNull();

        fireEvent.click(screen.getByRole('button', { name: ESCALATION }));

        await waitFor(() =>
            expect(TaskService.createPlan).toHaveBeenCalledWith(
                'I have tried everything and I need someone to come out.',
                'team-223',
                'deliberate',
                'session-223-troubleshooting',
                'task-223-escalation',
            ),
        );
        // The previous answer's provenance went dark, and the narration is
        // this turn's rather than the last one's.
        expect(store.getState().transparency.source).toBeNull();
        await waitFor(() =>
            expect(store.getState().progress).toMatchObject({
                phase: 'routed',
                planId: 'plan-escalation',
                lane: 'deliberate',
            }),
        );
        // And it knew the routed plan *before* the navigation it caused, which
        // is the ordering that keeps the narration alive across it.
        await waitFor(() =>
            expect(
                navigations.find((entry) => entry.path === '/chat/plan-escalation'),
            ).toMatchObject({ phase: 'routed', planId: 'plan-escalation' }),
        );
        expect(PlanDataService.submitClarification).not.toHaveBeenCalled();
    });
});
