import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
    HIDDEN_COMPLETED_TASKS_KEY,
    HIDE_COMPLETED_LABEL,
    forgetHiddenCompletedTasks,
    hiddenCompletedTaskIds,
    hideCompletedTasks,
    subscribeToHiddenCompletedTasks,
} from './hiddenCompletedTasks';

beforeEach(() => {
    window.sessionStorage.clear();
    forgetHiddenCompletedTasks();
});

/**
 * A fresh module instance reading whatever storage holds — which is what a
 * reload in the same tab actually is. The in-memory copy cannot stand in for
 * it: it is the thing under test on the other side of a refresh.
 */
const afterAReload = async () => {
    vi.resetModules();
    return import('./hiddenCompletedTasks');
};

describe('the hidden completed tasks', () => {
    it('opens with the whole history showing', () => {
        expect(hiddenCompletedTaskIds().size).toBe(0);
    });

    it('hides the ids it was given', () => {
        hideCompletedTasks(['plan-1', 'plan-2']);

        expect(hiddenCompletedTaskIds().has('plan-1')).toBe(true);
        expect(hiddenCompletedTaskIds().has('plan-2')).toBe(true);
    });

    it('is a set of ids and not a flag, so a later task is not hidden by an earlier clear', () => {
        // "Stay hidden until I unhide" is a different feature and deliberately
        // not this one: a task that completes *after* a clear still appears.
        hideCompletedTasks(['plan-1']);

        expect(hiddenCompletedTaskIds().has('plan-2')).toBe(false);
    });

    it('adds to what is already hidden rather than replacing it', () => {
        hideCompletedTasks(['plan-1']);
        hideCompletedTasks(['plan-2']);

        expect(hiddenCompletedTaskIds().has('plan-1')).toBe(true);
        expect(hiddenCompletedTaskIds().has('plan-2')).toBe(true);
    });

    it('survives a reload, because the clear has to hold across one', () => {
        hideCompletedTasks(['plan-1', 'plan-2']);

        // What a fresh module instance after a reload would read.
        expect(
            JSON.parse(window.sessionStorage.getItem(HIDDEN_COMPLETED_TASKS_KEY) ?? 'null'),
        ).toEqual(['plan-1', 'plan-2']);
    });

    it('leaves nothing behind that outlives the tab', () => {
        // `sessionStorage`, following the Signed-in device precedent: a fresh
        // tab is a fresh demonstration with the whole history back.
        hideCompletedTasks(['plan-1']);

        expect(window.localStorage.getItem(HIDDEN_COMPLETED_TASKS_KEY)).toBeNull();
        expect(window.localStorage.length).toBe(0);
    });

    it('keeps one snapshot identity while nothing changes, for the hook that reads it', () => {
        hideCompletedTasks(['plan-1']);

        expect(hiddenCompletedTaskIds()).toBe(hiddenCompletedTaskIds());
    });

    it('does not announce or re-snapshot when nothing new was hidden', () => {
        hideCompletedTasks(['plan-1']);
        const before = hiddenCompletedTaskIds();
        const listener = vi.fn();
        subscribeToHiddenCompletedTasks(listener);

        hideCompletedTasks(['plan-1']);
        hideCompletedTasks([]);

        expect(listener).not.toHaveBeenCalled();
        expect(hiddenCompletedTaskIds()).toBe(before);
    });

    it('tells its readers when it changes', () => {
        const listener = vi.fn();
        const unsubscribe = subscribeToHiddenCompletedTasks(listener);

        hideCompletedTasks(['plan-1']);
        forgetHiddenCompletedTasks();
        unsubscribe();
        hideCompletedTasks(['plan-2']);

        expect(listener).toHaveBeenCalledTimes(2);
    });

    it('survives storage that refuses to be written', () => {
        // Private browsing throws on write. A clear that cannot outlive a
        // reload is a small loss; a panel that throws is the demonstration.
        const setItem = vi
            .spyOn(Storage.prototype, 'setItem')
            .mockImplementation(() => {
                throw new Error('nope');
            });

        expect(() => hideCompletedTasks(['plan-1'])).not.toThrow();
        expect(hiddenCompletedTaskIds().has('plan-1')).toBe(true);

        setItem.mockRestore();
    });

    it('reads back what the tab hid before the reload', async () => {
        window.sessionStorage.setItem(
            HIDDEN_COMPLETED_TASKS_KEY,
            JSON.stringify(['plan-1', 'plan-2']),
        );

        expect([...(await afterAReload()).hiddenCompletedTaskIds()]).toEqual([
            'plan-1',
            'plan-2',
        ]);
    });

    it('survives a stored value that is not a list of ids', async () => {
        // This key is one `JSON.parse` away from a blank panel.
        window.sessionStorage.setItem(HIDDEN_COMPLETED_TASKS_KEY, '{oops');
        const reloaded = await afterAReload();

        expect(() => reloaded.hiddenCompletedTaskIds()).not.toThrow();
        expect(reloaded.hiddenCompletedTaskIds().size).toBe(0);
    });

    it('ignores stored entries that are not usable ids', async () => {
        window.sessionStorage.setItem(
            HIDDEN_COMPLETED_TASKS_KEY,
            JSON.stringify(['plan-1', '', '   ', 7, null]),
        );

        expect([...(await afterAReload()).hiddenCompletedTaskIds()]).toEqual(['plan-1']);
    });
});

describe('the words the control uses', () => {
    it('says it hides, because the record survives', () => {
        // ADR-022. A label saying *delete* over a record that is still in
        // Cosmos is the surface saying something that is not so.
        expect(HIDE_COMPLETED_LABEL.toLowerCase()).toContain('hide');
    });

    it('never claims to delete, clear, remove or archive anything', () => {
        expect(HIDE_COMPLETED_LABEL.toLowerCase()).not.toMatch(
            /delete|remove|clear|archive|erase/,
        );
    });
});
