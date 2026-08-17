import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
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
import TransparencyRail from '@/components/transparency/TransparencyRail';
import AgentTeamPanel from '@/components/transparency/AgentTeamPanel';
import { TeamService } from '../store/TeamService';
import { PlanDataService } from '../store/PlanDataService';
import {
    ASSISTANT_NAME,
    STORE_ASSISTANT_TEAM_ID,
    TRANSPARENCY_PANELS_LABEL,
} from '../models/storeSurface';
import { AgentMessageType } from '../models';
import { SECTION_HEADING, SUBSECTION_HEADING, SURFACE_HEADING } from '../models/headingOutline';
import { TRANSPARENCY_RAIL_ID } from '@/models/panelDrawer';
import { sourceFiles } from '@/testing/stylesheets';
import { FakeSocket } from '@/testing/fakeSocket';

import planReducer from '@/store/slices/planSlice';
import chatReducer from '@/store/slices/chatSlice';
import appReducer from '@/store/slices/appSlice';
import teamReducer from '@/store/slices/teamSlice';
import streamingReducer from '@/store/slices/streamingSlice';
import transparencyReducer, { transparencyRailToggled } from '@/store/slices/transparencySlice';
import ticketReducer from '@/store/slices/ticketSlice';
import progressReducer from '@/store/slices/progressSlice';
import panelDrawerReducer from '@/store/slices/panelDrawerSlice';

/**
 * The surface's heading outline (issue #57).
 *
 * A query for every heading element on the deployed page came back **empty** —
 * not with the wrong levels, with nothing at all — because Fluent's typography
 * components render a generic span unless they are told what element to be. So
 * these assertions read the outline off the rendered surface, which jsdom can
 * see, and are deliberately about *structure* rather than about wording: the
 * empty states and the panel copy are other tickets' to change.
 */

const TEAM = {
    team_id: STORE_ASSISTANT_TEAM_ID,
    name: ASSISTANT_NAME,
    agents: [{ input_key: '', type: '', name: 'ShiftTasksAgent', deployment_name: 'gpt-4.1-mini' }],
    starting_tasks: [
        { id: 'qt-1', name: 'How do I close the store?', prompt: 'How do I close the store?', lane: 'fast' },
    ],
} as any;

/**
 * A reply with the model's own Markdown headings in it. The chat surface has
 * to hold its outline while an agent is talking, and `#` in a reply is where
 * the second top-level heading came from.
 */
const REPLY = {
    agent: 'ShiftTasksAgent',
    agent_type: AgentMessageType.AI_AGENT,
    content: '# Closing the store\n\nCash up the tills.\n\n### Safe drop\n',
} as any;

const PLAN_DATA = {
    plan: { id: 'plan-1', overall_status: 'completed' },
    team: TEAM,
    messages: [REPLY],
    mplan: null,
    streaming_message: null,
    agents: [],
    steps: [],
} as any;

/**
 * The same conversation on the **Deliberate lane**: a `plan_approval_request`
 * has arrived, so there is a plan to review and the rail heads a section for it.
 *
 * The outline has to be asserted for *both* lanes (#78). Making the plan
 * section conditional makes the outline conditional, and an outline test that
 * only ever renders one of the two cases is an outline half-guarded.
 */
const DELIBERATE_PLAN_DATA = {
    ...PLAN_DATA,
    mplan: {
        id: 'mplan-1',
        status: 'awaiting_approval',
        user_request: 'The espresso machine is running cold',
        team: [],
        facts: '',
        steps: [
            { id: 1, action: 'Confirm the fault:', cleanAction: '', agent: 'TroubleshootingAgent' },
            { id: 2, action: 'Raise a service ticket', cleanAction: '', agent: 'EscalationAgent' },
        ],
        context: { task: '', participant_descriptions: {} },
    },
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
            progress: progressReducer,
            panelDrawer: panelDrawerReducer,
        },
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware({ serializableCheck: false }),
    });

/** Every heading the surface exposes, in document order, with its level. */
const outline = (): { level: number; text: string }[] =>
    screen
        .queryAllByRole('heading')
        .map((heading) => ({
            level: Number(heading.tagName.slice(1)),
            text: (heading.textContent ?? '').trim(),
        }));

const levelOf = (element: string): number => Number(element.slice(1));

/**
 * Every place the outline jumps down more than one level, in **document
 * order** — which is the only order that matters. A set of the distinct levels
 * would report `h1, h3, h2` as a clean `[1, 2, 3]`, and that exact sequence is
 * what a model's Markdown heading in a reply used to produce.
 */
const skippedLevels = (): string[] => {
    const jumps: string[] = [];
    let previous = 0;
    for (const heading of outline()) {
        if (heading.level > previous + 1) {
            jumps.push(`h${previous || 0} \u2192 h${heading.level} (${heading.text})`);
        }
        previous = heading.level;
    }
    return jumps;
};

