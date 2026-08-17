/**
 * The **Panel drawer**'s mechanics (issue #127, ADR-035).
 *
 * A drawer is a side-column rule, and every side-column rule on this surface is
 * released at the **Stacking breakpoint**: below it the columns stack, so there
 * is no width beside the conversation to give back and nothing for a drawer to
 * do.
 *
 * The breakpoint itself is declared **once**, in `storeSurface.css`. The rail's
 * drawer is the first rule about that column a *component* has to obey as well
 * as a stylesheet — collapsed means the panels **unmount**, which no media
 * query can do — so the number arrives here as well, and
 * `TransparencyRail.test` reads the stylesheet and fails if the two ever
 * disagree. Two breakpoints that drift apart is #58, and the band between them
 * would be a rail with room and no headings in it.
 */

/** The **Stacking breakpoint**, in pixels, as `storeSurface.css` declares it. */
export const STACKING_BREAKPOINT_PX = 900;

/** The stylesheet's own query, so nothing has to restate the number to use it. */
export const STACKING_BREAKPOINT_QUERY = `(max-width: ${STACKING_BREAKPOINT_PX}px)`;

/**
 * The widths a drawer exists at: the **negation** of the breakpoint, rather
 * than one pixel above it.
 *
 * `(min-width: 901px)` looks like the complement of `(max-width: 900px)` and is
 * not one. A viewport is not obliged to be a whole number of pixels — a zoomed
 * page, a fractional device pixel ratio or a scrollbar's width can all land the
 * surface at 900.5 — and there both queries are false: the shell would still be
 * three columns while the component had decided the drawer no longer exists,
 * leaving a rail nailed open with no control to close it. Negating the one
 * query closes the band by construction.
 */
export const DESKTOP_DRAWER_QUERY = `not all and ${STACKING_BREAKPOINT_QUERY}`;

/**
 * The **Transparency rail**'s element, so its toggle can say what it controls.
 *
 * `aria-controls` needs an id and the rail already carries this name as a class
 * and a test id; a fourth spelling of it would be a reference that silently
 * points at nothing.
 */
export const TRANSPARENCY_RAIL_ID = 'transparency-rail';

/** The class the collapsed rail carries, and the one thing that closes it. */
export const TRANSPARENCY_RAIL_COLLAPSED_CLASS = 'transparency-rail--collapsed';

/** The class the collapsed rail's wrapper carries on the chat surface. */
export const PLAN_PANEL_RIGHT_COLLAPSED_CLASS = 'plan-panel-right--collapsed';

/** The class the drawer's control carries, so the breakpoint can take it away. */
export const TRANSPARENCY_RAIL_TOGGLE_CLASS = 'transparency-rail-toggle';

/** The chat-history drawer's navigation target. */
export const CHAT_HISTORY_DRAWER_ID = 'chat-history-drawer';

/** The desktop-only disclosure class the Stacking breakpoint removes. */
export const CHAT_HISTORY_DRAWER_TOGGLE_CLASS = 'chat-history-drawer-toggle';

/** The disclosure to receive focus after the modal drawer closes. */
export const CHAT_HISTORY_DRAWER_TOGGLE_ID = 'chat-history-drawer-toggle';
