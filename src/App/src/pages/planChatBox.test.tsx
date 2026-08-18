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
        getChatTicket: vi.fn(async () => null),
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
import { TaskService } from '../store/TaskService';
import { ANSWER_THE_QUESTION, CONTINUE_THIS_CHAT } from '../models/resume';
import { PolicyBlockError } from '../api/policyBlock';
import { PERSONAL_ANSWER_KIND } from '../models/personalAnswer';
import {
    forgetSignedInDevice,
    rememberSignedInName,
    signedInName,
} from '../models/signedInDevice';
import { GUARDRAIL_ROW_KEY } from '../models/meter';
import { InputTaskResponse, PlanStatus, ProcessedPlanData } from '../models';

/**
 * What the chat surface's message box does with what is typed into it (#68,
 * #77).
 *
 * The box is one control with two acts (ADR-027): it answers a pending
 * **Clarification**, and outside one it continues this **Chat**'s **Session**.
 * The question this suite asks is the one the surface got wrong in every
 * direction available to it — it posted a clarification carrying an empty
 * `request_id` when none had been asked, went on believing one was pending
 * after it had been answered, and minted a fresh session for every turn, which
 * is the defect the **Follow-on task** card was authored around.
 *
 * Driven from the wire — a `user_clarification_request` frame through
 * `FakeSocket` — rather than by dispatching into the store, because "is a
 * clarification pending" is a claim about what the backend asked, and a test
 * that arranges the answer to that in the store can only agree with itself.
 * The assertion is on the submit path, `PlanDataService.submitClarification`.
 */

const ANSWER = 'I switched it off at the wall and back on again.';
/** A new question, typed into a chat nobody is waiting on. */
const FOLLOW_UP = 'Where is the filter stored?';

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
        <Provider
            store={store}
        >
            <MemoryRouter initialEntries={['/chat/plan-troubleshooting']}>
                <Routes>
                    <Route path="/chat/:id" element={<ChatPage />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
        ),
    };
};

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

/** What the resumed turn's request comes back as. */
const RESUMED = {
    status: 'accepted',
    session_id: 'session-223',
    plan_id: 'plan-resumed',
    description: 'Where is the filter stored?',
    lane: 'fast',
} satisfies InputTaskResponse;

/** A personal question, typed into a chat rather than into the home screen. */
const PERSONAL = 'How much PTO do I have left?';

/** The Identity boundary gate declining it (ADR-014). */
const REFUSAL = new PolicyBlockError({
    kind: 'policy_block',
    code: 'identity_boundary',
    message:
        'This assistant is set up for Store 223 rather than for individual associates.',
});

/** The Mocked unlock answering it: a successful request that made no plan (#27). */
const PERSONAL_REPLY = {
    status: "Answered from the associate's record",
    session_id: 'session-223',
    plan_id: null,
    personal_answer: {
        kind: PERSONAL_ANSWER_KIND,
        display_name: 'Tanya Alvarez',
        role: 'Store associate, Store 223',
        facts: [{ label: 'PTO balance', value: '34.5 hours' }],
        provenance_line:
            'No payroll system was queried — these figures were authored for this walkthrough.',
    },
} as unknown as InputTaskResponse;

