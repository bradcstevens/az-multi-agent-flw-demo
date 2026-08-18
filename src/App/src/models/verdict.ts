import { PersonRelation, isPersonRelation } from './reviewablePlan';

export type VerdictOutcome = 'approved' | 'declined';

export interface Verdict {
    planId: string;
    stepId: number;
    assignee: {
        kind: 'person';
        name: string;
        relation: PersonRelation;
        simulated: boolean;
    };
    outcome: VerdictOutcome;
    words: string;
    /** What a decline stopped, in the record's own words. Never composed here. */
    stoppedLine?: string;
    provenanceLine?: string;
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
    value !== null && typeof value === 'object' && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : null;

const asText = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

/** A Verdict record as it landed on the WebSocket, or null if it is unreadable. */
export const parseVerdict = (value: unknown): Verdict | null => {
    const record = asRecord(value);
    if (!record) return null;

    const planId = asText(record.m_plan_id);
    if (
        !planId
        || typeof record.step_id !== 'number'
        || !Number.isInteger(record.step_id)
    ) {
        return null;
    }

    const assignee = asRecord(record.assignee);
    const name = asText(assignee?.name);
    const relation = assignee?.relation;
    if (
        assignee?.kind !== 'person'
        || !name
        || !isPersonRelation(relation)
        || typeof assignee.simulated !== 'boolean'
    ) {
        return null;
    }

    const outcome = record.outcome;
    const words = asText(record.words);
    if ((outcome !== 'approved' && outcome !== 'declined') || !words) return null;

    const stoppedLine = asText(record.stopped_line);
    const provenanceLine = asText(record.provenance_line);
    return {
        planId,
        stepId: record.step_id,
        assignee: {
            kind: 'person',
            name,
            relation,
            simulated: assignee.simulated,
        },
        outcome,
        words,
        ...(stoppedLine ? { stoppedLine } : {}),
        ...(provenanceLine ? { provenanceLine } : {}),
    };
};