const renderHomeSurface = () =>
    render(
        <Provider store={makeStore()}>
            <MemoryRouter>
                <HomePage />
            </MemoryRouter>
        </Provider>,
    );

const renderChatSurface = () =>
    render(
        <Provider store={makeStore()}>
            <MemoryRouter initialEntries={['/chat/plan-1']}>
                <Routes>
                    <Route path="/chat/:id" element={<ChatPage />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );

beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
    window.appConfig = { API_URL: 'https://backend.example/api' } as never;
    vi.mocked(TeamService.getUserTeams).mockResolvedValue([TEAM]);
    vi.mocked(TeamService.initializeTeam).mockResolvedValue({ success: true } as any);
    vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(PLAN_DATA);
});

describe('the home surface has a heading outline', () => {
    it('offers the transparency-panel disclosure from the content toolbar', async () => {
        renderHomeSurface();

        await waitFor(() => expect(screen.getByText('Quick tasks')).toBeInTheDocument());

        const toggle = screen.getByRole('button', { name: TRANSPARENCY_PANELS_LABEL });
        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        expect(toggle).toHaveAttribute('aria-controls', TRANSPARENCY_RAIL_ID);
    });

    it('exposes exactly one top-level heading, and it names the assistant', async () => {
        renderHomeSurface();

        await waitFor(() => expect(screen.getByText('Quick tasks')).toBeInTheDocument());

        const top = outline().filter((heading) => heading.level === levelOf(SURFACE_HEADING));
        expect(top.map((heading) => heading.text)).toEqual([ASSISTANT_NAME]);
    });

    it('makes the question input and the Quick tasks reachable by heading navigation', async () => {
        renderHomeSurface();

        await waitFor(() => expect(screen.getByText('Quick tasks')).toBeInTheDocument());

        const sections = outline()
            .filter((heading) => heading.level === levelOf(SECTION_HEADING))
            .map((heading) => heading.text);
        expect(sections).toContain('How can I help?');
        expect(sections).toContain('Quick tasks');
    });

    it('makes every transparency panel reachable by heading navigation', async () => {
        // The rail exists so the audience can skim where an answer came from
        // and what it cost. Panel titles rendered as spans take that away from
        // the users who most need structure rather than layout.
        renderHomeSurface();

        await waitFor(() => expect(screen.getByText('Quick tasks')).toBeInTheDocument());

        const sections = outline()
            .filter((heading) => heading.level === levelOf(SECTION_HEADING))
            .map((heading) => heading.text);
        expect(sections).toContain('Agent Team');
        expect(sections).toContain('Grounding');
        expect(sections).toContain('What this cost');
    });

    it('heads who is available under the Agent Team panel, before a question is typed', async () => {
        // #79. The count is a subsection of the panel it counts, so the rail's
        // roster is reachable by heading navigation on this surface too, and
        // the outline still descends without skipping.
        renderHomeSurface();

        await waitFor(() => expect(screen.getByTestId('agent-team-availability')).toBeInTheDocument());

        const heading = screen.getByTestId('agent-team-availability');
        expect(heading.tagName.toLowerCase()).toBe(SUBSECTION_HEADING);
        expect(outline().map((entry) => entry.text)).toContain('1 specialist available');
    });

    it('descends without skipping a level', async () => {
        renderHomeSurface();

        await waitFor(() => expect(screen.getByText('Quick tasks')).toBeInTheDocument());

        expect(outline().length, 'no headings at all; this assertion is inert').toBeGreaterThan(0);
        expect(skippedLevels(), 'the outline jumps a level').toEqual([]);
    });
});

describe('the chat surface has a heading outline', () => {
    // The **Fast lane**: no `plan_approval_request`, so no plan section and no
    // heading for one (#78).
    it('exposes exactly one top-level heading, and it names the assistant', async () => {
        renderChatSurface();

        await waitFor(() => expect(screen.getByTestId('transparency-rail')).toBeInTheDocument());
        await waitFor(() => expect(screen.getByText('Agent Team')).toBeInTheDocument());

        const top = outline().filter((heading) => heading.level === levelOf(SURFACE_HEADING));
        expect(top.map((heading) => heading.text)).toEqual([ASSISTANT_NAME]);
    });

    it('offers the transparency-panel disclosure from the content toolbar', async () => {
        renderChatSurface();

        await waitFor(() => expect(screen.getByTestId('transparency-rail')).toBeInTheDocument());

        const toggle = screen.getByRole('button', { name: TRANSPARENCY_PANELS_LABEL });
        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        expect(toggle).toHaveAttribute('aria-controls', TRANSPARENCY_RAIL_ID);
    });

    it('makes every transparency panel reachable by heading navigation', async () => {
        renderChatSurface();

        await waitFor(() => expect(screen.getByText('Agent Team')).toBeInTheDocument());

        const sections = outline()
            .filter((heading) => heading.level === levelOf(SECTION_HEADING))
            .map((heading) => heading.text);
        expect(sections).toContain('Agent Team');
        expect(sections).toContain('Grounding');
        expect(sections).toContain('What this cost');
    });

    it('heads no plan section, because this request has no plan to review', async () => {
        // A heading a screen-reader user skims to and finds nothing behind is
        // worse than no heading: the section's only content was the statement
        // that it was empty.
        renderChatSurface();

        await waitFor(() => expect(screen.getByText('Agent Team')).toBeInTheDocument());

        const sections = outline()
            .filter((heading) => heading.level === levelOf(SECTION_HEADING))
            .map((heading) => heading.text);
        expect(sections).not.toContain('Plan Overview');
    });

    it('descends without skipping a level', async () => {
        renderChatSurface();

        await waitFor(() => expect(screen.getByText('Agent Team')).toBeInTheDocument());

        expect(outline().length, 'no headings at all; this assertion is inert').toBeGreaterThan(0);
        expect(skippedLevels(), 'the outline jumps a level').toEqual([]);
    });
});

