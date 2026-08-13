import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

import transparencyReducer from '@/store/slices/transparencySlice';
import ticketReducer from '@/store/slices/ticketSlice';
import { useTransparencySignals } from './useTransparencySignals';

/**
 * A stand-in for the socket: the same `on(type, handler)` contract
 * `WebSocketService` exposes, so the subscription is exercised by the message
 * **type string** the backend actually sends.
 */
const listeners = new Map<string, Set<(message: unknown) => void>>();
const emit = (type: string, data: unknown) =>
    listeners.get(type)?.forEach((handler) => handler({ type, data }));

vi.mock('@/store/WebSocketService', () => ({
    default: {
        on: (type: string, handler: (message: unknown) => void) => {
            if (!listeners.has(type)) listeners.set(type, new Set());
            listeners.get(type)!.add(handler);
            return () => listeners.get(type)!.delete(handler);
        },
    },
}));

const makeStore = () =>
    configureStore({ reducer: { transparency: transparencyReducer, ticket: ticketReducer } });

const Harness = () => {
    useTransparencySignals();
    return null;
};

describe('the transparency subscriptions', () => {
    beforeEach(() => listeners.clear());

    it('lights the Grounding panel on a source_used message', () => {
        const store = makeStore();
        render(
            <Provider store={store}>
                <Harness />
            </Provider>,
        );

        emit('source_used', {
            platform: 'Copilot Studio',
            source: 'Dataverse',
            agent_name: 'Store SOP Assistant',
            citations: [],
        });

        expect(store.getState().transparency.source?.platform).toBe('Copilot Studio');
    });

    it('accumulates the meter on a token_usage message', () => {
        const store = makeStore();
        render(
            <Provider store={store}>
                <Harness />
            </Provider>,
        );

        emit('token_usage', {
            agent_name: 'Shift Tasks Agent',
            executor_id: 'shift_tasks_agent',
            input_tokens: 10,
            output_tokens: 5,
            total_tokens: 15,
        });

        expect(store.getState().transparency.meter.rows[0].totalTokens).toBe(15);
    });

    it('collects a presenter_alert message without touching the meter', () => {
        const store = makeStore();
        render(
            <Provider store={store}>
                <Harness />
            </Provider>,
        );

        emit('presenter_alert', {
            title: 'Shift task due',
            content: 'Coffee station deep clean.',
            timestamp: '2026-08-13T09:00:00+00:00',
        });

        expect(store.getState().transparency.alerts).toHaveLength(1);
        expect(store.getState().transparency.meter.rows).toEqual([]);
    });

    it('unsubscribes when the surface goes away', () => {
        const store = makeStore();
        const { unmount } = render(
            <Provider store={store}>
                <Harness />
            </Provider>,
        );

        unmount();
        emit('token_usage', {
            agent_name: 'Shift Tasks Agent',
            executor_id: 'shift_tasks_agent',
            input_tokens: 10,
            output_tokens: 5,
            total_tokens: 15,
        });

        expect(store.getState().transparency.meter.rows).toEqual([]);
    });
});

describe('the Simulated ticket subscription (issue #22)', () => {
    beforeEach(() => listeners.clear());

    it('holds the ticket the plan approval raised', () => {
        // Exercised by the message **type string** the backend actually sends.
        // The subscription is the one seam where a rename on either side is
        // silent: `WebSocketService` passes unrecognised types through its
        // default branch, so drift here is a card that simply never appears.
        const store = makeStore();
        render(
            <Provider store={store}>
                <Harness />
            </Provider>,
        );

        emit('ticket_raised', {
            ticket_id: 'SIM-223-0041',
            status: 'submitted',
            fields: [{ name: 'steps_attempted', value: 'Fitted a fresh paper filter' }],
        });

        expect(store.getState().ticket.ticket?.ticketId).toBe('SIM-223-0041');
    });

    it('ignores a ticket payload it cannot read', () => {
        const store = makeStore();
        render(
            <Provider store={store}>
                <Harness />
            </Provider>,
        );

        emit('ticket_raised', { ticket_id: '', fields: [] });

        expect(store.getState().ticket.ticket).toBeNull();
    });
});
