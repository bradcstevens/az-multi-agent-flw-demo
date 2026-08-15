import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/apiService', () => ({
    apiService: { createPlan: vi.fn(), signIn: vi.fn() },
}));

import { TaskService } from './TaskService';
import { PlanStatus } from '../models/enums';
import type { Plan } from '../models';
import { apiService } from '../api/apiService';
import {
    forgetSignedInDevice,
    rememberSignedInName,
    signedInName,
} from '../models/signedInDevice';

const createPlan = vi.mocked(apiService.createPlan);
const signIn = vi.mocked(apiService.signIn);

beforeEach(() => {
    window.sessionStorage.clear();
    forgetSignedInDevice();
    createPlan.mockReset().mockResolvedValue({ plan_id: 'plan-1' } as any);
    signIn.mockReset().mockResolvedValue({
        session_id: 'sid',
        identity: { display_name: 'Tanya Alvarez' },
    } as any);
});

describe('the mocked sign-in', () => {
    it('takes the associate name from the backend, never from the browser', async () => {
        // The name the header shows and the name the Associate record is keyed
        // by would otherwise be two strings in two languages, free to drift.
        const name = await TaskService.signInDevice();

        expect(name).toBe('Tanya Alvarez');
        expect(signedInName()).toBe('Tanya Alvarez');
    });

    it('writes the identity into server-side session state', async () => {
        await TaskService.signInDevice();

        expect(signIn).toHaveBeenCalledTimes(1);
        expect(signIn.mock.calls[0][0]).toMatch(/^sid_/);
    });

    it('signs nobody in when the sign-in fails', async () => {
        // A device that believes it is signed in while the gate refuses is the
        // header claiming something that is not so.
        signIn.mockRejectedValue(new Error('unreachable'));

        await expect(TaskService.signInDevice()).resolves.toBeNull();
        expect(signedInName()).toBeNull();
    });

    it('signs nobody in when the sign-in names nobody', async () => {
        signIn.mockResolvedValue({ session_id: 'sid', identity: null } as any);

        await expect(TaskService.signInDevice()).resolves.toBeNull();
        expect(signedInName()).toBeNull();
    });
});

describe('creating a plan on a signed-in device', () => {
    it('signs the request its own session in before asking', async () => {
        // Every request carries a fresh session, because a session is one
        // conversation — one **Simulated ticket**, one **Lane** taken. So the
        // identity is materialised into each new session as it is created,
        // rather than by re-using one session for the whole tab.
        rememberSignedInName('Tanya Alvarez');

        await TaskService.createPlan('how much PTO do I have?');

        expect(signIn).toHaveBeenCalledTimes(1);
        expect(signIn.mock.calls[0][0]).toBe(createPlan.mock.calls[0][0].session_id);
    });

    it('signs the session in before the request that the gate reads it for', async () => {
        rememberSignedInName('Tanya Alvarez');
        const order: string[] = [];
        signIn.mockImplementation(async () => {
            order.push('sign_in');
            return { session_id: 'sid', identity: { display_name: 'T' } } as any;
        });
        createPlan.mockImplementation(async () => {
            order.push('process_request');
            return { plan_id: 'plan-1' } as any;
        });

        await TaskService.createPlan('how much PTO do I have?');

        expect(order).toEqual(['sign_in', 'process_request']);
    });

    it('asks anonymously while nobody is signed in', async () => {
        // The demo's opening state, and the one the walkthrough spends five of
        // its six beats in.
        await TaskService.createPlan('how do I close the store?');

        expect(signIn).not.toHaveBeenCalled();
    });

    it('falls back to anonymous when the session cannot be signed in', async () => {
        // Fails closed, like the gate: the request goes anonymous and is
        // refused, and the header returns to matching it.
        rememberSignedInName('Tanya Alvarez');
        signIn.mockRejectedValue(new Error('unreachable'));

        await TaskService.createPlan('how much PTO do I have?');

        expect(createPlan).toHaveBeenCalled();
        expect(signedInName()).toBeNull();
    });

    it('keeps a follow-on task in the conversation session it follows', async () => {
        await TaskService.createPlan(
            'I have tried everything and I need someone to come out.',
            'team-223',
            'deliberate',
            'session-223-troubleshooting',
        );

        expect(createPlan).toHaveBeenCalledWith({
            session_id: 'session-223-troubleshooting',
            description: 'I have tried everything and I need someone to come out.',
            team_id: 'team-223',
            lane: 'deliberate',
        });
    });

    it('carries the authored ticket requirement into the escalation request', async () => {
        await TaskService.createPlan(
            'I have tried everything and I need someone to come out.',
            'team-223',
            'deliberate',
            'session-223-troubleshooting',
            'task-223-escalation',
        );

        expect(createPlan).toHaveBeenCalledWith({
            session_id: 'session-223-troubleshooting',
            description: 'I have tried everything and I need someone to come out.',
            team_id: 'team-223',
            lane: 'deliberate',
            starting_task_id: 'task-223-escalation',
        });
    });
});

