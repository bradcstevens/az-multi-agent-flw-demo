/**
 * Who the Agent Team panel says is **available** (issue #65).
 *
 * The loading window used to tell the audience two contradictory things at
 * once. `PlanPanelRight` renders outside `PlanPage`'s `loading || !planData`
 * branch, so the Agent Team panel is on screen for the whole wait — sourced
 * from `planData?.team`, which is `null` until the fetch returns. It therefore
 * rendered its honest empty state, *"No agent roster loaded for this
 * conversation."*, two inches from a spinner reading *"Initializing AI
 * agents…"*. One of those was wrong, and it was not the panel.
 *
 * Nothing was missing. The **store assistant roster** has been in Redux since
 * `HomePage`'s mount, well before the presenter finishes typing, so the window
 * can say something true with no dependency on the wire at all.
 *
 * The distinction this module exists to keep is **available versus
 * participating** (`CONTEXT.md`). The roster says who *could* answer; the
 * stream says who *did*, one agent at a time, in the **Progress narration**.
 * On the boundary-probe beat the **Identity boundary gate** refuses above the
 * **Lane router** and the number that participate is **zero** — which is
 * exactly why the **Token meter** renders a real `0` on that row. "3 agents
 * identified" over that beat contradicts the panel directly beneath it, and
 * this surface's whole discipline is that it may say nothing but may not say
 * something that is not so.
 */

import { Agent, TeamConfig } from './Team';
import { rosterAgents } from './roster';

/** Where the names on the panel came from. */
export type AvailabilitySource =
    /** This conversation's own roster — the plan fetch has returned. */
    | 'conversation'
    /** The selected team, known before the question was even asked. */
    | 'roster'
    /** Neither. A real state, and the panel says so. */
    | 'none';

export interface AgentAvailability {
    /** The specialists to name, in roster order. */
    agents: Agent[];
    /** How many. Shown as a heading *over* the names, never instead of them. */
    count: number;
    source: AvailabilitySource;
}

/**
 * The specialists available to this conversation, conversation roster first.
 *
 * Order matters. The plan fetch's `team` is this conversation's own roster and
 * wins whenever it is present — a historical plan opened from the task list
 * may have run on a different team, and the team the tab happens to hold is
 * not a claim about it. `selectedTeam` fills the window before it arrives, and
 * that window is most of what the audience is looking at.
 *
 * `selectedCount` is passed rather than derived: `selectTeamAgentCount` is the
 * roster's count, and a second one computed here is a second thing to disagree
 * with it.
 */
export function resolveAvailability(
    conversationTeam: TeamConfig | null | undefined,
    planTeam: string[] | null | undefined,
    selectedTeam: TeamConfig | null | undefined,
    selectedCount: number,
): AgentAvailability {
    const conversation = rosterAgents(conversationTeam, planTeam);
    if (conversation.length > 0) {
        return { agents: conversation, count: conversation.length, source: 'conversation' };
    }

    const selected = selectedTeam?.agents ?? [];
    if (selected.length > 0) {
        return { agents: selected, count: selectedCount, source: 'roster' };
    }

    return { agents: [], count: 0, source: 'none' };
}

/**
 * The heading over the names.
 *
 * *Available*, and nothing stronger. "Identified", "assigned" and "selected"
 * all say the question was routed to these three, which no event in this
 * system reports and which is false on the beat where the gate refuses first.
 */
export function availabilityHeading(count: number): string {
    return `${count} specialist${count === 1 ? '' : 's'} available`;
}

/** The line under the heading that keeps the two claims apart in words. */
export const AVAILABILITY_NOTE =
    'Available to answer. Which of them take this question is named as each one responds.';

/** What the panel says when it genuinely knows of no roster. */
export const NO_ROSTER_MESSAGE = 'No agent roster loaded for this conversation.';
