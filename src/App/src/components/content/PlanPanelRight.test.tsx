import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import PlanPanelRight from './PlanPanelRight';
import { useTransparencySignals } from '@/hooks/useTransparencySignals';
import transparencyReducer, {
    conversationStarted,
    sourceUsedReceived,
    tokenUsageReceived,
    transparencyRailToggled,
} from '@/store/slices/transparencySlice';
import ticketReducer, { ticketRaised } from '@/store/slices/ticketSlice';
import teamReducer, { setSelectedTeam } from '@/store/slices/teamSlice';
import { NO_ROSTER_MESSAGE } from '@/models/agentAvailability';
import {
    PLAN_PANEL_RIGHT_COLLAPSED_CLASS,
    TRANSPARENCY_RAIL_COLLAPSED_CLASS,
} from '@/models/panelDrawer';
import { SRC } from '@/testing/stylesheets';
import { FakeSocket, frame } from '@/testing/fakeSocket';
import webSocketService from '@/store/WebSocketService';
import { PLAN_ARRIVING } from '@/models/progressNarration';
import progressReducer from '@/store/slices/progressSlice';

const makeStore = () =>
    configureStore({
        reducer: {
            transparency: transparencyReducer,
            ticket: ticketReducer,
            team: teamReducer,
            progress: progressReducer,
        },
        middleware: (getDefaultMiddleware) =>
            getDefaultMiddleware({ serializableCheck: false }),
    });

const planData = {
    plan: { id: 'plan-1' },
    team: {
        agents: [
            { input_key: '', type: '', name: 'ShiftTasksAgent', deployment_name: 'gpt-4.1-mini' },
        ],
    },
    messages: [],
    mplan: null,
    streaming_message: null,
} as any;

const renderPanel = (store = makeStore(), approvalRequest: any = null) =>
    render(
        <Provider store={store}>
            <PlanPanelRight
                planData={planData}
                loading={false}
                planApprovalRequest={approvalRequest}
            />
        </Provider>,
    );

const SocketDrivenPanel = () => {
    useTransparencySignals();
    return <PlanPanelRight planData={planData} loading={false} planApprovalRequest={null} />;
};

const renderSocketDrivenPanel = (store = makeStore()) =>
    render(
        <Provider store={store}>
            <SocketDrivenPanel />
        </Provider>,
    );

async function connectedSocket(): Promise<FakeSocket> {
    const connecting = webSocketService.connect('plan-rail');
    const socket = FakeSocket.latest()!;
    socket.open();
    await connecting;
    return socket;
}

