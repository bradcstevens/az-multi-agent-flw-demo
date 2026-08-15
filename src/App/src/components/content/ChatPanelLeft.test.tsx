import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

vi.mock('@/api', () => ({
    apiService: { getPlans: vi.fn().mockResolvedValue([]) },
}));

import ChatPanelLeft from './ChatPanelLeft';
import appReducer from '../../store/slices/appSlice';
import { ASSISTANT_NAME } from '../../models/storeSurface';
import { apiService } from '@/api';
import { PlanStatus } from '../../models/enums';
import { forgetHiddenCompletedTasks } from '../../models/hiddenCompletedTasks';
import type { Plan } from '../../models';

const renderPanel = (props: Record<string, unknown> = {}) =>
    render(
        <Provider store={configureStore({ reducer: { app: appReducer } })}>
            <MemoryRouter>
                <ChatPanelLeft
                    reloadChats={false}
                    onNewChatButton={() => undefined}
                    {...props}
                />
            </MemoryRouter>
        </Provider>,
    );

describe('the store surface has one assistant', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('is branded as the store assistant, not as the accelerator', async () => {
        renderPanel();

        expect(await screen.findByText(ASSISTANT_NAME)).toBeInTheDocument();
        expect(screen.queryByText(/contoso/i)).not.toBeInTheDocument();
    });

    it('offers no team picker, because the associate has no basis for the choice', async () => {
        // Routing between specialists is the orchestrator's job and the lane
        // router's job. Asking an associate mid-shift to pick a team makes a
        // decision they cannot make into a precondition of getting an answer.
        renderPanel();

        await waitFor(() => {
            expect(screen.queryByText(/current team/i)).not.toBeInTheDocument();
        });
        expect(screen.queryByRole('button', { name: /team/i })).not.toBeInTheDocument();
        expect(screen.queryByText(/select a team/i)).not.toBeInTheDocument();
    });

    it('offers no team upload either — a picker with one entry is still a picker', async () => {
        renderPanel();

        await screen.findByText(ASSISTANT_NAME);
        expect(screen.queryByText(/upload/i)).not.toBeInTheDocument();
    });
});


/*
  The walkthrough's centrepiece pair. ADR-024 has the escalation continue the
  troubleshooting turn's session, so these are two Plans and — per ADR-025 —
  one Chat.
*/
const TROUBLESHOOTING = {
    id: 'plan-troubleshooting',
    session_id: 'session-shared',
    timestamp: '2026-08-14T09:00:00Z',
    initial_goal: 'The coffee machine is showing an error',
    overall_status: PlanStatus.COMPLETED,
} as unknown as Plan;

const ESCALATION = {
    id: 'plan-escalation',
    session_id: 'session-shared',
    timestamp: '2026-08-14T09:20:00Z',
    initial_goal: "I can't fix it",
    overall_status: PlanStatus.COMPLETED,
} as unknown as Plan;

const HereIs = () => <span data-testid="here">{useLocation().pathname}</span>;

const renderPanelAt = (path: string) =>
    render(
        <Provider store={configureStore({ reducer: { app: appReducer } })}>
            <MemoryRouter initialEntries={[path]}>
                <HereIs />
                <Routes>
                    <Route
                        path="/chat/:id"
                        element={
                            <ChatPanelLeft
                                reloadChats={false}
                                onNewChatButton={() => undefined}
                            />
                        }
                    />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );

describe('one chat is one row', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        window.sessionStorage.clear();
        forgetHiddenCompletedTasks();
        vi.mocked(apiService.getPlans).mockResolvedValue([
            TROUBLESHOOTING,
            ESCALATION,
        ] as never);
    });

    it('renders the troubleshooting turn and its escalation as a single row', async () => {
        // Before #71 this rendered two rows carrying one `session_id` — and so
        // one React key — at the moment the demonstration makes its strongest
        // claim.
        const duplicateKeys = vi.spyOn(console, 'error').mockImplementation(() => undefined);

        renderPanelAt('/chat/plan-troubleshooting');

        expect(
            await screen.findByRole('button', { name: /coffee machine/i }),
        ).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /can't fix it/i })).not.toBeInTheDocument();
        expect(
            duplicateKeys.mock.calls.some((call) => String(call[0]).includes('same key')),
        ).toBe(false);

        duplicateKeys.mockRestore();
    });

    it('opens the chat where the conversation got to, so the escalation is reachable', async () => {
        renderPanelAt('/chat/plan-troubleshooting');

        fireEvent.click(await screen.findByRole('button', { name: /coffee machine/i }));

        await waitFor(() =>
            expect(screen.getByTestId('here')).toHaveTextContent('/chat/plan-escalation'),
        );
    });

    it('highlights the chat that is open, escalation included', async () => {
        renderPanelAt('/chat/plan-escalation');

        const row = await screen.findByRole('button', { name: /coffee machine/i });
        expect(row).toHaveClass('active');
    });

    it('highlights nothing when the open plan belongs to another chat', async () => {
        renderPanelAt('/chat/plan-somewhere-else');

        const row = await screen.findByRole('button', { name: /coffee machine/i });
        expect(row).not.toHaveClass('active');
    });
});
