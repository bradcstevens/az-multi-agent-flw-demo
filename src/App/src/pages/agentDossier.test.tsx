import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
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

vi.mock('../store/PlanDataService', async (importOriginal) => {
    const actual = await importOriginal<typeof import('../store/PlanDataService')>();
    class TestPlanDataService extends actual.PlanDataService {}
    TestPlanDataService.fetchPlanData = vi.fn();
    return { ...actual, PlanDataService: TestPlanDataService };
});

import HomePage from './HomePage';
import ChatPage from './ChatPage';
import { TeamService } from '../store/TeamService';
import { PlanDataService } from '../store/PlanDataService';
import { ASSISTANT_NAME, STORE_ASSISTANT_TEAM_ID } from '../models/storeSurface';
import webSocketService from '@/store/WebSocketService';
import { FakeSocket, frame } from '@/testing/fakeSocket';
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
            toolbox_filter: 'sop',
            use_toolbox: true,
            use_knowledge_base: true,
            knowledge_base_name: 'store-operations-kb',
            user_responses: true,
            temperature: 0.2,
        },
        {
            input_key: '',
            type: '',
            name: 'WorkforceAgent',
            deployment_name: 'gpt-5.4-mini',
            system_message: 'You answer HR process questions and never an individual record.',
            toolbox_filter: 'workforce',
            use_toolbox: false,
            use_knowledge_base: false,
            knowledge_base_name: 'store-operations-kb',
            user_responses: false,
            temperature: null,
        },
        // No `toolbox_filter` the browser's mirror carries, deliberately: the
        // real pack gives this agent the `escalation` domain, and the point
        // here is what the dossier does when it recognises none.
        { input_key: '', type: '', name: 'EscalationAgent', toolbox_filter: 'unknown-domain' },
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
        expect(within(dossier).getByText('MCP tools')).toBeInTheDocument();
        expect(within(dossier).getByText('search_store_procedures')).toBeInTheDocument();
        expect(within(dossier).getByText('Searches store procedures')).toBeInTheDocument();
        expect(within(dossier).getByText('Knowledge base')).toBeInTheDocument();
        expect(within(dossier).getByText('store-operations-kb')).toBeInTheDocument();
        expect(within(dossier).getByText('Follow-up questions')).toBeInTheDocument();
        expect(within(dossier).getByText('Can ask you follow-up questions')).toBeInTheDocument();
        expect(within(dossier).getByText('Temperature')).toBeInTheDocument();
        expect(within(dossier).getByText('0.2')).toBeInTheDocument();
    });

    it('reads the standing MCP tools after the prompt and before configured facts', async () => {
        renderHomeSurface();

        await userEvent.click(await screen.findByRole('button', { name: 'Shift Tasks Agent' }));

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        const prompt = within(dossier).getByTestId('agent-dossier-prompt');
        const tools = within(dossier).getByTestId('agent-dossier-mcp-tools');
        const configuration = within(dossier).getByTestId('agent-dossier-configuration');

        expect(
            prompt.compareDocumentPosition(tools) & Node.DOCUMENT_POSITION_FOLLOWING,
        ).toBeTruthy();
        expect(
            tools.compareDocumentPosition(configuration) & Node.DOCUMENT_POSITION_FOLLOWING,
        ).toBeTruthy();
    });

    it('states availability without making a participation claim', async () => {
        renderHomeSurface();

        await userEvent.click(await screen.findByRole('button', { name: 'Shift Tasks Agent' }));

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        expect(within(dossier).getByText('Available')).toBeInTheDocument();
        expect(within(dossier).queryByText('Spoke in this answer')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('Available, has not spoken')).not.toBeInTheDocument();
    });

    it('reads the configured facts after the prompt, in the order the spec sets out', async () => {
        renderHomeSurface();

        await userEvent.click(await screen.findByRole('button', { name: 'Shift Tasks Agent' }));

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        const prompt = within(dossier).getByTestId('agent-dossier-prompt');
        const configuration = within(dossier).getByTestId('agent-dossier-configuration');

        // What the agent was told is read before how it was configured to use it.
        expect(
            prompt.compareDocumentPosition(configuration) & Node.DOCUMENT_POSITION_FOLLOWING,
        ).toBeTruthy();
        expect(
            Array.from(configuration.querySelectorAll('dt')).map((label) => label.textContent),
        ).toEqual(['Knowledge base', 'Follow-up questions', 'Temperature']);
    });

    it('states a knowledge base the pack switched off as no knowledge base at all', async () => {
        renderHomeSurface();

        await userEvent.click(await screen.findByRole('button', { name: 'Workforce Agent' }));

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        // The pack names one and sets `use_knowledge_base` false, which is what
        // the backend reads before it attaches anything: this agent reads none.
        expect(within(dossier).queryByText('Knowledge base')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('store-operations-kb')).not.toBeInTheDocument();
        // Every agent in the store pack runs at the deployment's own temperature.
        expect(within(dossier).queryByText('Temperature')).not.toBeInTheDocument();
        // A configured `false` is a choice the pack made, said in plain English.
        expect(
            within(dossier).getByText('Will not ask you follow-up questions'),
        ).toBeInTheDocument();
        expect(within(dossier).queryByText('false')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('null')).not.toBeInTheDocument();
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
        // Not even the container the three would have hung from.
        expect(within(dossier).queryByTestId('agent-dossier-configuration')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('false')).not.toBeInTheDocument();
    });

    it('states a toolbox the pack switched off as no tools at all', async () => {
        renderHomeSurface();

        await userEvent.click(await screen.findByRole('button', { name: 'Workforce Agent' }));

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        // The pack names a domain and sets `use_toolbox` false, which is what
        // the backend reads before it attaches anything: this agent holds no
        // tools, so a standing claim that it holds two would be the false
        // disclosure the split exists to prevent.
        expect(within(dossier).queryByText('MCP tools')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('list_workforce_procedures')).not.toBeInTheDocument();
        expect(within(dossier).queryByText('get_workforce_procedure')).not.toBeInTheDocument();
        expect(within(dossier).queryByTestId('agent-dossier-mcp-tools')).not.toBeInTheDocument();
    });

    it('does not guess MCP tools for a domain the browser does not recognise', async () => {
        renderHomeSurface();

        await userEvent.click(await screen.findByRole('button', { name: 'Escalation Agent' }));

        const dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        expect(within(dossier).queryByText('MCP tools')).not.toBeInTheDocument();
        expect(within(dossier).queryByTestId('agent-dossier-mcp-tools')).not.toBeInTheDocument();
    });
});

