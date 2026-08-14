import {
    createDarkTheme,
    createLightTheme,
    type BrandVariants,
    type Theme,
} from '@fluentui/react-components';

/**
 * The store assistant's own theme.
 *
 * This surface used to ship Fluent's `teamsLightTheme` / `teamsDarkTheme`, whose
 * brand ramp is Microsoft Teams' violet. That was wrong twice over: it is the
 * default every Fluent demonstration wears, so the surface read as a framework
 * sample rather than as a product; and it collided semantically, because the one
 * badge on the Quick Tasks grid that has to be told apart from the other five —
 * the Deliberate lane's **Needs approval** — is drawn in Fluent's marigold, and
 * violet against marigold is a muddy pair to scan from the back of a room.
 *
 * The accent here is a deep petrol. It is a single accent, deliberately: one
 * hue for every affordance the associate can act on, and nothing else competing
 * for the same attention.
 *
 * Two properties are load-bearing rather than decorative:
 *
 * * **It is the complement of the warning colour.** Petrol against marigold is
 *   the widest separation the palette can offer, and the Quick Tasks grid is
 *   read as "five say one thing, one says another" — from a distance, by an
 *   audience, in the single beat the lane argument gets. The badge earns that
 *   contrast from the theme rather than by hardcoding a colour, which is what
 *   #56 established and what `LaneBadge` and `SendControl` both have tests for.
 * * **Every step is in gamut and the text-bearing ones are measured.** The ramp
 *   is generated in OKLCH so the steps are perceptually even rather than evenly
 *   spaced in sRGB, then clamped to what each lightness can actually hold — an
 *   unclamped pale step clips to an electric cyan. The four steps Fluent puts
 *   text on or in are checked against their real backgrounds in `storeTheme.test.ts`;
 *   see the mapping recorded there.
 *
 * Nothing here decides what the surface *says*. Colour is the theme's to state
 * and the theme's alone — a component that names a colour of its own is the
 * failure this file exists to make unnecessary.
 */
const petrol: BrandVariants = {
    10: '#011a1c',
    20: '#042a2c',
    30: '#093a3e',
    40: '#0e494d',
    50: '#13575c',
    60: '#176469',
    70: '#1b7076',
    80: '#207e85',
    90: '#269098',
    100: '#41a1a8',
    110: '#60b0b7',
    120: '#7dc0c5',
    130: '#98d0d4',
    140: '#b3dfe3',
    150: '#cdedf0',
    160: '#e6f8f9',
};

/**
 * Geist, self-hosted.
 *
 * A variable font, and bundled rather than fetched: this surface is served from
 * a container to a shared device in a store, and a webfont that arrives from a
 * CDN is a webfont that does not arrive when the store's network is what it
 * usually is. The stack falls back to the system's own UI face, so a failed
 * load costs character rather than legibility.
 *
 * The full 100–900 axis is available, which is what lets the type ramp below
 * use Medium and SemiBold as real steps instead of jumping Regular to Bold.
 */
const SANS = "'Geist Variable', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif";

/**
 * Geist Mono, for figures as well as for code.
 *
 * `fontFamilyNumeric` is the token the Token meter's columns resolve through,
 * and that table is the demonstration's cost argument: tokens and estimated
 * Copilot Credits, read down two columns and compared row against row. In a
 * proportional face those columns do not line up, and a reader comparing a
 * refused request's measured zero against a request that cost something is
 * comparing ragged digits. A monospaced face makes the comparison a glance.
 */
const MONO = "'Geist Mono Variable', ui-monospace, 'SF Mono', Consolas, monospace";

/**
 * Shadows tinted with the palette's own hue.
 *
 * Fluent's defaults are pure black at low opacity, which over a tinted surface
 * reads as grey dirt rather than as shade. These carry the petrol hue, so the
 * elevation looks lit rather than smudged, and they are cast consistently
 * downward — one light source, above.
 */
const tintedShadows = (opacity: [number, number]): Record<string, string> => {
    const [ambient, direct] = opacity;
    const rgb = '13, 42, 46';
    return {
        shadow2: `0 0 2px rgba(${rgb}, ${ambient}), 0 1px 2px rgba(${rgb}, ${direct})`,
        shadow4: `0 0 2px rgba(${rgb}, ${ambient}), 0 2px 4px rgba(${rgb}, ${direct})`,
        shadow8: `0 0 2px rgba(${rgb}, ${ambient}), 0 4px 8px rgba(${rgb}, ${direct})`,
        shadow16: `0 0 2px rgba(${rgb}, ${ambient}), 0 8px 16px rgba(${rgb}, ${direct})`,
        shadow28: `0 0 8px rgba(${rgb}, ${ambient}), 0 14px 28px rgba(${rgb}, ${direct})`,
        shadow64: `0 0 8px rgba(${rgb}, ${ambient}), 0 32px 64px rgba(${rgb}, ${direct})`,
    };
};

/**
 * The type ramp, retuned.
 *
 * Fluent's display sizes are set at the same optical tracking as its body
 * sizes, which leaves a headline looking loose and weightless at 24px and
 * above. Large type wants negative tracking and tighter leading; small type
 * wants the opposite. Only the display end is touched here — the body sizes are
 * read on a phone, mid-shift, and are already tuned for that.
 */
const typography = {
    fontFamilyBase: SANS,
    fontFamilyMonospace: MONO,
    fontFamilyNumeric: MONO,
    lineHeightHero700: '34px',
    lineHeightHero800: '38px',
    lineHeightHero900: '48px',
};

const shared = (base: Theme): Theme => ({
    ...base,
    ...typography,
    // A tighter radius inside than out: Fluent ships the same 4px at every
    // scale, which makes a 16px-padded card and the control inside it look like
    // the same object drawn twice.
    borderRadiusMedium: '6px',
    borderRadiusLarge: '10px',
    borderRadiusXLarge: '14px',
});

export const storeLightTheme: Theme = {
    ...shared(createLightTheme(petrol)),
    ...tintedShadows([0.1, 0.12]),
};

export const storeDarkTheme: Theme = {
    ...shared(createDarkTheme(petrol)),
    // Heavier on a dark canvas, where a shadow at light-theme opacity is
    // invisible and the elevation it was carrying is simply lost.
    ...tintedShadows([0.28, 0.32]),
};

/** The ramp itself, exported so tests can measure the steps Fluent puts text on. */
export const brandRamp = petrol;
