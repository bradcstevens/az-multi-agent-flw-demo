import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/apiService', () => ({
    apiService: { createPlan: vi.fn(), signIn: vi.fn() },
}));

import { TaskService } from './TaskService';
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
});
