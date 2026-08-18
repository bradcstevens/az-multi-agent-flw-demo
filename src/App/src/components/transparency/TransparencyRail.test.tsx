import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';

import {
    allRules,
    allRulesIncludingMediaQueries,
    classesIn,
    classTokensIn,
    isRendered,
    SHELL_STYLESHEET,
    sourceFiles,
    stackedBody,
} from '@/testing/stylesheets';
import {
    DESKTOP_DRAWER_QUERY,
    STACKING_BREAKPOINT_PX,
    TRANSPARENCY_RAIL_TOGGLE_CLASS,
} from '@/models/panelDrawer';

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

const collapsedRailContainers = (): string[] =>
    Array.from(
        new Set(
            allRulesIncludingMediaQueries()
                .flatMap((rule) => classesIn(rule.selector))
                .filter((className) => className.endsWith('--collapsed'))
                .filter(isRendered),
        ),
    );

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

    it('collapses every rendered rail container on desktop and releases it when the shell stacks', () => {
        const containers = collapsedRailContainers();
        expect(containers, 'no rendered rail container has a collapsed state').not.toEqual([]);

        for (const className of containers) {
            // `allRules`, not `allRulesIncludingMediaQueries`: the collapse has
            // to hold at **every** desktop width. Flattened, a `width: 0` inside
            // some other query — a wide-screen rule, a print block — would
            // satisfy this while the rail stayed 320px wide across the band the
            // demonstration is actually given.
            const closesOnDesktop = allRules().some(
                (rule) =>
                    classesIn(rule.selector).includes(className) &&
                    /(?:^|[;\s])width:\s*0/.test(rule.body) &&
                    /min-width:\s*0/.test(rule.body),
            );
            expect(closesOnDesktop, `.${className} does not give its width back on desktop`).toBe(true);

            const stacked = stackedBody(className);
            expect(
                stacked,
                `.${className} keeps its collapsed desktop width below the stacking breakpoint`,
            ).toMatch(/(?:^|[;\s])width:\s*100%/);

            const compactsGap = allRules().some(
                (rule) =>
                    classesIn(rule.selector).includes(className) &&
                    /(?:^|[;\s])gap:\s*0/.test(rule.body),
            );
            if (compactsGap) {
                expect(
                    stacked,
                    `.${className} keeps its collapsed spacing below the stacking breakpoint`,
                ).toMatch(/(?:^|[;\s])gap:\s*12px/);
            }
        }
    });
});

/**
 * The rail as a **Panel drawer** (issue #127, ADR-035).
 *
 * The rail is read *beside* the answer it explains, so closing it returns its
 * width to the conversation rather than covering it. Which makes the drawer a
 * side-column rule like every other one, released at the **Stacking
 * breakpoint** — and below it the rail is always open, so the control that
 * closes it is *absent* rather than disabled.
 *
 * Read out of the stylesheets for #58's reason: the number that releases the
 * drawer is declared in `storeSurface.css`, and a component that unmounts the
 * rail's panels has to be released by the same number or the band between the
 * two is a rail with room and no headings.
 */
describe('the transparency rail is a Panel drawer', () => {
    it('closes at the breakpoint the stylesheet declares, rather than at a second one', () => {
        // The drawer is the first rule about this column that a *component*
        // has to obey as well as a stylesheet, so it is the first chance for
        // the surface to own the number twice.
        //
        // The drawer's query is the stylesheet's, negated, rather than a second
        // query one pixel above it. A viewport is not obliged to be a whole
        // number of pixels — zoom, a fractional device pixel ratio and a
        // scrollbar all produce halves — and at 900.5 both `(max-width: 900px)`
        // and `(min-width: 901px)` are false: three columns of shell around a
        // rail the component had decided could not be closed, with the control
        // that closes it already gone.
        const declared = Array.from(
            readFileSync(SHELL_STYLESHEET, 'utf8').matchAll(/@media\s*\(max-width:\s*(\d+)px\)/g),
            (match) => Number(match[1]),
        );

        expect(
            Array.from(new Set(declared)),
            'the shell stylesheet declares no single stacking breakpoint',
        ).toEqual([STACKING_BREAKPOINT_PX]);
        expect(
            DESKTOP_DRAWER_QUERY,
            'the drawer opens on a band the stacking breakpoint does not release',
        ).toBe(`not all and (max-width: ${STACKING_BREAKPOINT_PX}px)`);
    });

    it("takes the drawer's control away below the breakpoint rather than disabling it", () => {
        // A control for a state that cannot exist is worse than no control: the
        // stacked rail is always open, so a toggle there either lies about what
        // it does or sits inert under the associate's thumb.
        expect(
            stackedBody(TRANSPARENCY_RAIL_TOGGLE_CLASS),
            'the drawer keeps its control on a surface that cannot close the drawer',
        ).toMatch(/display:\s*none/);
    });
});
