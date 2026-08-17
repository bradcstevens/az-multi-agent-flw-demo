import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
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

import HomePage from './HomePage';
import { TeamService } from '../store/TeamService';
import { TaskService } from '../store/TaskService';
import { PolicyBlockError } from '../api/policyBlock';
import { ASSISTANT_NAME, STORE_ASSISTANT_TEAM_ID } from '../models/storeSurface';
import { AVAILABILITY_NOTE } from '../models/agentAvailability';
import { GUARDRAIL_ROW_KEY } from '../models/meter';
import { FakeSocket } from '@/testing/fakeSocket';

import planReducer from '@/store/slices/planSlice';
import chatReducer from '@/store/slices/chatSlice';
import appReducer from '@/store/slices/appSlice';
import teamReducer from '@/store/slices/teamSlice';
import streamingReducer from '@/store/slices/streamingSlice';
import transparencyReducer from '@/store/slices/transparencySlice';
import ticketReducer from '@/store/slices/ticketSlice';
import progressReducer from '@/store/slices/progressSlice';

/**
 * The rail states who is **available**, before a question is typed (issue #79).
 *
 * Availability is a true thing the surface can state **before any question is
 * sent** — the **store assistant roster** is the one this page already resolves
 * in order to exist at all, so the count needs no request of its own and
 * nothing on the socket. It is not stated *before* that roster resolves: the
 * panel is absent for the whole team fetch rather than rendering an empty state
 * beside a spinner, which is the contradiction #65 removed on the other
 * surface. Participation is a different claim entirely, and this file's job is
 * to keep the two apart on the one beat where conflating them would be caught
 * out: the
 * **Identity boundary gate** refuses the boundary probe above the **Lane
 * router**, so the number that participate is zero and the **Token meter**
 * renders a measured `0` two panels below the roster.
 */

const TEAM = {
    team_id: STORE_ASSISTANT_TEAM_ID,
    name: ASSISTANT_NAME,
    agents: [
        { input_key: '', type: '', name: 'TroubleshootingAgent', deployment_name: 'o4-mini' },
        { input_key: '', type: '', name: 'ShiftTasksAgent', deployment_name: 'gpt-4.1-mini' },
        { input_key: '', type: '', name: 'EscalationAgent', deployment_name: 'gpt-4.1-mini' },
    ],
    starting_tasks: [],
} as any;

const REFUSAL = new PolicyBlockError({
    kind: 'policy_block',
    code: 'identity_boundary',
    message: 'This assistant is set up for Store 223 rather than for individual associates.',
});

const createPlan = vi.spyOn(TaskService, 'createPlan');

const renderHome = () =>
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
            <MemoryRouter>
                <HomePage />
            </MemoryRouter>
        </Provider>,
    );

const rail = () => screen.getByTestId('transparency-rail');
const teamPanel = () => screen.getByTestId('agent-team-panel');

/**
 * Every word that would turn availability into participation. Scoped to the
 * Agent Team panel rather than the whole rail: the **Grounding** panel's own
 * empty state legitimately speaks of an answer, and it is not this panel's
 * claim.
 */
const PARTICIPATION = /identified|assigned|selected|chosen|participated|responded|took part/i;

beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
    window.appConfig = { API_URL: 'https://backend.example/api' } as never;
    vi.mocked(TeamService.getUserTeams).mockResolvedValue([TEAM]);
    vi.mocked(TeamService.initializeTeam).mockResolvedValue({ success: true } as any);
    createPlan.mockReset().mockResolvedValue({ plan_id: 'plan-1' } as any);
});

