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

import { StartingTask, TeamConfig, TicketStatusReply } from './Team';

/** How a prompt is compared after its round trip through a text box. */
const comparable = (text: string): string => text.trim().toLowerCase();

const taskForGoal = (
    team: TeamConfig | null | undefined,
    goal: string | null | undefined,
): StartingTask | undefined => {
    if (!team || !goal) return undefined;

    const wanted = comparable(goal);
    return (team.starting_tasks ?? []).find(
        (candidate) => comparable(candidate?.prompt ?? '') === wanted,
    );
};

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
    const task = taskForGoal(team, goal);

    return (task?.rehearsed_replies ?? []).filter(
        (reply): reply is string => typeof reply === 'string' && reply.trim() !== '',
    );
};

/** The follow-on task for a plan, or none when it began outside the roster. */
export const followOnTaskFor = (
    team: TeamConfig | null | undefined,
    goal: string | null | undefined,
): StartingTask | undefined => {
    const followOnId = taskForGoal(team, goal)?.follow_on;
    if (!followOnId) return undefined;

    return (team?.starting_tasks ?? []).find((candidate) => candidate.id === followOnId);
};

/** The ticket-status inquiry authored for this Chat's ticketing task, or none. */
export const ticketStatusReplyFor = (
    team: TeamConfig | null | undefined,
    goal: string | null | undefined,
): TicketStatusReply | undefined => {
    const replyFor = (task: StartingTask | undefined): TicketStatusReply | undefined => {
        const reply = task?.ticket_status_reply;
        if (
            !reply
            || typeof reply.prompt !== 'string'
            || !reply.prompt.trim()
            || typeof reply.lane !== 'string'
        ) {
            return undefined;
        }
        return reply;
    };
    const taskReply = replyFor(taskForGoal(team, goal));
    if (taskReply) return taskReply;

    /*
     * A Chat row opens its latest Plan. Once the inquiry itself creates that
     * Plan, its goal is the status prompt rather than the ticketing task. Match
     * that authored prompt among ticketing tasks, so different ticket flows in
     * the same team do not borrow each other's continuation.
     */
    const statusGoalReplies = (team?.starting_tasks ?? [])
        .filter((task) => task.ticket_on_approval === true)
        .map(replyFor)
        .filter(
            (reply): reply is TicketStatusReply =>
                reply !== undefined && comparable(reply.prompt) === comparable(goal ?? ''),
        );
    return statusGoalReplies.length === 1 ? statusGoalReplies[0] : undefined;
};
