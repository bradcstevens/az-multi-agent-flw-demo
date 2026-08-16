/*
 * PROTOTYPE — throwaway. Not production code. See issue #85.
 *
 * The one part of this prototype worth keeping. Everything else on this route
 * is a page that will be deleted; this module is the shape the answer takes.
 *
 * The question it exists to answer: **what does a plan worth approving look
 * like** — and, the part ADR-028 explicitly handed here, **what does a step
 * assigned to a person look like**, given `MStep` carries `agent` and `action`
 * and nothing in the system today can say "this one is waiting on a human".
 *
 * Pure. No DOM, no React, no imports. Lifts out as-is.
 */

/* ------------------------------------------------------------------ *
 * Who a step is assigned to
 * ------------------------------------------------------------------ */

/**
 * The answer to ADR-028's deferred question.
 *
 * A step assigned to a person is not an agent step with a different badge. It
 * is a different *kind* of step: the system cannot perform it, only ask for it,
 * and then wait. That distinction is the whole reason a plan is worth
 * approving — the associate is authorising work that will reach other people.
 *
 * `relation` is deliberately not a free string. Spec 4's shift swap needs
 * exactly three: the associate approving their own request, the peer they
 * named, and the manager who signs it off.
 */
export type Assignee =
    | { kind: 'agent'; name: string }
    | {
          kind: 'person';
          name: string;
          relation: 'associate' | 'peer' | 'manager';
          /** Invented for the walkthrough rather than read from a system. */
          simulated: boolean;
      };

export interface ProposedStep {
    id: number;
    /** What will be done, in the associate's words. */
    action: string;
    assignee: Assignee;
    /**
     * The step this one cannot begin before. A plan whose human steps have an
     * order is a plan an associate can actually check: "Marcus is asked before
     * Dana is" is a claim they can agree or disagree with.
     */
    waitsOn?: number;
}

export interface ProposedPlan {
    /** The request in the associate's own words. */
    request: string;
    /** Which revision the associate is looking at. First review is 1. */
    revision: number;
    steps: ProposedStep[];
    /** What the associate said when they sent the previous revision back. */
    revisedBecause?: string;
}

/* ------------------------------------------------------------------ *
 * What the associate can do with it
 * ------------------------------------------------------------------ */

/**
 * Approve, or send back with feedback.
 *
 * There is no third door, and that is the finding from #98: the framework's
 * binary is `approve()` versus `revise(feedback)`, and `revise` folds the
 * feedback into the chat history, replans and re-issues the review **on the
 * same run**. This repository never calls it — today's "reject" deletes the
 * plan and raises `RuntimeError` (#84). So "reject" is not modelled here at
 * all: the brief asked for "a new plan generated with accompanying questions",
 * which is `revise`, not a dead end.
 *
 * Leaving the conversation is still possible, but it is navigation, not a
 * verdict on the plan, and it does not belong in this union.
 */
export type ReviewAction =
    | { type: 'approve' }
    | { type: 'revise'; feedback: string };

export type ReviewStatus = 'awaiting-review' | 'approved';

export interface ReviewState {
    status: ReviewStatus;
    plan: ProposedPlan;
    /** Every revision the associate has already sent back, oldest first. */
    history: string[];
}

/**
 * The suggested replies offered alongside the free-text box.
 *
 * Authored against the plan in front of the associate rather than generated,
 * which is the same discipline the **Rehearsed reply** chips are held to. A
 * suggestion that cannot be checked is a suggestion that can put words in the
 * associate's mouth on stage.
 */
export function revisionSuggestions(plan: ProposedPlan): string[] {
    const suggestions: string[] = [];
    const peer = plan.steps.find(
        (step) => step.assignee.kind === 'person' && step.assignee.relation === 'peer'
    );

    if (peer && peer.assignee.kind === 'person') {
        suggestions.push(`Ask someone else instead of ${peer.assignee.name}.`);
    }
    if (plan.steps.filter((step) => step.assignee.kind === 'person').length > 1) {
        suggestions.push('I should be asked before anyone else is.');
    }
    if (plan.steps.some((step) => step.assignee.kind === 'agent')) {
        suggestions.push('Do not put anything on the schedule until my shift lead replies.');
    }
    return suggestions;
}

/**
 * The only two transitions there are.
 *
 * Pure: same state and action in, same state out. `revise` bumps the revision
 * and records why, because a plan the associate has already sent back once is
 * a different thing to review than a plan they are seeing for the first time —
 * and today's `Plan` has no revision field at all (#84), so this is the shape
 * that would have to be added.
 */
export function review(state: ReviewState, action: ReviewAction): ReviewState {
    if (state.status === 'approved') {
        return state;
    }

    switch (action.type) {
        case 'approve':
            return { ...state, status: 'approved' };

        case 'revise':
            return {
                status: 'awaiting-review',
                history: [...state.history, action.feedback],
                plan: {
                    ...state.plan,
                    revision: state.plan.revision + 1,
                    revisedBecause: action.feedback,
                    steps: reviseSteps(state.plan.steps, action.feedback),
                },
            };
    }
}

/**
 * Stand-in for the replan. A real revision comes back from the model; this
 * moves one thing so the surface has a visible difference to render.
 */
