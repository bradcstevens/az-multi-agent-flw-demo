import { describe, it, expect } from 'vitest';
import progressReducer, {
    agentResponding,
    requestRouted,
    planOpened,
    requestSent,
    requestSettled,
    socketConnected,
    selectProgressNarration,
    selectRequestPhase,
} from './progressSlice';
import type { RootState } from '../store';
import { planApprovalAccepted } from './planSlice';

const initial = () => progressReducer(undefined, { type: '@@INIT' });

const after = (...actions: Array<{ type: string; payload?: unknown }>) =>
    actions.reduce((state, action) => progressReducer(state, action as never), initial());

const asRoot = (progress: ReturnType<typeof initial>) => ({ progress }) as RootState;

describe('the phase a request is in', () => {
    it('says nothing before anything has been asked', () => {
        expect(selectRequestPhase(asRoot(initial()))).toBe('idle');
        expect(selectProgressNarration(asRoot(initial()))).toBeNull();
    });

    it('enters Sent when the POST goes out', () => {
        const state = after(requestSent());
        expect(selectRequestPhase(asRoot(state))).toBe('sent');
        expect(selectProgressNarration(asRoot(state))).toBe('Sending your question...');
    });

    it('announces the lane the router decided', () => {
        const state = after(requestSent(), requestRouted({ lane: 'fast', planId: 'plan-1' }));
        expect(selectProgressNarration(asRoot(state))).toBe('Routed — Fast lane');
    });

    it('says nothing new when the socket connects, because connecting is plumbing', () => {
        const state = after(
            requestSent(),
            requestRouted({ lane: 'fast', planId: 'plan-1' }),
            socketConnected(),
        );
        expect(selectRequestPhase(asRoot(state))).toBe('connected');
        expect(selectProgressNarration(asRoot(state))).toBe('Routed — Fast lane');
    });

    it('names the agent that is responding', () => {
        const state = after(requestSent(), agentResponding('Troubleshooting Agent'));
        expect(selectProgressNarration(asRoot(state))).toBe(
            'Troubleshooting Agent is responding...',
        );
    });

    it('stops narrating once the request has settled', () => {
        const state = after(requestSent(), agentResponding('Shift Tasks Agent'), requestSettled());
        expect(selectRequestPhase(asRoot(state))).toBe('done');
        expect(selectProgressNarration(asRoot(state))).toBeNull();
    });
});

describe('the phase only ever advances', () => {
    it('does not run back to Routed when a reconnect reports the socket again', () => {
        const state = after(
            requestSent(),
            requestRouted({ lane: 'fast', planId: 'plan-1' }),
            agentResponding('Shift Tasks Agent'),
            socketConnected(),
        );
        expect(selectRequestPhase(asRoot(state))).toBe('working');
        expect(selectProgressNarration(asRoot(state))).toBe('Shift Tasks Agent is responding...');
    });

    it('does not start narrating again after the answer has arrived', () => {
        const state = after(
            requestSent(),
            requestSettled(),
            agentResponding('Shift Tasks Agent'),
            socketConnected(),
        );
        expect(selectRequestPhase(asRoot(state))).toBe('done');
        expect(selectProgressNarration(asRoot(state))).toBeNull();
    });

    it('names the agent that spoke most recently while it is still working', () => {
        const state = after(
            requestSent(),
            agentResponding('Shift Tasks Agent'),
            agentResponding('Troubleshooting Agent'),
        );
        expect(selectProgressNarration(asRoot(state))).toBe(
            'Troubleshooting Agent is responding...',
        );
    });

    it('starts over on the next question, which is a new request and not a step back', () => {
        const state = after(
            requestSent(),
            agentResponding('Shift Tasks Agent'),
            requestSettled(),
            requestSent('plan-1'),
        );
        expect(selectRequestPhase(asRoot(state))).toBe('sent');
        expect(selectProgressNarration(asRoot(state))).toBe('Sending your question...');
    });

    it('starts over when the associate approves the plan, which puts a POST in flight', () => {
        // The Deliberate lane's second half. Read off `planApprovalAccepted`
        // itself rather than dispatched beside it: an approval that narrated
        // only when the plan page remembered to say so is two places to
        // disagree about whether a request is in flight.
        //
        // It holds the lane — the last thing a signal reported — until an agent
        // speaks. Nothing has told the surface anything newer, and "Executing
        // your plan..." would be a stage nothing emits.
        const state = after(
            requestSent(),
            requestRouted({ lane: 'deliberate', planId: 'plan-1' }),
            requestSettled(),
            planApprovalAccepted(),
        );
        expect(selectRequestPhase(asRoot(state))).toBe('sent');
        expect(selectProgressNarration(asRoot(state))).toBe('Routed — Needs approval');
    });

    it('keeps the plan an approved request belongs to', () => {
        const state = after(
            requestSent(),
            requestRouted({ lane: 'deliberate', planId: 'plan-1' }),
            requestSettled(),
            planApprovalAccepted(),
            planOpened('plan-1'),
        );
        expect(selectRequestPhase(asRoot(state))).toBe('sent');
    });
});

describe('the plan the narration belongs to', () => {
    it('survives the navigation the request itself made', () => {
        const state = after(
            requestSent(),
            requestRouted({ lane: 'deliberate', planId: 'plan-1' }),
            planOpened('plan-1'),
        );
        expect(selectProgressNarration(asRoot(state))).toBe('Routed — Needs approval');
    });

    it('does not follow the presenter to somebody else\'s conversation', () => {
        // Opening an earlier task from the left panel while a request is in
        // flight. "Shift Tasks Agent is responding..." over a conversation that
        // finished last week is the surface saying something that is not so.
        const state = after(
            requestSent(),
            requestRouted({ lane: 'fast', planId: 'plan-1' }),
            agentResponding('Shift Tasks Agent'),
            planOpened('plan-2'),
        );
        expect(selectRequestPhase(asRoot(state))).toBe('idle');
        expect(selectProgressNarration(asRoot(state))).toBeNull();
    });

    it('says nothing on a reload, which has no signal of its own to report', () => {
        expect(selectProgressNarration(asRoot(after(planOpened('plan-1'))))).toBeNull();
    });

    it('survives the navigation even though the response reported no lane', () => {
        // The router failing to name a lane must not also lose the plan the
        // request is for: the narration would then be reset by the very
        // navigation it caused, and the surface would fall silent on a request
        // that is still in flight.
        const state = after(
            requestSent(),
            requestRouted({ lane: null, planId: 'plan-1' }),
            planOpened('plan-1'),
        );
        expect(selectRequestPhase(asRoot(state))).toBe('routed');
        expect(selectProgressNarration(asRoot(state))).toBe('Sending your question...');
    });
});