describe('the Agent dossier on the chat surface', () => {
    it('names a specialist as available before its stream frame and as having spoken after it', async () => {
        const connecting = webSocketService.connect('plan-1');
        const socket = FakeSocket.latest()!;
        socket.open();
        await connecting;
        renderChatSurface();

        const opener = await screen.findByRole('button', { name: 'Shift Tasks Agent' });
        await userEvent.click(opener);
        let dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        expect(within(dossier).getByText('Available, has not spoken')).toBeInTheDocument();
        expect(within(dossier).queryByText('Spoke in this answer')).not.toBeInTheDocument();
        expect(screen.queryByTestId('meter-row-ShiftTasksAgent')).not.toBeInTheDocument();

        await userEvent.keyboard('{Escape}');
        act(() => {
            socket.deliver(
                frame('agent_message_streaming', {
                    agent_name: 'shift_tasks_agent',
                    content: 'Check the closing procedure.',
                    is_final: false,
                }),
            );
        });

        await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
        await userEvent.click(opener);
        dossier = screen.getByRole('dialog', { name: 'Agent dossier' });
        expect(within(dossier).getByText('Spoke in this answer')).toBeInTheDocument();
        expect(within(dossier).queryByText('Available, has not spoken')).not.toBeInTheDocument();
        expect(screen.queryByTestId('meter-row-ShiftTasksAgent')).not.toBeInTheDocument();
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
