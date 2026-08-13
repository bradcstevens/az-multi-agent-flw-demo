/**
 * The hidden chord that fires the Presenter alert (issue #24, R8).
 *
 * The control has to be **invisible and unguessable**, because the audience is
 * looking at the same screen: a visible "send alert" button turns a
 * demonstration of a proactive assistant into a demonstration of a button. So
 * there is no affordance anywhere in the UI, and the only way in is a chord the
 * presenter was told about.
 *
 * Three modifiers, so it cannot be produced by typing a question, and matched
 * on `code` rather than `key`, so it is the *physical* key that matters — with
 * Alt held, several keyboard layouts compose a different character entirely,
 * and a chord that only works on US English is a chord that fails on the
 * borrowed laptop.
 *
 * `metaKey` must be **up**: Cmd-shaped combinations belong to the operating
 * system, and a chord that also fires under Cmd is a chord that fires while the
 * presenter is doing something else. `AltGraph` must be up for the mirror-image
 * reason: on Windows and several European layouts AltGr *is* reported as
 * Ctrl+Alt, so without this a presenter typing an ordinary accented character
 * into the question box fires the chord mid-sentence.
 *
 * An **auto-repeat** is not a press. Holding the chord a beat too long would
 * otherwise POST an alert every repeat interval, and a stack of identical cards
 * on stage reads as a bug rather than a beat.
 */

const CHORD_CODE = 'KeyA';

/** How the chord is written down for the presenter, and nowhere on screen. */
export const PRESENTER_CHORD_LABEL = 'Ctrl + Alt + Shift + A';

export function isPresenterChord(event: KeyboardEvent): boolean {
    return (
        event.code === CHORD_CODE &&
        event.ctrlKey &&
        event.altKey &&
        event.shiftKey &&
        !event.metaKey &&
        !event.repeat &&
        !event.getModifierState?.('AltGraph')
    );
}
