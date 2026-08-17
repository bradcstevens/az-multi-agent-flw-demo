/**
 * What the store surface claims about itself (issue #25).
 *
 * One module, because the claim has to be the same everywhere it is made: the
 * left panel's toolbar, the conversation's header, the browser tab and the
 * identity chip are four places to disagree about which assistant this is, and
 * a demo that calls itself two things in one screenshot has already lost the
 * argument it exists to make.
 *
 * The rule the transparency surfaces run on (#23, #24) applies here to
 * *identity*: **a surface may say nothing, but it may not say something that is
 * not so.** That is why `selectStoreAssistant` recognises rather than guesses.
 */

import { TeamConfig } from './Team';

/** The assistant, named. */
export const ASSISTANT_NAME = 'Circle K Frontline Store Assistant';

/** The short form, for places too narrow for the full name. */
export const ASSISTANT_SHORT_NAME = 'Frontline Store Assistant';

/** The store the shared device belongs to. Fictional — see `SIMULATED_LABEL`. */
export const STORE_LABEL = 'Store 223';

/**
 * The store assistant's team identifier.
 *
 * Hex-only, per the content pack rules, and `223` reads as the store. The
 * stock packs hold `…0001` through `…0007`; this one is deliberately outside
 * that run so a renumbering upstream cannot collide with it. Issue #19 authors
 * the pack under this identifier.
 */
export const STORE_ASSISTANT_TEAM_ID = '00000000-0000-0000-0000-000000000223';

/** What the surface says when nobody has signed in. */
export const ANONYMOUS_IDENTITY_LABEL = 'No user signed in';

/** The label every simulated element carries. */
export const SIMULATED_LABEL = 'Simulated';

/**
 * The **Transparency rail**'s disclosure control, named (ADR-035).
 *
 * A **Panel drawer**'s toggle is a disclosure button: one static accessible
 * name, plus `aria-expanded` and `aria-controls` for the state and the target.
 * Never a label flipping between *Show* and *Hide* — a control that renames
 * itself under a screen reader is a second control, and the associate has to
 * relearn it every time they use it.
 */
export const TRANSPARENCY_PANELS_LABEL = 'Transparency panels';

/** The rail's one state description when the presenter has pinned it closed. */
export const TRANSPARENCY_RAIL_PINNED_CLOSED_DESCRIPTION = 'Pinned closed for this conversation.';

/**
 * The one assistant, resolved out of whatever the backend returned.
 *
 * Recognition, not position. A store surface with **no** assistant is a demo
 * that cannot run and says so; a store surface showing the accelerator's HR
 * Onboarding roster under the Circle K header is a demo that lies quietly and
 * gets believed. So there is no `teams[0]` fallback — that fallback *is* the
 * stock content packs failing to be suppressed.
 *
 * Two ways to be recognised, because the pack is uploaded by a script and
 * re-uploaded by hand: its identifier, and failing that its name.
 */
export function selectStoreAssistant(
    teams: TeamConfig[] | null | undefined,
): TeamConfig | null {
    const candidates = teams ?? [];

    const byId = candidates.find((team) => team?.team_id === STORE_ASSISTANT_TEAM_ID);
    if (byId) return byId;

    const byName = candidates.find(
        (team) => team?.name?.trim().toLowerCase() === ASSISTANT_NAME.toLowerCase(),
    );
    return byName ?? null;
}
