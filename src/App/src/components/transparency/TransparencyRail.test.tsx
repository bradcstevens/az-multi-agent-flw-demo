import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';

import {
    allRulesIncludingMediaQueries,
    classesIn,
    classTokensIn,
    isRendered,
    sourceFiles,
    stackedBody,
} from '@/testing/stylesheets';

/**
 * The transparency rail's own box (issue #60).
 *
 * The rail is where the demonstration's argument lives — where the answer came
 * from, and what it cost — and it is read on a phone, on a shared device,
 * mid-shift. A rail that renders wider than it declares is clipped by whatever
 * contains it, and a clipped token meter loses its right-hand end, which is the
 * estimated Copilot Credits column: the exact number the two-billing-models
 * point is made with.
 *
 * Read out of the stylesheets rather than listed here, per #58. jsdom has no
 * layout engine, so the rendered width is not observable in this loop — the
 * rule that produces it is, and a rule asked of the whole stylesheet keeps
 * agreeing with the surface after a rename.
 */

/** A declared length, as opposed to `100%`, `auto` or a keyword. */
const DECLARED_LENGTH = /(?:^|[;\s])width:\s*\d+px/;
const DECLARES_PADDING = /(?:^|[;\s])padding(?:-left|-right|-inline)?:\s*\d/;

/** The class the rail carries, and the one thing allowed to declare its width. */
const RAIL = 'transparency-rail';

/**
 * Every class rendered by a component that also renders the rail — the boxes
 * the rail shares a column with, derived from the source rather than listed.
 */
const railColumnClasses = (): string[] => {
    const hosts = sourceFiles().filter((path) => readFileSync(path, 'utf8').includes('TransparencyRail'));
    const rendered = hosts.flatMap((path) => Array.from(classTokensIn(readFileSync(path, 'utf8'))));
    return Array.from(
        new Set(
            allRulesIncludingMediaQueries()
                .flatMap((rule) => classesIn(rule.selector))
                .filter((className) => className !== RAIL)
                .filter((className) => rendered.includes(className)),
        ),
    );
};

describe('the transparency rail fits its own box', () => {
    it('renders the width it declares, padding included', () => {
        // A content-box column is its declared width *plus* its padding, so
        // every width in the stylesheet is a number the surface never uses. On
        // the chat surface that difference is clipped away silently by the
        // container; on a phone it is cut off the right-hand edge.
        const misdeclared = allRulesIncludingMediaQueries()
            .filter((rule) => DECLARED_LENGTH.test(rule.body) && DECLARES_PADDING.test(rule.body))
            .filter((rule) => !/box-sizing:\s*border-box/.test(rule.body))
            .flatMap((rule) =>
                classesIn(rule.selector).map((className) => ({ file: rule.file, className })),
            )
            .filter(({ className }) => isRendered(className));

        expect(
            misdeclared.map(({ file, className }) => `.${className} (${file})`),
            'padded, fixed-width and content-box: renders wider than it declares',
        ).toEqual([]);
    });

    it('is the only box in its column that declares a width', () => {
        // The panel and the rail both declared one — 280px and 320px, forty
        // pixels apart before either one's padding — so one of them was always
        // wrong and the outer one clipped the difference away. Whichever number
        // is right, there can only be one of it, or the two drift again the way
        // the two stacking breakpoints did in #58.
        const rivals = railColumnClasses().filter((className) =>
            allRulesIncludingMediaQueries().some(
                (rule) =>
                    classesIn(rule.selector).includes(className) && DECLARED_LENGTH.test(rule.body),
            ),
        );

        expect(
            rivals,
            'declares a width of its own in the column the rail already sizes',
        ).toEqual([]);
    });

    it('lets every other box in its column break below the width it sets', () => {
        // The panel takes the rail's number instead of declaring a second one,
        // which means the column is sized from its content — so anything in it
        // that cannot break is a box that can widen the column past the rail.
        // The plan's words come from a model: one unbroken 120-character URL
        // measured the panel out from 321px to 335px, and a string with nothing
        // to break at would take it much further, pushing the rail off the
        // side. Derived from the stylesheet — a rule that holds words is one
        // that sets a font size — because a list here would not have named the
        // next panel somebody adds.
        const sized = allRulesIncludingMediaQueries().filter((rule) =>
            /width:\s*min-content/.test(rule.body),
        );
        expect(sized, 'no column is sized from its content; this test is inert').not.toEqual([]);

        const columnSheets = new Set(sized.map((rule) => rule.file));
        const breaks = new Set(
            allRulesIncludingMediaQueries()
                .filter((rule) => /overflow-wrap:\s*(?:anywhere|break-word)/.test(rule.body))
                .flatMap((rule) => classesIn(rule.selector)),
        );

        const unbreakable = Array.from(
            new Set(
                allRulesIncludingMediaQueries()
                    .filter((rule) => columnSheets.has(rule.file))
                    .filter((rule) => /font-size:/.test(rule.body))
                    .flatMap((rule) => classesIn(rule.selector)),
            ),
        )
            .filter((className) => isRendered(className))
            .filter((className) => !breaks.has(className));

        expect(
            unbreakable,
            'holds words it cannot break, in the column the rail is supposed to size',
        ).toEqual([]);
    });

    it('holds no scroll region of its own once the page stacks', () => {
        // Stacked, the surface scrolls as one. A box inside it that keeps a
        // `max-height` or an `overflow` of its own is a scroll window nested in
        // an already-scrolling page — measured at 320px, `.plan-section` held
        // 456px of plan in 382px of box, and the rail held six times its own
        // height, so the Grounding panel and the Token meter were in practice
        // invisible on a phone. `.plan-section` takes its cap from a
        // `(max-width: 1920px) and (max-height: 1080px)` query, which a phone
        // matches, which is why the cap is not visible where the rail is.
        const nested = [RAIL, ...railColumnClasses()].filter((className) => {
            const constrains = allRulesIncludingMediaQueries().some(
                (rule) =>
                    classesIn(rule.selector).includes(className) &&
                    (/max-height:\s*\d/.test(rule.body) ||
                        /overflow(?:-x|-y)?:\s*(?:auto|scroll|hidden)/.test(rule.body)),
            );
            if (!constrains) return false;

            const stacked = stackedBody(className);
            return !(
                /max-height:\s*none/.test(stacked) && /overflow:\s*visible/.test(stacked)
            );
        });

        expect(
            nested,
            'still a scroll region of its own inside the stacked, already-scrolling page',
        ).toEqual([]);
    });
});
