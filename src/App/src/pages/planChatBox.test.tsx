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
        approvePlan: vi.fn(),
        getSessionState: vi.fn(async () => ({})),
    };
    return { apiService, APIService: vi.fn(() => apiService) };
});

/*
  Only the two calls that leave the browser are stubbed. The clarification
  parser stays real, because whether a frame is a question this surface can
  answer is its verdict — a stubbed parser would let this suite agree with
  itself about a shape the service never produces (#47).
*/
vi.mock('../store/PlanDataService', async (importOriginal) => {
    const actual = await importOriginal<typeof import('../store/PlanDataService')>();
    class StubbedPlanDataService extends actual.PlanDataService {
        static fetchPlanData = vi.fn();
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
    // The barrel re-exports the default binding, which the conversation's
    // agent messages reach for; a factory that returns only the named one
    // hands them `undefined`.
    return { TaskService: StubbedTaskService, default: StubbedTaskService };
});

vi.mock('../components/content/ChatPanelLeft', () => ({ default: () => null }));
vi.mock('../components/content/PlanPanelRight', () => ({ default: () => null }));

import ChatPage from './ChatPage';
import { PlanDataService } from '../store/PlanDataService';
import planReducer from '../store/slices/planSlice';
import chatReducer from '../store/slices/chatSlice';
import appReducer from '../store/slices/appSlice';
import teamReducer from '../store/slices/teamSlice';
import streamingReducer from '../store/slices/streamingSlice';
import transparencyReducer from '../store/slices/transparencySlice';
import ticketReducer from '../store/slices/ticketSlice';
import progressReducer from '@/store/slices/progressSlice';
import { FakeSocket, frame } from '@/testing/fakeSocket';
import { NOTHING_TO_ANSWER } from '../components/content/PlanChatBody';
import { PlanStatus, ProcessedPlanData } from '../models';

/**
 * What the chat surface's message box does with what is typed into it (#68).
 *
 * The box answers a **Clarification** and nothing else, so the question this
 * suite asks is the one the surface got wrong in both directions: it posted a
 * clarification carrying an empty `request_id` when none had been asked, and it
 * went on believing one was pending after it had been answered.
 *
 * Driven from the wire — a `user_clarification_request` frame through
 * `FakeSocket` — rather than by dispatching into the store, because "is a
 * clarification pending" is a claim about what the backend asked, and a test
 * that arranges the answer to that in the store can only agree with itself.
 * The assertion is on the submit path, `PlanDataService.submitClarification`.
 */

const ANSWER = 'I switched it off at the wall and back on again.';

const PLAN_DATA = {
    plan: {
        id: 'plan-troubleshooting',
        data_type: 'plan',
        initial_goal: 'The coffee brewer is down.',
        session_id: 'session-223',
        timestamp: '',
        plan_id: 'plan-troubleshooting',
        user_id: 'user-223',
        overall_status: PlanStatus.IN_PROGRESS,
    },
    team: null,
    messages: [],
    mplan: null,
    streaming_message: null,
} as unknown as ProcessedPlanData;

const renderPlan = () =>
    render(
        <Provider
            store={configureStore({
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
            })}
        >
            <MemoryRouter initialEntries={['/chat/plan-troubleshooting']}>
                <Routes>
                    <Route path="/chat/:id" element={<ChatPage />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );

/** The question the orchestrator put to the associate, exactly as it reaches the browser. */
const ask = async (data: Record<string, unknown>) => {
    const socket = await waitFor(() => {
        const opened = FakeSocket.latest();
        expect(opened).toBeTruthy();
        return opened!;
    });
    act(() => {
        socket.open();
        socket.deliver(frame('user_clarification_request', data));
    });
};

const answer = (text: string) => {
    fireEvent.change(screen.getByRole('textbox'), { target: { value: text } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
};

describe('the chat surface message box', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
        vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(PLAN_DATA);
        vi.mocked(PlanDataService.submitClarification)
            .mockReset()
            .mockResolvedValue({} as never);
    });

    it('answers the clarification it was asked, with that question\'s request id', async () => {
        renderPlan();
        await screen.findByRole('textbox');
        await ask({ request_id: 'req-1', question: 'What have you already tried?' });

        answer(ANSWER);

        await waitFor(() =>
            expect(PlanDataService.submitClarification).toHaveBeenCalledWith(
                expect.objectContaining({ request_id: 'req-1', answer: ANSWER }),
            ),
        );
    });

    it('answers nothing when the question carries no request id', async () => {
        // A clarification with no identifier is not a question this surface can
        // answer, so the box does not open on it. Answering it anyway posted a
        // clarification against an empty `request_id` — a request answering
        // nothing, and the typed message gone. The frame is refused where it
        // arrives, rather than throwing inside the socket's listener and being
        // logged there, which is how it was previously "handled".
        const logged = vi.spyOn(console, 'error').mockImplementation(() => {});
        renderPlan();
        await screen.findByRole('textbox');
        await ask({ question: 'What have you already tried?' });

        expect(screen.getByRole('status')).toHaveTextContent(NOTHING_TO_ANSWER);
        expect(screen.getByRole('textbox')).toBeDisabled();
        expect(PlanDataService.submitClarification).not.toHaveBeenCalled();
        expect(logged.mock.calls.flat().join(' ')).not.toContain('Listener error');
        logged.mockRestore();
    });

    it('says nothing is waiting on a reply before any question has been asked', async () => {
        renderPlan();

        expect(await screen.findByRole('status')).toHaveTextContent(NOTHING_TO_ANSWER);
    });

    it('stops treating a clarification as pending once it has been answered', async () => {
        // The question is settled the moment it is answered. Leaving it in the
        // store left the surface claiming one was pending for the rest of the
        // conversation — the **Rehearsed replies** still offered, and a retry
        // aimed at a `request_id` the backend has already resolved.
        renderPlan();
        await screen.findByRole('textbox');
        await ask({ request_id: 'req-1', question: 'What have you already tried?' });

        answer(ANSWER);

        expect(await screen.findByRole('status')).toHaveTextContent(NOTHING_TO_ANSWER);
    });

    it('leaves the next question standing when a slower answer to the last one lands', async () => {
        // The backend releases the orchestration before it finishes persisting,
        // so the next question can reach the browser while the previous answer
        // is still in flight. An answer that settled whatever happened to be
        // stored would close the box on a question the backend is waiting on.
        let settleTheAnswer: () => void;
        vi.mocked(PlanDataService.submitClarification).mockImplementation(
            () => new Promise((resolve) => {
                settleTheAnswer = () => resolve({} as never);
            }),
        );
        renderPlan();
        await screen.findByRole('textbox');
        await ask({ request_id: 'req-1', question: 'What have you already tried?' });
        answer(ANSWER);
        await ask({ request_id: 'req-2', question: 'Which head is it, left or right?' });

        await act(async () => {
            settleTheAnswer!();
        });

        expect(screen.queryByRole('status')).not.toBeInTheDocument();
        expect(screen.getByRole('textbox')).not.toBeDisabled();
    });

    it('posts nothing when the submit path is reached with no question pending', async () => {
        /*
          The surface offers no route to this: the box is closed and the chips
          are gone. The guard is what makes the claim hold in *any* state —
          including the one **Resume** introduces, where the box is open and a
          turn typed into it is not a clarification (ADR-027, #77). Driven at
          the callback, because the point is that the seam refuses rather than
          that the door is locked.
        */
        renderPlan();
        const box = await screen.findByRole('textbox');

        fireEvent.keyDown(box, { key: 'Enter' });

        expect(PlanDataService.submitClarification).not.toHaveBeenCalled();
        expect(screen.queryByText(/clarification/i)).not.toBeInTheDocument();
    });
});