function reviseSteps(steps: ProposedStep[], feedback: string): ProposedStep[] {
    if (/someone else|instead of/i.test(feedback)) {
        return steps.map((step) =>
            step.assignee.kind === 'person' && step.assignee.relation === 'peer'
                ? {
                      ...step,
                      action: step.action.replace(step.assignee.name, 'Priya Raman'),
                      assignee: { ...step.assignee, name: 'Priya Raman' },
                  }
                : step
        );
    }

    if (/before anyone else|asked before/i.test(feedback)) {
        const associate = steps.find(
            (step) => step.assignee.kind === 'person' && step.assignee.relation === 'associate'
        );
        if (!associate) return steps;
        const reordered = [associate, ...steps.filter((step) => step.id !== associate.id)];
        return reordered.map((step, index) => ({
            ...step,
            waitsOn: index === 0 ? undefined : reordered[index - 1].id,
        }));
    }

    return steps;
}

/* ------------------------------------------------------------------ *
 * What the surface may say while the plan is being made
 * ------------------------------------------------------------------ */

/**
 * ADR-023's phases, and the signal each one is entitled to.
 *
 * Reproduced here because the prototype has to show the *approach* to the plan,
 * not just the plan: item 5 of #85. The rule that matters is the one that is
 * easy to break by accident — there is deliberately **no "agents selected"
 * phase**, because no such event exists anywhere in the system.
 */
export const NARRATION_PHASES = [
    {
        phase: 'Sent',
        says: 'Sending your request',
        signal: 'the createPlan POST is in flight',
    },
    {
        phase: 'Routed',
        says: 'Working this one through the full plan',
        signal: "the createPlan response's lane",
    },
    {
        phase: 'Connected',
        says: 'Working this one through the full plan',
        signal: 'connection_status — plumbing, says nothing',
    },
    {
        phase: 'Working',
        says: 'Workforce Agent is responding',
        signal: 'agent_message_streaming, which carries the executor name',
    },
    {
        phase: 'Done',
        says: '',
        signal: 'plan_approval_request — the narration stops and the plan appears',
    },
] as const;

export type NarrationPhase = (typeof NARRATION_PHASES)[number]['phase'];

/* ------------------------------------------------------------------ *
 * The plan the variations render
 * ------------------------------------------------------------------ */

/**
 * The shift swap, as ADR-028 left it: the associate **names** their partner —
 * there is no peer discovery — and the plan carries the approvals.
 *
 * The two invented people are marked `simulated: true`. Whether that becomes a
 * visible badge is #92's to decide, not this prototype's; the model records the
 * fact either way, because a surface cannot label what the data does not know.
 */
export const SHIFT_SWAP: ProposedPlan = {
    request: 'Swap my Saturday shift with Marcus Bell',
    revision: 1,
    steps: [
        {
            id: 1,
            action: 'Check the swap procedure for this store',
            assignee: { kind: 'agent', name: 'Workforce Agent' },
        },
        {
            id: 2,
            action: 'Confirm you want Saturday 14 February covered',
            assignee: { kind: 'person', name: 'You', relation: 'associate', simulated: false },
            waitsOn: 1,
        },
        {
            id: 3,
            action: 'Ask Marcus Bell to take the shift',
            assignee: { kind: 'person', name: 'Marcus Bell', relation: 'peer', simulated: true },
            waitsOn: 2,
        },
        {
            id: 4,
            action: 'Ask Dana Reyes to approve the swap',
            assignee: { kind: 'person', name: 'Dana Reyes', relation: 'manager', simulated: true },
            waitsOn: 3,
        },
        {
            id: 5,
            action: 'Put the swap on the schedule',
            assignee: { kind: 'agent', name: 'Workforce Agent' },
            waitsOn: 4,
        },
    ],
};

export const INITIAL_REVIEW: ReviewState = {
    status: 'awaiting-review',
    plan: SHIFT_SWAP,
    history: [],
};

/* ------------------------------------------------------------------ *
 * Small pure helpers the variations share
 * ------------------------------------------------------------------ */

/** "2 people, 1 specialist" — counted from the plan, never hardcoded. */
export function whoIsInvolved(plan: ProposedPlan): string {
    const people = new Set(
        plan.steps
            .filter(
                (step) => step.assignee.kind === 'person' && step.assignee.relation !== 'associate'
            )
            .map((step) => step.assignee.name)
    );
    const agents = new Set(
        plan.steps.filter((step) => step.assignee.kind === 'agent').map((step) => step.assignee.name)
    );

    const parts: string[] = [];
    if (people.size) parts.push(`${people.size} ${people.size === 1 ? 'person' : 'people'}`);
    if (agents.size) {
        parts.push(`${agents.size} ${agents.size === 1 ? 'specialist' : 'specialists'}`);
    }
    return parts.join(' and ');
}

/** How a step's assignee should be described in one short phrase. */
export function describeAssignee(assignee: Assignee): string {
    if (assignee.kind === 'agent') return assignee.name;
    switch (assignee.relation) {
        case 'associate':
            return 'You';
        case 'peer':
            return `${assignee.name}, the associate you named`;
        case 'manager':
            return `${assignee.name}, your shift lead`;
    }
}

/**
 * Whether this step leaves the building.
 *
 * The single most useful thing an associate can tell about a step, and the one
 * today's model cannot express.
 */
export function leavesTheSystem(step: ProposedStep): boolean {
    return step.assignee.kind === 'person' && step.assignee.relation !== 'associate';
}

/** What the surface promises will happen when a person is asked. */
export function whatWaitingMeans(step: ProposedStep): string {
    if (step.assignee.kind !== 'person') return '';
    switch (step.assignee.relation) {
        case 'associate':
            return 'Nothing moves until you say so.';
        case 'peer':
            return 'They get a message. They can say no.';
        case 'manager':
            return 'They sign it off. They can say no.';
    }
}
