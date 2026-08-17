import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

vi.mock('@/api/apiService', () => {
    const apiService = {
        getPlans: vi.fn(),
        endChatTurn: vi.fn(),
        getSessionState: vi.fn(async () => ({})),
        getChatTicket: vi.fn(async () => null),
        approvePlan: vi.fn(),
    };
    return { apiService, APIService: vi.fn(() => apiService) };
});

vi.mock('../store/PlanDataService', async (importOriginal) => {
    const actual = await importOriginal<typeof import('../store/PlanDataService')>();
    class StubbedPlanDataService extends actual.PlanDataService {
        static fetchPlanData = vi.fn();
    }
    return { PlanDataService: StubbedPlanDataService };
});

vi.mock('../components/content/PlanPanelRight', () => ({ default: () => null }));

import ChatPage from './ChatPage';
import { apiService } from '@/api/apiService';
import { PlanDataService } from '../store/PlanDataService';
import planReducer from '../store/slices/planSlice';
import chatReducer from '../store/slices/chatSlice';
import appReducer from '../store/slices/appSlice';
import teamReducer from '../store/slices/teamSlice';
import streamingReducer from '../store/slices/streamingSlice';
import transparencyReducer from '../store/slices/transparencySlice';
import ticketReducer from '../store/slices/ticketSlice';
import progressReducer from '../store/slices/progressSlice';
import webSocketService from '../store/WebSocketService';
import { FakeSocket, frame } from '../testing/fakeSocket';
import { PlanStatus, ProcessedPlanData } from '../models';
import { HttpError } from '../api/httpClient';

const PLAN_DATA = {
    plan: {
        id: 'plan-troubleshooting',
        data_type: 'plan',
        initial_goal: 'The coffee brewer is down.',
        session_id: 'session-223',
        timestamp: '2026-08-17T10:00:00Z',
        plan_id: 'plan-troubleshooting',
        user_id: 'user-223',
        overall_status: PlanStatus.IN_PROGRESS,
    },
    team: null,
    messages: [],
    mplan: null,
    streaming_message: null,
} as unknown as ProcessedPlanData;

const OTHER_PLAN = {
    ...PLAN_DATA.plan,
    id: 'plan-other',
    plan_id: 'plan-other',
    session_id: 'session-other',
    initial_goal: 'The freezer needs a new filter.',
};

const renderLeavingChat = (initialPath = '/chat/plan-troubleshooting') =>
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
            <MemoryRouter initialEntries={[initialPath]}>
                <Routes>
                    <Route path="/" element={<div>New chat</div>} />
                    <Route path="/chat/:id" element={<ChatPage />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );

const openInFlightSocket = async () => {
    const socket = await waitFor(() => {
        const opened = FakeSocket.forPlan('plan-troubleshooting').at(-1);
        expect(opened).toBeTruthy();
        return opened!;
    });
    act(() => {
        socket.open();
        socket.deliver(
            frame('agent_message_streaming', {
                plan_id: 'plan-troubleshooting',
                agent: 'Store operations agent',
                content: 'Checking the equipment record.',
            }),
        );
    });
};

describe('leaving a chat', () => {
    beforeEach(() => {
        FakeSocket.instances = [];
        vi.stubGlobal('WebSocket', FakeSocket);
        window.appConfig = { API_URL: 'https://backend.example/api' } as never;
        vi.mocked(PlanDataService.fetchPlanData).mockResolvedValue(PLAN_DATA);
        vi.mocked(apiService.getPlans).mockResolvedValue([
            PLAN_DATA.plan,
            OTHER_PLAN,
        ] as never);
        vi.mocked(apiService.endChatTurn).mockReset().mockResolvedValue({
            status: 'ended',
            session_id: 'session-223',
            cancelled: true,
        });
    });

    afterEach(() => {
        webSocketService.disconnect();
    });

    it.each([
        ['New chat', () => screen.getByRole('button', { name: 'New chat' })],
        [
            'another chat row',
            () =>
                screen.getByRole('button', {
                    name: /^The freezer needs a new filter/,
                }),
        ],
        ['the logo', () => screen.getByTestId('store-assistant-logo')],
    ])(
        'ends the displayed turn once when the associate chooses %s',
        async (_, trigger) => {
            renderLeavingChat();
            await screen.findByRole('button', {
                name: /^The freezer needs a new filter/,
            });
            await openInFlightSocket();

            fireEvent.click(trigger());

            await waitFor(() =>
                expect(apiService.endChatTurn).toHaveBeenCalledWith('session-223'),
            );
            expect(apiService.endChatTurn).toHaveBeenCalledTimes(1);
            expect(
                screen.queryByText(/the plan process will be stopped/i),
            ).not.toBeInTheDocument();
        },
    );

    it('does not end the turn when the socket drops', async () => {
        renderLeavingChat();
        await screen.findByRole('button', {
            name: /^The freezer needs a new filter/,
        });
        await openInFlightSocket();

        act(() => {
            FakeSocket.latest()!.onclose?.({ code: 1006 });
        });

        expect(apiService.endChatTurn).not.toHaveBeenCalled();
    });

    it('does not leave when the associate selects the chat already open', async () => {
        renderLeavingChat();
        await screen.findByRole('button', {
            name: /^The coffee brewer is down/,
        });
        await openInFlightSocket();

        fireEvent.click(
            screen.getByRole('button', { name: /^The coffee brewer is down/ }),
        );

        expect(apiService.endChatTurn).not.toHaveBeenCalled();
    });

    it('resolves the session before leaving while the initial plan read is pending', async () => {
        let settleInitialRead: (data: ProcessedPlanData) => void;
        vi.mocked(PlanDataService.fetchPlanData)
            .mockReset()
            .mockImplementationOnce(
                () =>
                    new Promise((resolve) => {
                        settleInitialRead = resolve;
                    }),
            )
            .mockResolvedValueOnce(PLAN_DATA);

        renderLeavingChat();
        fireEvent.click(await screen.findByRole('button', { name: 'New chat' }));

        await waitFor(() =>
            expect(apiService.endChatTurn).toHaveBeenCalledWith('session-223'),
        );
        settleInitialRead!(PLAN_DATA);
    });

    it('leaves a Chat route whose Plan record no longer exists', async () => {
        vi.mocked(PlanDataService.fetchPlanData).mockRejectedValue(
            new HttpError('Plan not found', 404),
        );

        renderLeavingChat();
        fireEvent.click(await screen.findByRole('button', { name: 'New chat' }));

        expect(await screen.findByText('New chat')).toBeInTheDocument();
        expect(apiService.endChatTurn).not.toHaveBeenCalled();
    });
});