describe('the chat surface has a heading outline with a plan up for review', () => {
    // The **Deliberate lane**. Making the plan section conditional made the
    // outline conditional, so both cases are asserted rather than one of them
    // quietly dropped (#78).
    beforeEach(() => {
        vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(DELIBERATE_PLAN_DATA);
    });

    it('exposes exactly one top-level heading, and it names the assistant', async () => {
        renderChatSurface();

        await waitFor(() => expect(screen.getByText('Plan Overview')).toBeInTheDocument());

        const top = outline().filter((heading) => heading.level === levelOf(SURFACE_HEADING));
        expect(top.map((heading) => heading.text)).toEqual([ASSISTANT_NAME]);
    });

    it('makes the plan and every transparency panel reachable by heading navigation', async () => {
        renderChatSurface();

        await waitFor(() => expect(screen.getByText('Plan Overview')).toBeInTheDocument());

        const sections = outline()
            .filter((heading) => heading.level === levelOf(SECTION_HEADING))
            .map((heading) => heading.text);
        expect(sections).toContain('Plan Overview');
        expect(sections).toContain('Agent Team');
        expect(sections).toContain('Grounding');
        expect(sections).toContain('What this cost');
    });

    it('descends without skipping a level', async () => {
        renderChatSurface();

        await waitFor(() => expect(screen.getByText('Plan Overview')).toBeInTheDocument());

        expect(outline().length, 'no headings at all; this assertion is inert').toBeGreaterThan(0);
        expect(skippedLevels(), 'the outline jumps a level').toEqual([]);
    });
});

describe('the rail heads its panels without heading the surface', () => {
    it('exposes no top-level heading of its own', () => {
        // The rail is on both surfaces. A top-level heading inside it would be
        // a second one on each — and on the chat surface it is rendered inside
        // the panel *beside* the conversation, which is not what the page is
        // about.
        render(
            <Provider store={makeStore()}>
                <TransparencyRail team={TEAM} />
            </Provider>,
        );

        expect(
            outline().filter((heading) => heading.level === levelOf(SURFACE_HEADING)),
        ).toEqual([]);
    });

    it('has an expanded outline and a collapsed outline', () => {
        const store = makeStore();
        render(
            <Provider store={store}>
                <TransparencyRail team={TEAM}>
                    <AgentTeamPanel available={TEAM} availableCount={1} />
                </TransparencyRail>
            </Provider>,
        );

        const sections = () =>
            outline()
                .filter((heading) => heading.level === levelOf(SECTION_HEADING))
                .map((heading) => heading.text);

        expect(sections()).toEqual(['Agent Team', 'Grounding', 'What this cost']);

        act(() => {
            store.dispatch(transparencyRailToggled());
        });

        expect(sections()).toEqual([]);
    });

    it('cannot ship a panel title as a span', () => {
        // Read out of the source rather than listed here: the failure this
        // guards is a *new* panel, and a list of the three that exist today
        // would agree with itself forever. Every component that renders the
        // panel-title class has to take its level from the outline module.
        const TITLE_CLASS = 'transparency-panel__title';

        // The opening tag itself, not the file: an unused import of
        // `SECTION_HEADING` elsewhere in the same module would otherwise let a
        // span through.
        const untitled = sourceFiles().flatMap((path) =>
            Array.from(readFileSync(path, 'utf8').matchAll(/<[^<>]*>/g))
                .map((match) => match[0])
                .filter((tag) => tag.includes(TITLE_CLASS))
                .filter((tag) => !tag.includes('as={SECTION_HEADING}'))
                .map((tag) => `${path}: ${tag.trim()}`),
        );

        expect(untitled, 'renders a panel title that is not a heading').toEqual([]);
        expect(
            sourceFiles().filter((path) => readFileSync(path, 'utf8').includes(TITLE_CLASS)),
            'no component renders a panel title; this assertion is inert',
        ).not.toEqual([]);
    });
});