describe('the chat surface message box', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
        vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(PLAN_DATA);
        vi.mocked(PlanDataService.submitClarification)
            .mockReset()
            .mockResolvedValue({} as never);
        vi.mocked(TaskService.createPlan).mockReset().mockResolvedValue(RESUMED);
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

    it('answers no clarification carrying no request id, and resumes instead', async () => {
        // A clarification with no identifier is not a question this surface can
        // answer. Answering it anyway posted a clarification against an empty
        // `request_id` — a request answering nothing, and the typed message
        // gone (#68). The box is open now, so what is typed is a new turn in
        // this chat rather than a message with nowhere to go. The frame is
        // still refused where it arrives, rather than throwing inside the
        // socket's listener and being logged there.
        const logged = vi.spyOn(console, 'error').mockImplementation(() => {});
        renderPlan();
        await screen.findByRole('textbox');
        await ask({ question: 'What have you already tried?' });

        answer(ANSWER);

        await waitFor(() => expect(TaskService.createPlan).toHaveBeenCalled());
        expect(PlanDataService.submitClarification).not.toHaveBeenCalled();
        expect(logged.mock.calls.flat().join(' ')).not.toContain('Listener error');
        logged.mockRestore();
    });

    it('invites another turn in this chat before any question has been asked', async () => {
        renderPlan();

        expect(
            await screen.findByPlaceholderText(CONTINUE_THIS_CHAT),
        ).toBeInTheDocument();
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

        expect(
            await screen.findByPlaceholderText(CONTINUE_THIS_CHAT),
        ).toBeInTheDocument();
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

        expect(
            screen.getByPlaceholderText(ANSWER_THE_QUESTION),
        ).toBeInTheDocument();
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

describe('resuming a chat from its message box', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
        vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(PLAN_DATA);
        vi.mocked(PlanDataService.submitClarification)
            .mockReset()
            .mockResolvedValue({} as never);
        vi.mocked(TaskService.createPlan).mockReset().mockResolvedValue(RESUMED);
    });

    it("carries this chat's session rather than minting a new one", async () => {
        /*
          ADR-027, and the whole of #77. Every submission used to mint a fresh
          `session_id`, which is why the **Simulated ticket** read an empty
          **Troubleshooting record** and why the **Follow-on task** card had to
          be authored to work around it. The lane is not declared, because a
          typed turn is free-typed input and belongs to the **Lane keyword
          fallback**; nor is a **Quick Task** id, because none was tapped.
        */
        renderPlan();
        await screen.findByRole('textbox');

        answer(FOLLOW_UP);

        await waitFor(() =>
            expect(TaskService.createPlan).toHaveBeenCalledWith(
                FOLLOW_UP,
                undefined,
                undefined,
                'session-223',
                undefined,
            ),
        );
    });

    it('sends what was typed, and never the transcript', async () => {
        /*
          Resume carries only what was explicitly persisted against the session
          (ADR-027). The transcript on screen is display-only: replaying it
          would fabricate a per-Chat agent memory that the user-keyed,
          in-process **Workflow cache** does not preserve, and the demonstration
          would be claiming a continuity it cannot keep.
        */
        renderPlan();
        await screen.findByRole('textbox');
        // The conversation so far is on screen — asserted, so that "it is not
        // sent" is a claim about something the surface really is displaying.
        await screen.findByText(PLAN_DATA.plan.initial_goal);

        answer(FOLLOW_UP);

        await waitFor(() => expect(TaskService.createPlan).toHaveBeenCalled());
        const [description] = vi.mocked(TaskService.createPlan).mock.calls[0];
        expect(description).toBe(FOLLOW_UP);
        expect(description).not.toContain(PLAN_DATA.plan.initial_goal);
    });

    it('opens the plan the resumed turn created', async () => {
        renderPlan();
        await screen.findByRole('textbox');

        answer(FOLLOW_UP);

        await waitFor(() =>
            expect(PlanDataService.fetchPlanData).toHaveBeenCalledWith(
                'plan-resumed',
                expect.anything(),
            ),
        );
    });

    it('answers the pending clarification instead of resuming, when one is pending', async () => {
        // One control, two acts, and the pending question wins: a turn typed
        // while the orchestration is waiting on an answer is that answer, and
        // starting a new plan with it would strand the turn that asked.
        renderPlan();
        await screen.findByRole('textbox');
        await ask({ request_id: 'req-1', question: 'What have you already tried?' });

        answer(ANSWER);

        await waitFor(() =>
            expect(PlanDataService.submitClarification).toHaveBeenCalled(),
        );
        expect(TaskService.createPlan).not.toHaveBeenCalled();
    });

    it('starts nothing when nothing was typed', async () => {
        renderPlan();
        const box = await screen.findByRole('textbox');

        fireEvent.change(box, { target: { value: '   ' } });
        fireEvent.keyDown(box, { key: 'Enter' });

        expect(TaskService.createPlan).not.toHaveBeenCalled();
    });

    it('submits one turn while it is being created', async () => {
        // The box is not disabled by the send itself the way the follow-on
        // card is by its own ref, so the in-flight lock has to be this path's.
        let settle: () => void;
        vi.mocked(TaskService.createPlan).mockImplementation(
            () => new Promise((resolve) => {
                settle = () => resolve(RESUMED);
            }),
        );
        renderPlan();
        await screen.findByRole('textbox');

        answer(FOLLOW_UP);
        answer(FOLLOW_UP);

        expect(TaskService.createPlan).toHaveBeenCalledTimes(1);
        settle!();
    });
});

