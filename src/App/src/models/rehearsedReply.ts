/**
 * The Rehearsed replies (issue #26).
 *
 * A **Rehearsed reply** is a one-tap answer to a Clarification, authored on the
 * Quick Task that provokes one. Only the troubleshooting beat asks a question
 * back — `TroubleshootingAgent` is instructed to ask what the associate has
 * already tried — and answering it is the one place in the walkthrough the
 * presenter would otherwise have to type.
 *
 * It matters twice over. The clarification seam records that answer as
 * **Attempted steps** (#21), and the **Simulated ticket** the escalation beat
 * raises carries them (#22). A walkthrough where nobody types the answer is a
 * walkthrough whose ticket reads `not reported`.
 *
 * The replies are resolved by matching the plan's `initial_goal` back to a
 * Quick Task's prompt, **not** carried in navigation state. State does not
 * survive a reload, and a presenter reloading mid-beat is exactly when they
 * need the tap — the same reason the lane taken is read back from session
 * state rather than held in the router's `state`.
 *
 * A goal that matches nothing yields nothing, which is what an edited prompt
 * yields: edited text is free-typed input, and it gives up the declared Lane
 * for the same reason. Replies written for one question and offered under
 * another are a tap that answers something nobody asked.
 */

import { TeamConfig } from './Team';

/** How a prompt is compared after its round trip through a text box. */
const comparable = (text: string): string => text.trim().toLowerCase();

/**
 * The rehearsed replies for a plan, or none.
 *
 * @param team The assistant whose Quick Tasks were on offer.
 * @param goal The plan's initial goal, as the backend recorded it.
 */
export const rehearsedRepliesFor = (
    team: TeamConfig | null | undefined,
    goal: string | null | undefined,
): string[] => {
    if (!team || !goal) return [];

    const wanted = comparable(goal);
    const task = (team.starting_tasks ?? []).find(
        (candidate) => comparable(candidate?.prompt ?? '') === wanted,
    );

    return (task?.rehearsed_replies ?? []).filter(
        (reply): reply is string => typeof reply === 'string' && reply.trim() !== '',
    );
};
