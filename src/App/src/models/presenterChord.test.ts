import { describe, it, expect } from 'vitest';

import { PRESENTER_CHORD_LABEL, isPresenterChord } from './presenterChord';

const chord = (over: Partial<KeyboardEvent> = {}) =>
    ({
        code: 'KeyA',
        ctrlKey: true,
        altKey: true,
        shiftKey: true,
        metaKey: false,
        repeat: false,
        getModifierState: () => false,
        ...over,
    }) as KeyboardEvent;

describe('the presenter chord', () => {
    it('fires on all three modifiers plus the key', () => {
        expect(isPresenterChord(chord())).toBe(true);
    });

    it('does not fire on the key alone — the audience is watching this keyboard', () => {
        expect(isPresenterChord(chord({ ctrlKey: false }))).toBe(false);
        expect(isPresenterChord(chord({ altKey: false }))).toBe(false);
        expect(isPresenterChord(chord({ shiftKey: false }))).toBe(false);
    });

    it('does not fire on ordinary typing', () => {
        expect(
            isPresenterChord(
                chord({ ctrlKey: false, altKey: false, shiftKey: false }),
            ),
        ).toBe(false);
    });

    it('does not fire on another key held with the same modifiers', () => {
        expect(isPresenterChord(chord({ code: 'KeyB' }))).toBe(false);
    });

    it('ignores the layout, matching the physical key', () => {
        // Alt+A composes a different character on several layouts, so `key`
        // is not what is matched — a chord that works only on US English is a
        // chord that fails on the borrowed laptop.
        expect(isPresenterChord(chord({ key: 'å' } as Partial<KeyboardEvent>))).toBe(true);
    });

    it('fires once per press, not once per auto-repeat', () => {
        // Holding the chord a beat too long would otherwise POST a stream of
        // alerts, and a stack of identical cards on stage reads as a bug.
        expect(isPresenterChord(chord({ repeat: true }))).toBe(false);
    });

    it('does not fire under AltGr, which many layouts report as Ctrl+Alt', () => {
        // On Windows and several European layouts AltGr sets both ctrlKey and
        // altKey, so Shift+AltGr+A while typing a question would otherwise fire
        // the chord mid-sentence.
        expect(
            isPresenterChord(
                chord({ getModifierState: (key: string) => key === 'AltGraph' } as Partial<KeyboardEvent>),
            ),
        ).toBe(false);
    });

    it('has a label the presenter can be told, and the audience is not', () => {
        expect(PRESENTER_CHORD_LABEL).toMatch(/Ctrl/i);
    });
});
