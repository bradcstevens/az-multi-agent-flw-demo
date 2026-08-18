import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { readFileSync } from 'node:fs';

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

import HomePage from './HomePage';
import ChatPage from './ChatPage';
import { TeamService } from '../store/TeamService';
import { PlanDataService } from '../store/PlanDataService';
import { ASSISTANT_NAME, STORE_ASSISTANT_TEAM_ID } from '../models/storeSurface';
import { FakeSocket } from '@/testing/fakeSocket';
import { allRules, sourceFiles } from '@/testing/stylesheets';

import planReducer from '@/store/slices/planSlice';
import chatReducer from '@/store/slices/chatSlice';
import appReducer from '@/store/slices/appSlice';
import teamReducer from '@/store/slices/teamSlice';
import streamingReducer from '@/store/slices/streamingSlice';
import transparencyReducer from '@/store/slices/transparencySlice';
import ticketReducer from '@/store/slices/ticketSlice';
import progressReducer from '@/store/slices/progressSlice';

const VERBATIM_SYSTEM_MESSAGE = `You are the shift-tasks specialist.

First paragraph has punctuation Markdown would eat: *literal*, [brackets], and # hashes.

Second paragraph keeps its blank line.`;

const TEAM = {
    team_id: STORE_ASSISTANT_TEAM_ID,
    name: ASSISTANT_NAME,
    agents: [
        {
            input_key: '',
            type: '',
            name: 'ShiftTasksAgent',
            deployment_name: 'gpt-5.4-mini',
            description: 'Answers routine store-procedure questions from the Store SOP Assistant.',
            system_message: VERBATIM_SYSTEM_MESSAGE,
            knowledge_base_name: 'store-operations-kb',
            user_responses: true,
            temperature: 0.2,
        },
        { input_key: '', type: '', name: 'EscalationAgent' },
    ],
    starting_tasks: [],
} as any;

const renderHomeSurface = () =>
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

const renderChatSurface = () =>
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
            <MemoryRouter initialEntries={['/chat/plan-1']}>
                <Routes>
                    <Route path="/chat/:id" element={<ChatPage />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );

const outline = () =>
    screen.queryAllByRole('heading').map((heading) => ({
        level: Number(heading.tagName.slice(1)),
        text: (heading.textContent ?? '').trim(),
    }));

beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
    window.appConfig = { API_URL: 'https://backend.example/api' } as never;
    vi.mocked(TeamService.getUserTeams).mockResolvedValue([TEAM]);
    vi.mocked(TeamService.initializeTeam).mockResolvedValue({ success: true } as any);
    vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue({
        plan: { id: 'plan-1', overall_status: 'completed' },
        team: TEAM,
        messages: [],
        mplan: null,
        streaming_message: null,
        agents: [],
        steps: [],
    } as any);
});

describe('the Agent dossier on the home surface', () => {
    it('opens the selected specialist with its configured facts and verbatim system message', async () => {
        renderHomeSurface();

        const opener = await screen.findByRole('button', { name: 'Shift Tasks Agent' });
        await userEvent.click(opener);

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        expect(dossier).toBeInTheDocument();
        expect(within(dossier).getByText('Shift Tasks Agent')).toBeInTheDocument();
        expect(within(dossier).getByText('gpt-5.4-mini')).toBeInTheDocument();
        expect(
            within(dossier).getByText('Answers routine store-procedure questions from the Store SOP Assistant.'),
        ).toBeInTheDocument();
        expect(within(dossier).getByTestId('agent-dossier-prompt').textContent).toBe(
            VERBATIM_SYSTEM_MESSAGE,
        );
        expect(within(dossier).getByText('Knowledge base')).toBeInTheDocument();
        expect(within(dossier).getByText('store-operations-kb')).toBeInTheDocument();
        expect(within(dossier).getByText('Follow-up questions')).toBeInTheDocument();
        expect(within(dossier).getByText('Can ask you follow-up questions')).toBeInTheDocument();
        expect(within(dossier).getByText('Temperature')).toBeInTheDocument();
        expect(within(dossier).getByText('0.2')).toBeInTheDocument();
    });

    it('returns focus to the name when Escape closes the dialog', async () => {
        renderHomeSurface();

        const opener = await screen.findByRole('button', { name: 'Shift Tasks Agent' });
        await userEvent.click(opener);

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        expect(dossier.contains(document.activeElement)).toBe(true);

        await userEvent.keyboard('{Escape}');

        expect(screen.queryByRole('dialog', { name: 'Agent dossier' })).not.toBeInTheDocument();
        expect(opener).toHaveFocus();
    });

    it('opens from the keyboard and returns focus after its visible close control', async () => {
        renderHomeSurface();

        const opener = await screen.findByRole('button', { name: 'Shift Tasks Agent' });
        opener.focus();
        await userEvent.keyboard('{Enter}');

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        await userEvent.click(
            within(dossier).getByRole('button', { name: 'Close Agent dossier' }),
        );

        expect(screen.queryByRole('dialog', { name: 'Agent dossier' })).not.toBeInTheDocument();
        expect(opener).toHaveFocus();
    });

    it('does not invent a field the roster did not set', async () => {
        renderHomeSurface();

        await userEvent.click(await screen.findByRole('button', { name: 'Escalation Agent' }));

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        expect(within(dossier).queryByText('Model')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('System message, verbatim')).not.toBeInTheDocument();
        expect(within(dossier).queryByTestId('agent-dossier-prompt')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('Knowledge base')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('Follow-up questions')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('Temperature')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('false')).not.toBeInTheDocument();
    });
});

describe('the Agent dossier layout', () => {
    it('is declared by the surface stylesheet rather than inline', () => {
        const dossierSource = sourceFiles().find((path) => path.endsWith('/AgentDossier.tsx'));
        expect(dossierSource, 'no Agent dossier source was found').toBeDefined();
        expect(readFileSync(dossierSource!, 'utf8')).not.toMatch(/\bstyle=/);

        expect(
            allRules().filter((rule) => rule.selector.includes('.agent-dossier')),
            'the Agent dossier has no stylesheet layout',
        ).not.toEqual([]);
    });
});

describe('the Agent dossier leaves each surface outline unchanged', () => {
    it.each([
        ['home', renderHomeSurface],
        ['chat', renderChatSurface],
    ])('opens on the %s surface without adding a heading', async (_, renderSurface) => {
        renderSurface();

        const opener = await screen.findByRole('button', { name: 'Shift Tasks Agent' });
        const before = outline();
        await userEvent.click(opener);

        expect(screen.getByRole('dialog', { name: 'Agent dossier' })).toBeInTheDocument();
        expect(outline()).toEqual(before);

        cleanup();
    });
});
