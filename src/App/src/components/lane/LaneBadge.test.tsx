import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge, FluentProvider, teamsDarkTheme, teamsLightTheme } from '@fluentui/react-components';
import { Checkmark16Filled } from '@fluentui/react-icons';

import LaneBadge from './LaneBadge';

describe('the Lane, made visible', () => {
    it('names the lane it was given', () => {
        render(<LaneBadge lane="fast" />);

        expect(screen.getByTestId('lane-badge')).toHaveTextContent('Fast lane');
    });

    it('says what the Deliberate lane costs the associate', () => {
        render(<LaneBadge lane="deliberate" variant="taken" />);

        const badge = screen.getByTestId('lane-badge');
        expect(badge).toHaveAttribute('data-lane', 'deliberate');
        expect(badge).toHaveAttribute('data-lane-variant', 'taken');
        expect(badge.getAttribute('title')).toMatch(/approve/i);
    });

    it('claims nothing about the Fast lane beyond the approval step', () => {
        // A Lane decides exactly one thing — whether the plan-review gate is
        // built — so that is the only thing the badge may claim. Two claims it
        // must not make, and one Quick Task falsifies each (#26):
        //
        // * a **latency** claim. Fast-lane latency is still unmeasured, and
        //   ADR-013 makes that measurement the sole trigger for reopening the
        //   orchestrator-bypass question. A tooltip is not the place the number
        //   gets asserted for the first time.
        // * an **answer**. The one-tap boundary probe declares the Fast lane
        //   and is never answered at all — the Identity boundary gate refuses
        //   it above the lane router — so a badge promising a reply is the
        //   surface saying something that is not so on the beat the whole
        //   governance argument turns on.
        render(<LaneBadge lane="fast" />);

        const title = screen.getByTestId('lane-badge').getAttribute('title') ?? '';
        expect(title).toMatch(/approval/i);
        expect(title).not.toMatch(/answer|straight away|second|fast|quick/i);
    });
});

/**
 * The Lane, legible (issue #16).
 *
 * A lane nobody can read is a lane that is not surfaced, and the accelerator's
 * badge was three separate ways of not being read at once: a pill that wrapped
 * outside its own border, the quietest colour pair Fluent draws, and hairline
 * glyphs inside it. The Deliberate lane — the one card on a grid of six whose
 * lane the audience actually has to see — was the least legible of the lot.
 */
describe('the Lane, legible', () => {
    it('never breaks its label across two lines', () => {
        // Fluent's Badge is a fixed `height: 20px` box whose border is an
        // `::after` pinned to that height, so a label allowed to wrap is drawn
        // outside the pill with the border struck through it. Both labels are
        // two words and the card is a grid cell that narrows with the window,
        // so this is the badge's default state and not an edge case: "Fast
        // lane" broke in two on a 1440px screen.
        render(<LaneBadge lane="fast" />);

        expect(getComputedStyle(screen.getByTestId('lane-badge')).whiteSpace).toBe(
            'nowrap',
        );
    });

    it('is never the thing that gives when the card runs out of room', () => {
        // The other half of the same failure. Left shrinkable, the badge is
        // what a narrow grid column takes the width out of — and a pill
        // narrower than its own label is a pill whose label wraps.
        render(<LaneBadge lane="deliberate" />);

        expect(getComputedStyle(screen.getByTestId('lane-badge')).flexShrink).toBe(
            '0',
        );
    });

    it.each([
        ['light', teamsLightTheme],
        ['dark', teamsDarkTheme],
    ])('draws the loudest pair Fluent has in the %s theme', (_name, theme) => {
        // Measured against Fluent's own rendering rather than against a class
        // name copied out of the implementation, for the reason #56 records:
        // colour is the theme's to state, and `filled` is the one appearance
        // Fluent guarantees as an accessible pair in *both* themes. Naming two
        // colours here instead would meet the ratio in the theme its author
        // happened to be looking at and be nobody's guarantee in the other.
        //
        // Compared by what separates two references differing *only* in
        // appearance, so the claim is about the appearance rather than about
        // the size or the icon the badge happens to carry as well.
        const drawn = laneBadgeClasses(theme, <LaneBadge lane="deliberate" />);

        for (const quieter of ['tint', 'outline'] as const) {
            const filledAlone = distinguishes(
                reference(theme, { appearance: 'filled' }),
                reference(theme, { appearance: quieter }),
            );

            expect(filledAlone.length).toBeGreaterThan(0);
            expect(filledAlone.every((c) => drawn.includes(c))).toBe(true);
        }
    });

    it('declares no colour of its own', () => {
        // The opposite failure to the one above, and the one this surface has
        // actually shipped (#56): a colour hardcoded past the theme, meeting
        // its ratio in whichever theme the author happened to be looking at.
        render(<LaneBadge lane="fast" />);

        expect(
            screen.getByTestId('lane-badge').getAttribute('style') ?? '',
        ).not.toMatch(/(^|[;\s])(color|background|border)/);
    });

    it('is louder where it is scanned than where it is read', () => {
        // A declared lane is read down a grid of six cards from across a room,
        // and the whole point of that grid is that five say one thing and one
        // says another. A taken lane sits in the plan toolbar beside the store
        // and the associate, close up, and must not shout over them.
        const largeAlone = distinguishes(
            reference(teamsLightTheme, { size: 'large' }),
            reference(teamsLightTheme, { size: 'medium' }),
        );

        const declared = laneBadgeClasses(
            teamsLightTheme,
            <LaneBadge lane="fast" variant="declared" />,
        );
        const taken = laneBadgeClasses(
            teamsLightTheme,
            <LaneBadge lane="fast" variant="taken" />,
        );

        expect(largeAlone.length).toBeGreaterThan(0);
        expect(largeAlone.every((c) => declared.includes(c))).toBe(true);
        expect(largeAlone.some((c) => taken.includes(c))).toBe(false);
    });
});

/** The classes Fluent puts on the root of `element`'s Lane badge in `theme`. */
const laneBadgeClasses = (
    theme: typeof teamsLightTheme,
    element: React.ReactElement,
): string[] => {
    const { unmount } = render(
        <FluentProvider theme={theme}>{element}</FluentProvider>,
    );
    const classes = Array.from(screen.getByTestId('lane-badge').classList);
    unmount();
    return classes;
};

/**
 * A plain Fluent Badge of the same *shape* — an icon and a label — differing
 * only in the prop under test.
 *
 * The shape matters: Fluent styles an empty badge and a labelled one
 * differently, so a bare reference would put the icon and label classes into
 * every diff and make each comparison a claim about something else.
 */
const reference = (
    theme: typeof teamsLightTheme,
    props: { appearance?: 'filled' | 'tint' | 'outline'; size?: 'medium' | 'large' },
): string[] => {
    const { container, unmount } = render(
        <FluentProvider theme={theme}>
            <Badge
                appearance={props.appearance ?? 'filled'}
                size={props.size ?? 'large'}
                color="warning"
                icon={<Checkmark16Filled />}
            >
                Needs approval
            </Badge>
        </FluentProvider>,
    );
    const classes = Array.from(container.querySelector('.fui-Badge')!.classList);
    unmount();
    return classes;
};

/**
 * What `a` carries that `b` does not — the classes the differing prop bought.
 *
 * Griffel's per-render sequence hash (`___…`) is dropped: it identifies the
 * exact combination of classes on one element, so it never matches across two
 * differently-composed badges and would make every comparison here vacuous.
 * What is left is the atomic classes, which are the styling itself.
 */
const distinguishes = (a: string[], b: string[]): string[] =>
    a.filter((c) => !c.startsWith('___') && !b.includes(c));