describe('the chat surface with Plan review off', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        webSocketService.disconnect();
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
    });

    afterEach(() => {
        webSocketService.disconnect();
        vi.unstubAllGlobals();
    });

    it('shows the agent roster even though there is no plan to review', () => {
        // The Fast lane produces no plan object at all (ADR-013). The panel
        // used to bail out entirely on that, so the Agent Team was empty for
        // most of the walkthrough.
        renderPanel();

        expect(screen.getByTestId('agent-team-member-ShiftTasksAgent')).toBeInTheDocument();
    });

    it('does not render the plan section at all (#78)', () => {
        // A section whose only content is the statement that it is empty is a
        // heading a screen-reader user skims to and finds nothing behind. The
        // Fast lane never puts a plan up for review — no `plan_approval_request`
        // frame, ADR-023's *Done* phase — so the section is not on screen.
        renderPanel();

        expect(screen.queryByText('Plan Overview')).not.toBeInTheDocument();
        expect(document.querySelector('.plan-section')).toBeNull();
    });

    it('says nothing about a plan rather than promising one that is not coming', () => {
        renderPanel();

        expect(screen.queryByText(/No plan to review/i)).not.toBeInTheDocument();
        expect(screen.queryByText(PLAN_ARRIVING)).not.toBeInTheDocument();
    });

    it('shows the transparency rail, so the panels are reachable in the fast lane', () => {
        renderPanel();

        expect(screen.getByTestId('transparency-rail')).toBeInTheDocument();
        expect(screen.getByTestId('grounding-panel')).toBeInTheDocument();
        expect(screen.getByTestId('token-meter-panel')).toBeInTheDocument();
    });

    it('carries a token_usage signal all the way to the meter, model column included', () => {
        const store = makeStore();
        store.dispatch(
            tokenUsageReceived({
                agent_name: 'Shift Tasks Agent',
                executor_id: 'ShiftTasksAgent',
                input_tokens: 900,
                output_tokens: 100,
                total_tokens: 1000,
            }),
        );

        renderPanel(store);

        const row = screen.getByTestId('meter-row-ShiftTasksAgent');
        expect(row).toHaveTextContent('1,000');
        expect(row).toHaveTextContent('gpt-4.1-mini');
    });

    it('carries a source_used signal all the way to the Grounding panel', () => {
        const store = makeStore();
        store.dispatch(
            sourceUsedReceived({
                platform: 'Copilot Studio',
                source: 'Dataverse',
                agent_name: 'Store SOP Assistant',
                citations: [
                    {
                        position: 1,
                        name: 'SOP-102 Store Closing Procedure.docx',
                        snippet: 'Cash up the tills…',
                        url: null,
                    },
                ],
            }),
        );

        renderPanel(store);

        expect(screen.getByTestId('grounding-platform')).toHaveTextContent('Copilot Studio');
        expect(screen.getByText('SOP-102 Store Closing Procedure.docx')).toBeInTheDocument();
    });

    it('opens the unpinned rail from a Source used frame on the real socket seam', async () => {
        const store = makeStore();
        store.dispatch(transparencyRailToggled());
        store.dispatch(conversationStarted('session-rail'));
        renderSocketDrivenPanel(store);

        expect(screen.getByTestId('transparency-rail')).toHaveClass(
            TRANSPARENCY_RAIL_COLLAPSED_CLASS,
        );

        const socket = await connectedSocket();
        act(() => {
            socket.deliver(
                frame('source_used', {
                    platform: 'Copilot Studio',
                    source: 'Dataverse',
                    agent_name: 'Store SOP Assistant',
                    citations: [],
                }),
            );
        });

        expect(screen.getByTestId('transparency-rail')).not.toHaveClass(
            TRANSPARENCY_RAIL_COLLAPSED_CLASS,
        );
        expect(screen.getByTestId('grounding-platform')).toHaveTextContent('Copilot Studio');
    });

    it('keeps a presenter-pinned rail closed when Source used arrives on the socket', async () => {
        const store = makeStore();
        store.dispatch(transparencyRailToggled());
        renderSocketDrivenPanel(store);

        const socket = await connectedSocket();
        act(() => {
            socket.deliver(
                frame('source_used', {
                    platform: 'Copilot Studio',
                    source: 'Dataverse',
                    agent_name: 'Store SOP Assistant',
                    citations: [],
                }),
            );
        });

        expect(screen.getByTestId('transparency-rail')).toHaveClass(
            TRANSPARENCY_RAIL_COLLAPSED_CLASS,
        );
        expect(store.getState().transparency.source?.platform).toBe('Copilot Studio');
    });
});

describe('the chat surface on the deliberate lane', () => {
    // Removing the early return was meant to stop the Fast lane rendering "No
    // plan available" — not to change the lane that *does* have a plan to
    // review. These pin the path the escalation beat depends on (#22).
    const approvalRequest = {
        steps: [
            { action: 'Confirm the fault:', agent: 'TroubleshootingAgent' },
            { action: 'Raise a service ticket', agent: 'EscalationAgent' },
        ],
        team: { agents: [] },
    } as any;

    it('keeps plan review out of the evidence rail', () => {
        renderPanel(makeStore(), approvalRequest);

        expect(screen.queryByText('Plan Overview')).not.toBeInTheDocument();
        expect(screen.queryByText(/Raise a service ticket/)).not.toBeInTheDocument();
        expect(screen.queryByText(PLAN_ARRIVING)).not.toBeInTheDocument();
    });

    it('still shows the roster and the rail beside the plan', () => {
        renderPanel(makeStore(), approvalRequest);

        expect(screen.getByTestId('agent-team-member-ShiftTasksAgent')).toBeInTheDocument();
        expect(screen.getByTestId('transparency-rail')).toBeInTheDocument();
    });

    it('leaves its own orientation to the stacking breakpoint', () => {
        // This panel is a shell column, and it contains the rail. An inline
        // `width` or `border-left` here beats a media query, so the shared
        // stacking breakpoint would be present, correct and inert for the whole
        // chat surface — the failure #25 already found once on the shell
        // itself, and the reason the rail stacked while its container did not.
        renderPanel();

        const panel = screen.getByTestId('plan-panel-right');
        expect(panel).toHaveClass('plan-panel-right');
        expect(panel.style.width).toBe('');
        expect(panel.style.height).toBe('');
        expect(panel.style.borderLeft).toBe('');
    });
});

