/**
 * The store the application actually runs on.
 *
 * Every other suite on this surface builds its own store out of the reducers it
 * needs, which is what makes them readable — and which means not one of them can
 * see a reducer that never reached the real store. A slice that imports a module
 * which imports the `@/store` barrel is a cycle: `store.ts` is evaluated while
 * that slice is still mid-evaluation, its default export is `undefined`, and
 * `combineReducers` drops the key. The console says so once, at startup, and
 * every test stays green.
 *
 * That is not hypothetical. `progressSlice` reaches `agentIconUtils` through
 * `progressNarration` to resolve an executor's display name, and
 * `agentIconUtils` imported `TaskService` from the barrel — so the **Progress
 * narration** slice was absent from the running store while its own 16 tests
 * passed, and the surface would have narrated nothing at all.
 *
 * The import order below is load-bearing: a slice is imported *before* the
 * store, because that is the order the application's own module graph takes and
 * the only order in which the fault appears.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { join } from 'path';

import './slices/progressSlice';
import { store } from './store';

/** The reducer keys `store.ts` claims, read out of its own `reducer: { … }`. */
const claimedReducerKeys = (): string[] => {
    const source = readFileSync(join(__dirname, 'store.ts'), 'utf-8');
    const block = source.match(/reducer:\s*\{([\s\S]*?)\n {4}\}/);
    if (!block) throw new Error('store.ts no longer declares a `reducer: { … }` block');
    return [...block[1].matchAll(/^\s*(\w+):\s*\w+,/gm)].map((m) => m[1]);
};

describe('the store the application runs on', () => {
    it('carries every reducer it claims, even when a slice is imported first', () => {
        const claimed = claimedReducerKeys();
        expect(claimed).toContain('progress');

        const present = Object.keys(store.getState());
        expect(present).toEqual(expect.arrayContaining(claimed));
    });

    it('has the Progress narration slice, which reaches the store through a util', () => {
        expect(store.getState().progress).toBeDefined();
        expect(store.getState().progress.phase).toBe('idle');
    });
});