/**
 * What a resumed turn that produced no plan says.
 *
 * Both of these were unreachable from this surface until resume: the box
 * answered clarifications, and a clarification is neither refused by the
 * **Identity boundary** gate nor answered out of an associate's record. A
 * question typed into a chat is an ordinary question, so it can be either —
 * and reporting either as "Unable to create plan" is the surface calling a
 * governed refusal, or an answer, a bug (ADR-014, #27).
 */
describe('a resumed turn that made no plan', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
        vi.mocked(PlanDataService.fetchPlanData)
            .mockReset()
            .mockResolvedValue(PLAN_DATA);
        vi.mocked(TaskService.createPlan).mockReset().mockResolvedValue(RESUMED);
        forgetSignedInDevice();
    });

    it('renders a Policy block as policy rather than as a failed request', async () => {
        vi.mocked(TaskService.createPlan).mockRejectedValue(REFUSAL);
        renderPlan();
        await screen.findByRole('textbox');

        answer(PERSONAL);

        const notice = await screen.findByTestId('policy-block');
        expect(notice).toHaveTextContent(REFUSAL.policyBlock.message);
        expect(notice).toHaveAttribute('data-policy-code', 'identity_boundary');
        expect(
            screen.queryByText(/Unable to create plan/i),
        ).not.toBeInTheDocument();
    });

    it('records the refusal on the Token meter, as a measured zero', async () => {
        // A refused request adds nothing, and the row showing that zero beside
        // rows that cost something is what makes "nothing" legible (#24, R7).
        // The meter is one claim about this conversation whichever surface the
        // question was typed on.
        vi.mocked(TaskService.createPlan).mockRejectedValue(REFUSAL);
        const { store } = renderPlan();
        await screen.findByRole('textbox');

        answer(PERSONAL);

        await screen.findByTestId('policy-block');
        const { meter } = (store.getState() as never as {
            transparency: { meter: { rows: Record<string, unknown>[] } };
        }).transparency;
        expect(meter.rows).toContainEqual(
            expect.objectContaining({
                key: GUARDRAIL_ROW_KEY,
                billing: 'refused',
                totalTokens: 0,
                calls: 1,
            }),
        );
    });

    it('stops naming an associate the gate has just declined to answer for', async () => {
        // A refusal *is* the gate stating that nobody is signed in. The header
        // reads the device's own record, so a refusal that left it standing
        // would have the surface naming somebody the gate will not serve.
        rememberSignedInName('Tanya Alvarez');
        vi.mocked(TaskService.createPlan).mockRejectedValue(REFUSAL);
        renderPlan();
        await screen.findByRole('textbox');

        answer(PERSONAL);

        await screen.findByTestId('policy-block');
        expect(signedInName()).toBeNull();
    });

    it('renders the associate record as the answer it is', async () => {
        vi.mocked(TaskService.createPlan).mockResolvedValue(PERSONAL_REPLY);
        renderPlan();
        await screen.findByRole('textbox');

        answer(PERSONAL);

        const card = await screen.findByTestId('personal-answer');
        expect(card).toHaveTextContent('Tanya Alvarez');
        expect(card).toHaveTextContent('34.5 hours');
        expect(
            screen.queryByText(/Unable to create plan/i),
        ).not.toBeInTheDocument();
    });

    it('stays on the chat it was typed into, since there is no plan to open', async () => {
        vi.mocked(TaskService.createPlan).mockResolvedValue(PERSONAL_REPLY);
        renderPlan();
        await screen.findByRole('textbox');

        answer(PERSONAL);

        await screen.findByTestId('personal-answer');
        // Every read is still of the chat that was typed into: a plan-less
        // answer is not a navigation, and `requestRouted` never fired.
        vi.mocked(PlanDataService.fetchPlanData).mock.calls.forEach(([id]) =>
            expect(id).toBe('plan-troubleshooting'),
        );
    });

    it('clears the previous turn\'s refusal when the next turn starts', async () => {
        // A refusal is about the turn that was refused. Left up beside the
        // answer that replaced it, it reads as though it were still in force —
        // which is the before-and-after of #27 shown backwards.
        vi.mocked(TaskService.createPlan).mockRejectedValueOnce(REFUSAL);
        renderPlan();
        await screen.findByRole('textbox');

        answer(PERSONAL);
        await screen.findByTestId('policy-block');

        answer(FOLLOW_UP);

        await waitFor(() =>
            expect(screen.queryByTestId('policy-block')).not.toBeInTheDocument(),
        );
    });
});
