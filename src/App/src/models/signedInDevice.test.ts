import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
    SIGNED_IN_NAME_KEY,
    forgetSignedInDevice,
    rememberSignedInName,
    signedInName,
    subscribeToSignedInDevice,
} from './signedInDevice';

beforeEach(() => {
    window.sessionStorage.clear();
    forgetSignedInDevice();
});

describe('the signed-in device', () => {
    it('opens anonymous, which is the refusing state', () => {
        expect(signedInName()).toBeNull();
    });

    it('remembers the name the backend returned', () => {
        rememberSignedInName('Tanya Alvarez');

        expect(signedInName()).toBe('Tanya Alvarez');
    });

    it('survives a reload, because the demo is one tap from a reload', () => {
        rememberSignedInName('Tanya Alvarez');

        // What a fresh module instance after a reload would read.
        expect(window.sessionStorage.getItem(SIGNED_IN_NAME_KEY)).toBe('Tanya Alvarez');
    });

    it('is forgotten by signing out', () => {
        rememberSignedInName('Tanya Alvarez');

        forgetSignedInDevice();

        expect(signedInName()).toBeNull();
        expect(window.sessionStorage.getItem(SIGNED_IN_NAME_KEY)).toBeNull();
    });

    it('leaves nothing behind in storage that outlives the tab', () => {
        // `sessionStorage`, deliberately, not `localStorage`. A fresh session is
        // an anonymous shared store device, which is where the demo has to
        // start — and a laptop closed after one rehearsal must open on the
        // refusing state for the next, with nothing to reset by hand.
        rememberSignedInName('Tanya Alvarez');

        expect(window.localStorage.getItem(SIGNED_IN_NAME_KEY)).toBeNull();
        expect(window.localStorage.length).toBe(0);
    });

    it('does not remember a blank name', () => {
        // A sign-in that came back without a name signed nobody in. Recording
        // it would put an empty chip on the header while the gate refuses.
        rememberSignedInName('   ');

        expect(signedInName()).toBeNull();
    });

    it('tells its readers when it changes', () => {
        const listener = vi.fn();
        const unsubscribe = subscribeToSignedInDevice(listener);

        rememberSignedInName('Tanya Alvarez');
        forgetSignedInDevice();
        unsubscribe();
        rememberSignedInName('Tanya Alvarez');

        expect(listener).toHaveBeenCalledTimes(2);
    });

    it('survives storage that refuses to be written', () => {
        // Private browsing throws on write. The header is not worth a blank
        // screen, and an unrecorded sign-in refuses, which is the safe way to
        // be wrong.
        const setItem = vi
            .spyOn(Storage.prototype, 'setItem')
            .mockImplementation(() => {
                throw new Error('nope');
            });

        expect(() => rememberSignedInName('Tanya Alvarez')).not.toThrow();
        expect(signedInName()).toBe('Tanya Alvarez');

        setItem.mockRestore();
    });
});
