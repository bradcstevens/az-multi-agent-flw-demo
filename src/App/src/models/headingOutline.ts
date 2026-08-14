/**
 * The surface's **heading outline** (issue #57).
 *
 * Fluent's typography presets render a `<span>` unless they are told what
 * element to be, so every title on both surfaces — the assistant's name, "How
 * can I help?", "Quick tasks", "Plan Overview", and each transparency panel —
 * was a styled span and the whole surface was one undifferentiated run of text.
 * Heading navigation is how a screen-reader user skims a page; here it landed
 * on nothing. WCAG 2.1 Level A, 1.3.1.
 *
 * It costs this surface more than most. The **transparency rail**'s whole job
 * is to be skimmed — the audience is meant to see where an answer came from and
 * what it cost without reading every word — and the panel titles are what make
 * it skimmable. Rendering them as spans takes the rail's argument away from
 * exactly the users who most need it stated in structure rather than in layout.
 *
 * Two levels, declared here rather than chosen per component, on the
 * `storeSurface.ts` precedent: a level picked beside each title is a level that
 * drifts, and a heading outline that skips a level is the defect this fixes in
 * a different form.
 *
 * The **surface heading** is the assistant's name in the conversation's header
 * (`ContentToolbar`). The left panel's toolbar says the same name, and cannot
 * be the page's heading: it is dropped at the **Stacking breakpoint**, and a
 * heading the associate's phone never renders is not an outline.
 */

/** The one top-level heading a surface may expose. */
export const SURFACE_HEADING = 'h1';

/**
 * A section of a surface: the question input, the Quick tasks, the plan
 * overview, and every transparency panel. One level below the surface's own,
 * so the outline descends without skipping.
 */
export const SECTION_HEADING = 'h2';