describe('a chat is a session, so the list has one row per session', () => {
    // ADR-024 made the escalation continue the troubleshooting turn's session,
    // so beats 3 and 4 of the walkthrough are two Plans sharing one
    // `session_id`. ADR-025 says the surface groups them as one Chat.
    const troubleshooting = {
        id: 'plan-troubleshooting',
        session_id: 'session-shared',
        timestamp: '2026-08-14T09:00:00Z',
        initial_goal: 'The coffee machine is showing an error',
        overall_status: PlanStatus.COMPLETED,
    } as unknown as Plan;

    const escalation = {
        id: 'plan-escalation',
        session_id: 'session-shared',
        timestamp: '2026-08-14T09:20:00Z',
        initial_goal: "I can't fix it",
        overall_status: PlanStatus.COMPLETED,
    } as unknown as Plan;

    it('renders the troubleshooting turn and its escalation as one chat', () => {
        const { completed } = TaskService.transformPlansToChats([
            troubleshooting,
            escalation,
        ]);

        expect(completed).toHaveLength(1);
        expect(completed[0].id).toBe('session-shared');
    });

    it('names the chat for what the conversation was about, not where it got to', () => {
        // Newest-first, which is the order a history endpoint hands them back:
        // the name must come from the turn that opened the conversation, so it
        // cannot be read off the array.
        const { completed } = TaskService.transformPlansToChats([
            escalation,
            troubleshooting,
        ]);

        expect(completed[0].name).toBe('The coffee machine is showing an error');
    });

    it('opens the latest plan, so the escalation is what the row reaches', () => {
        const { completed } = TaskService.transformPlansToChats([
            escalation,
            troubleshooting,
        ]);

        expect(completed[0].planId).toBe('plan-escalation');
    });

    it('keeps the order the history gave when a plan carries a timestamp it cannot read', () => {
        // An unreadable timestamp is not comparable with a readable one, so a
        // comparator that falls back to array order for those pairs and to
        // time for the rest disagrees with itself: for a group ordered
        // [10:00, 09:00, unreadable] it holds a > b, b < c and a < c at once,
        // and which plan names the row then depends on the engine's sort. One
        // unreadable timestamp therefore hands the whole chat back in the
        // order the history gave it.
        const unreadable = {
            ...escalation,
            id: 'plan-unreadable',
            timestamp: 'not a date',
        } as unknown as Plan;

        const { completed } = TaskService.transformPlansToChats([
            escalation,
            troubleshooting,
            unreadable,
        ]);

        expect(completed[0].name).toBe("I can't fix it");
        expect(completed[0].planId).toBe('plan-unreadable');
    });

    it('lets the rest of the history render when one record carries no readable date', () => {
        // `Intl.DateTimeFormat.format` throws on an unreadable timestamp, and
        // it is called while building every row — so one malformed record took
        // the whole panel with it rather than its own date.
        const undated = {
            ...troubleshooting,
            id: 'plan-undated',
            session_id: 'session-undated',
            timestamp: '',
            initial_goal: 'How do I close the store?',
        } as unknown as Plan;

        const { completed } = TaskService.transformPlansToChats([
            undated,
            troubleshooting,
            escalation,
        ]);

        expect(completed.map((chat) => chat.name)).toEqual([
            'How do I close the store?',
            'The coffee machine is showing an error',
        ]);
        expect(completed[0].date).toBeUndefined();
        expect(completed[1].date).toBeTruthy();
    });

    it('keeps separate conversations as separate rows', () => {
        const otherSession = {
            ...troubleshooting,
            id: 'plan-other',
            session_id: 'session-other',
            initial_goal: 'How do I close the store?',
        } as unknown as Plan;

        const { completed } = TaskService.transformPlansToChats([
            troubleshooting,
            escalation,
            otherSession,
        ]);

        expect(completed.map((chat) => chat.id)).toEqual([
            'session-shared',
            'session-other',
        ]);
    });
});
