export type PersonRelation = 'associate' | 'peer' | 'manager';

export type Assignee =
    | { kind: 'agent'; name: string }
    | {
          kind: 'person';
          name: string;
          relation: PersonRelation;
          simulated: boolean;
      };

export interface ProposedStep {
    id: number;
    action: string;
    assignee: Assignee;
    waitsOn?: number;
}

export interface PlanApprovalStep {
    id: number;
    action: string;
    cleanAction?: string;
    agent?: string;
    assignee?: Assignee;
    waitsOn?: number | null;
}

export interface ReviewablePlanStep {
    id: number;
    action: string;
    assignee: Assignee;
    waitsOn?: number;
    role: 'Specialist step' | 'Person step';
    assigneeDescription: string;
    waitingDescription: string | null;
}

export interface PlanVerdictState {
    /** Which revision of this Reviewable plan the associate is looking at. */
    revision: number;
    /** What the associate asked to change, oldest first. */
    feedback: string[];
    verdict: 'pending' | 'approved';
}

/**
 * The two things an associate may say about a Reviewable plan. There is no
 * third: leaving the conversation is navigation, not a verdict (ADR-031).
 */
export type PlanVerdictAction =
    | { kind: 'approve' }
    | { kind: 'revise'; feedback: string };

export const isPersonRelation = (value: unknown): value is PersonRelation =>
    value === 'associate' || value === 'peer' || value === 'manager';

const asAssignee = (step: PlanApprovalStep): Assignee => {
    if (!step.assignee) {
        return { kind: 'agent', name: step.agent || 'Specialist' };
    }

    if (step.assignee.kind === 'agent') {
        return step.assignee;
    }

    if (isPersonRelation(step.assignee.relation)) {
        return step.assignee;
    }

    throw new Error(`Unknown person relation: ${String(step.assignee.relation)}`);
};

const describePerson = (assignee: Extract<Assignee, { kind: 'person' }>): string => {
    switch (assignee.relation) {
        case 'associate':
            return 'You are asked to confirm this request.';
        case 'peer':
            return `${assignee.name}, the associate you named, is asked next.`;
        case 'manager':
            return `${assignee.name}, your shift lead, is asked next.`;
    }
};

const describeWaiting = (assignee: Extract<Assignee, { kind: 'person' }>): string => {
    if (assignee.relation === 'associate') {
        return 'You get a message. You can say no.';
    }
    return `${assignee.name} gets a message. ${assignee.name} can say no.`;
};

const orderSteps = (steps: readonly PlanApprovalStep[]): PlanApprovalStep[] => {
    const remaining = new Map(steps.map((step) => [step.id, step]));
    const ordered: PlanApprovalStep[] = [];
    const completed = new Set<number>();

    while (remaining.size) {
        const ready = [...remaining.values()].filter(
            (step) => step.waitsOn == null || completed.has(step.waitsOn),
        );

        if (!ready.length) {
            throw new Error('Plan waitsOn order has a cycle or an unknown step.');
        }

        for (const step of ready) {
            ordered.push(step);
            completed.add(step.id);
            remaining.delete(step.id);
        }
    }

    return ordered;
};

export const reviewablePlanSteps = (steps: readonly PlanApprovalStep[]): ReviewablePlanStep[] =>
    orderSteps(steps).map((step) => {
        const assignee = asAssignee(step);
        const action = step.action || step.cleanAction || '';
        const reviewStep = {
            id: step.id,
            action,
            assignee,
            ...(step.waitsOn == null ? {} : { waitsOn: step.waitsOn }),
        };

        if (assignee.kind === 'agent') {
            return {
                ...reviewStep,
                role: 'Specialist step',
                assigneeDescription: `${assignee.name} performs this step.`,
                waitingDescription: null,
            };
        }

        return {
            ...reviewStep,
            role: 'Person step',
            assigneeDescription: describePerson(assignee),
            waitingDescription: describeWaiting(assignee),
        };
    });

/**
 * The starters offered beside the free-text box when a plan is sent back.
 *
 * **Derived**, never generated (ADR-033): pure code reading the plan in front
 * of the associate — the peer it names, whether more than one person is
 * involved, whether a specialist would act. A different plan offers a
 * different set, and no model puts words in the associate's mouth on stage.
 */
export const revisionSuggestionsFor = (
    steps: readonly PlanApprovalStep[],
): string[] => {
    const reviewSteps = reviewablePlanSteps(steps);
    const people = reviewSteps
        .map((step) => step.assignee)
        .filter((assignee): assignee is Extract<Assignee, { kind: 'person' }> =>
            assignee.kind === 'person');

    const namedPeers = [
        ...new Set(
            people.filter((person) => person.relation === 'peer').map((peer) => peer.name),
        ),
    ];

    const suggestions = namedPeers.map((name) => `Ask somebody other than ${name}.`);
    if (people.length > 1) {
        suggestions.push('Change the order people are asked.');
    }
    if (reviewSteps.some((step) => step.assignee.kind === 'agent')) {
        suggestions.push('Use a different specialist.');
    }
    return suggestions;
};

/** The lineage an arriving Reviewable plan carries, before any verdict on it. */
export const pendingVerdictFor = (plan: {
    revision?: number;
    revision_feedback?: string[];
}): PlanVerdictState => ({
    revision: plan.revision ?? 1,
    feedback: [...(plan.revision_feedback ?? [])],
    verdict: 'pending',
});

/**
 * The verdict reducer. Approval is terminal — a second verdict on an approved
 * plan changes nothing — and a send-back keeps the feedback that produced the
 * revision it asks for, so the associate can check they were understood.
 * Returns the state it was given when nothing was said, which is what the
 * caller reads to know there is nothing to send.
 */
export const applyPlanVerdict = (
    state: PlanVerdictState,
    action: PlanVerdictAction,
): PlanVerdictState => {
    if (state.verdict === 'approved') return state;
    if (action.kind === 'approve') return { ...state, verdict: 'approved' };
    const feedback = action.feedback.trim();
    if (!feedback) return state;
    return {
        ...state,
        revision: state.revision + 1,
        feedback: [...state.feedback, feedback],
    };
};
