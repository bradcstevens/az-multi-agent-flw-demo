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
    revision: number;
    feedback: string[];
    verdict: 'pending' | 'approved';
}

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

/** Authored feedback starters, selected deterministically from this Reviewable plan. */
export const revisionSuggestionsFor = (
    steps: readonly PlanApprovalStep[],
): string[] => {
    const reviewSteps = reviewablePlanSteps(steps);
    const suggestions: string[] = [];
    if (reviewSteps.some((step) => step.assignee.kind === 'person' && step.assignee.relation === 'peer')) {
        suggestions.push('Ask a different associate.');
    }
    if (reviewSteps.filter((step) => step.assignee.kind === 'person').length > 1) {
        suggestions.push('Change the order people are asked.');
    }
    if (reviewSteps.some((step) => step.assignee.kind === 'agent')) {
        suggestions.push('Use a different specialist.');
    }
    return suggestions;
};

/** The review verdict is binary: approval is terminal; feedback asks for a revision. */
export const applyPlanVerdict = (
    state: PlanVerdictState,
    action: PlanVerdictAction,
): PlanVerdictState => {
    if (state.verdict === 'approved') return state;
    if (action.kind === 'approve') return { ...state, verdict: 'approved' };
    const feedback = action.feedback.trim();
    return feedback
        ? { ...state, revision: state.revision + 1, feedback: [...state.feedback, feedback] }
        : state;
};