describe('the Simulated ticket on the chat surface (issue #22)', () => {
    // The rail is the one surface that survives the stacking breakpoint — #25
    // drops the left panel and keeps this one — and the associate's screen is
    // a phone. A ticket rendered only where a phone cannot reach it is a
    // ticket the person holding the broken equipment never sees.
    const raised = {
        ticket_id: 'SIM-223-0041',
        status: 'submitted',
        fields: [
            { name: 'symptom', value: 'left head runs cold and slow' },
            { name: 'steps_attempted', value: 'Fitted a fresh paper filter' },
        ],
    };

    it('shows nothing until a ticket has actually been raised', () => {
        renderPanel(makeStore());

        expect(screen.queryByTestId('simulated-ticket')).not.toBeInTheDocument();
    });

    it('shows the ticket the approval confirmed', () => {
        const store = makeStore();
        store.dispatch(ticketRaised(raised));

        renderPanel(store);

        expect(screen.getByTestId('simulated-ticket-id')).toHaveTextContent('SIM-223-0041');
        expect(screen.getByText(/Fitted a fresh paper filter/)).toBeInTheDocument();
    });

});

describe('the loading window names the specialists standing by (issue #65)', () => {
    // `PlanPanelRight` is rendered outside `PlanPage`'s `loading || !planData`
    // branch, so this panel is on screen for the whole wait. Sourced only from
    // `planData?.team` it read "No agent roster loaded for this conversation."
    // beside a spinner reading "Initializing AI agents…". The roster was in
    // Redux the entire time.
    const STORE_ASSISTANT = {
        agents: [
            { input_key: '', type: '', name: 'TroubleshootingAgent', deployment_name: 'o4-mini' },
            { input_key: '', type: '', name: 'ShiftTasksAgent', deployment_name: 'gpt-4.1-mini' },
            { input_key: '', type: '', name: 'EscalationAgent' },
        ],
    } as any;

    const renderLoading = (store = makeStore()) =>
        render(
            <Provider store={store}>
                <PlanPanelRight planData={null} loading planApprovalRequest={null} />
            </Provider>,
        );

    it('names the roster the app is already holding, with no help from the wire', () => {
        const store = makeStore();
        store.dispatch(setSelectedTeam(STORE_ASSISTANT));

        renderLoading(store);

        expect(screen.getByTestId('agent-team-member-TroubleshootingAgent')).toBeInTheDocument();
        expect(screen.getByTestId('agent-team-member-ShiftTasksAgent')).toBeInTheDocument();
        expect(screen.getByTestId('agent-team-member-EscalationAgent')).toBeInTheDocument();
    });

    it('counts them in a heading over the names', () => {
        const store = makeStore();
        store.dispatch(setSelectedTeam(STORE_ASSISTANT));

        renderLoading(store);

        expect(screen.getByTestId('agent-team-availability')).toHaveTextContent(
            '3 specialists available',
        );
    });

    it('no longer claims no roster for a team it is holding', () => {
        const store = makeStore();
        store.dispatch(setSelectedTeam(STORE_ASSISTANT));

        renderLoading(store);

        expect(screen.queryByText(NO_ROSTER_MESSAGE)).not.toBeInTheDocument();
    });

    it('still says there is no roster when the app is holding none', () => {
        // A deployment with the store assistant missing is a real state, and
        // #25's whole argument is that the surface says so rather than
        // quietly showing a stranger.
        renderLoading();

        expect(screen.getByTestId('agent-team-empty')).toHaveTextContent(NO_ROSTER_MESSAGE);
    });

    it('claims availability and not that any of them took the question', () => {
        // The boundary probe is refused above the Lane router: three
        // specialists are available and zero participate, which is what the
        // Token meter's measured `0` on that row says.
        const store = makeStore();
        store.dispatch(setSelectedTeam(STORE_ASSISTANT));

        renderLoading(store);

        expect(screen.getByTestId('agent-team-note')).toBeInTheDocument();
        expect(
            screen.queryByText(/identified|assigned|selected|chosen|working on/i),
        ).not.toBeInTheDocument();
    });

    it('takes the count from the roster selector rather than deriving a second one', () => {
        // Read out of the source: `selectTeamAgentCount` has been exported and
        // unused since the slice was written, and a `.length` beside it is a
        // second count to keep in step with the first.
        const source = readFileSync(
            join(SRC, 'components', 'content', 'PlanPanelRight.tsx'),
            'utf8',
        );

        expect(source).toContain('selectTeamAgentCount');
        expect(source, 'recounts the roster beside the selector').not.toMatch(
            /agents\??\.length/,
        );
    });
});