describe('the rail states who is available, before a question is typed', () => {
    it('accepts typing while the team initialization request is still in flight', async () => {
        let finishInitialization: () => void = () => undefined;
        vi.mocked(TeamService.initializeTeam).mockReturnValue(
            new Promise((resolve) => {
                finishInitialization = () => resolve({ success: true } as any);
            }),
        );
        renderHome();

        const textbox = await screen.findByRole('textbox');
        await userEvent.type(textbox, 'How do I close the store?');

        expect(textbox).toHaveValue('How do I close the store?');
        expect(TeamService.initializeTeam).toHaveBeenCalledWith(TEAM.team_id);
        finishInitialization();
    });

    it('counts the specialists from the roster with nothing yet sent', async () => {
        renderHome();

        const availability = await screen.findByTestId('agent-team-availability');
        expect(availability).toHaveTextContent('3 specialists available');
        expect(createPlan).not.toHaveBeenCalled();
    });

    it('names them in the rail rather than only counting them', async () => {
        renderHome();

        await screen.findByTestId('agent-team-availability');
        expect(within(rail()).getAllByTestId(/^agent-team-member/)).toHaveLength(3);
    });

    it('says nothing at all about a roster it does not have', async () => {
        // #78's rule: a panel whose only content is the statement that it is
        // empty is worse than no panel. And its empty state speaks of "this
        // conversation", of which the home surface has none. The surface
        // already says the honest version once, in the middle of the screen.
        vi.mocked(TeamService.getUserTeams).mockResolvedValue([]);

        renderHome();

        await waitFor(() =>
            expect(screen.getByTestId('assistant-unavailable')).toBeInTheDocument(),
        );
        expect(screen.queryByTestId('agent-team-panel')).not.toBeInTheDocument();
    });

    it('says nothing while the roster is still being resolved', async () => {
        // #65's contradiction, one surface across: `selectedTeam` is null for
        // the whole of the team fetch, and an empty roster panel beside a
        // spinner reading "Starting the store assistant..." is the surface
        // telling the room two things at once. It holds its tongue instead.
        let release: (teams: unknown[]) => void = () => undefined;
        vi.mocked(TeamService.getUserTeams).mockReturnValue(
            new Promise((resolve) => {
                release = resolve as (teams: unknown[]) => void;
            }) as never,
        );

        renderHome();

        expect(screen.queryByTestId('agent-team-panel')).not.toBeInTheDocument();
        expect(screen.getByTestId('transparency-rail')).toBeInTheDocument();

        release([TEAM]);
        expect(await screen.findByTestId('agent-team-availability')).toHaveTextContent(
            '3 specialists available',
        );
    });
});

describe('what the home rail is allowed to claim', () => {
    it('claims availability and never participation', async () => {
        renderHome();

        await screen.findByTestId('agent-team-availability');
        expect(screen.getByTestId('agent-team-note')).toHaveTextContent(AVAILABILITY_NOTE);
        expect(within(teamPanel()).queryByText(PARTICIPATION)).not.toBeInTheDocument();
    });

    it('presupposes no question, because none has been typed', async () => {
        // The note is on screen before anything has been asked, so a note that
        // speaks of "this question" is describing one that does not exist.
        renderHome();

        await screen.findByTestId('agent-team-note');
        expect(AVAILABILITY_NOTE).not.toMatch(/this question/i);
    });
});

describe('the boundary-probe beat', () => {
    it('leaves the availability claim standing beside the meter\u2019s measured zero', async () => {
        // The gate refuses above the Lane router, so the number that
        // participate is zero. Availability is unchanged by that — the three
        // specialists were available and none of them was asked — and the two
        // statements sit two panels apart without contradicting each other.
        createPlan.mockRejectedValue(REFUSAL);
        renderHome();

        const textbox = await screen.findByRole('textbox');
        await userEvent.type(textbox, 'how much PTO do I have?');
        await userEvent.click(screen.getByRole('button', { name: 'Send question' }));

        await screen.findByTestId('policy-block');

        // The meter's *only* row is the guardrail's, measured at zero tokens.
        // Not one of the three available specialists is on it, which is what
        // "zero participated" means when it is read off the screen rather than
        // asserted about one name.
        const row = await screen.findByTestId(`meter-row-${GUARDRAIL_ROW_KEY}`);
        expect(within(row).getByTestId('meter-tokens')).toHaveTextContent('0');
        expect(screen.getAllByTestId(/^meter-row-/)).toHaveLength(1);

        const billed = screen.getAllByTestId('meter-agent').map((cell) => cell.textContent);
        for (const agent of TEAM.agents) {
            expect(billed.join(' ')).not.toContain(agent.name.replace(/Agent$/, ''));
        }

        // And the roster still says all three were available, which the beat
        // has not made untrue.
        expect(screen.getByTestId('agent-team-availability')).toHaveTextContent(
            '3 specialists available',
        );
        expect(within(teamPanel()).queryByText(PARTICIPATION)).not.toBeInTheDocument();
    });
});