describe('the chat surface wraps the rail, and the drawer closes both (issue #127)', () => {
    // The collapse rule has to name **two** containers. The home surface
    // renders a bare `.transparency-rail`; the chat surface wraps it in
    // `.plan-panel-right`, which declares the column's width there. Name only
    // the rail and this wrapper keeps the width the rail just gave up — a
    // 320px empty column with a left border down it, on the surface the
    // walkthrough spends all its time on.

    it('gives the conversation the wrapper width back when the rail closes', () => {
        const store = makeStore();
        renderPanel(store);

        const wrapper = screen.getByTestId('plan-panel-right');
        expect(wrapper).not.toHaveClass(PLAN_PANEL_RIGHT_COLLAPSED_CLASS);

        act(() => {
            store.dispatch(transparencyRailToggled());
        });

        expect(wrapper).toHaveClass(PLAN_PANEL_RIGHT_COLLAPSED_CLASS);
        expect(screen.getByTestId('transparency-rail')).toHaveClass(
            TRANSPARENCY_RAIL_COLLAPSED_CLASS,
        );
        expect(screen.queryByRole('heading', { name: 'Grounding' })).not.toBeInTheDocument();
    });

    it('takes the Simulated ticket out of the column rather than clipping it away', () => {
        // Everything the collapsed column holds unmounts, not just the rail's
        // panels. A zero-width column with `overflow: hidden` leaves the ticket
        // card invisible to the room and fully present to a screen reader —
        // #78's defect with the two audiences swapped, and this card is the one
        // thing in the column carrying a number somebody would repeat aloud.
        const store = makeStore();
        store.dispatch(
            ticketRaised({
                ticket_id: 'SIM-223-0041',
                status: 'submitted',
                fields: [{ name: 'symptom', value: 'left head runs cold and slow' }],
            }),
        );
        renderPanel(store);
        expect(screen.getByTestId('simulated-ticket')).toBeInTheDocument();

        act(() => {
            store.dispatch(transparencyRailToggled());
        });

        expect(screen.queryByTestId('simulated-ticket')).not.toBeInTheDocument();
    });

    it('obeys the drawer through the rail, rather than deciding a second time', () => {        // Read out of the source, because the failure is two containers that
        // agree today and drift later: a wrapper that reads the slice and the
        // breakpoint for itself is a second answer to *is the drawer open*, and
        // the one that disagrees is the one nobody is looking at.
        const source = readFileSync(
            join(SRC, 'components', 'content', 'PlanPanelRight.tsx'),
            'utf8',
        );

        expect(source).toContain('useTransparencyRailOpen');
        expect(source, 'reads the drawer state a second way').not.toContain(
            'selectTransparencyRailExpanded',
        );
        expect(source, 'reads the breakpoint a second way').not.toContain('useDesktopDrawer');
    });
});
