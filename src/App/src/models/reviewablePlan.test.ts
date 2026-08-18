import { describe, expect, it } from 'vitest';

import {
    applyPlanVerdict,
    isPersonRelation,
    nextUnresolvedPerson,
    pendingVerdictFor,
    revisionSuggestionsFor,
    reviewablePlanSteps,
    type ProposedStep,
} from './reviewablePlan';

const pendingVerdict = () => pendingVerdictFor({});

const STEPS: ProposedStep[] = [
    {
        id: 1,
        action: 'Check the swap procedure for this store',
        assignee: { kind: 'agent', name: 'Workforce Agent' },
    },
    {
        id: 2,
        action: 'Confirm you want Saturday covered',
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
];

describe('the Reviewable plan model', () => {
    it('describes specialists and people in the order the plan asks them', () => {
        expect(reviewablePlanSteps(STEPS)).toEqual([
            {
                ...STEPS[0],
                role: 'Specialist step',
                assigneeDescription: 'Workforce Agent performs this step.',
                waitingDescription: null,
            },
            {
                ...STEPS[1],
                role: 'Person step',
                assigneeDescription: 'You are asked to confirm this request.',
                waitingDescription: 'You get a message. You can say no.',
            },
            {
                ...STEPS[2],
                role: 'Person step',
                assigneeDescription: 'Marcus Bell, the associate you named, is asked next.',
                waitingDescription: 'Marcus Bell gets a message. Marcus Bell can say no.',
            },
            {
                ...STEPS[3],
                role: 'Person step',
                assigneeDescription: 'Dana Reyes, your shift lead, is asked next.',
                waitingDescription: 'Dana Reyes gets a message. Dana Reyes can say no.',
            },
        ]);
    });

    it('admits only the three person relations the contract defines', () => {
        expect(['associate', 'peer', 'manager'].every(isPersonRelation)).toBe(true);
        expect(isPersonRelation('director')).toBe(false);
    });

    it('orders dependent steps from waitsOn rather than their frame position', () => {
        expect(reviewablePlanSteps([STEPS[3], STEPS[1], STEPS[0], STEPS[2]]).map((step) => step.id)).toEqual([
            1,
            2,
            3,
            4,
        ]);
    });

    it('names only the person the approved plan is actually waiting on', () => {
        expect(nextUnresolvedPerson(STEPS, [])?.name).toBe('Marcus Bell');
        expect(nextUnresolvedPerson(STEPS, [3])?.name).toBe('Dana Reyes');
        expect(nextUnresolvedPerson(STEPS, [3, 4])).toBeNull();
    });

    it('rejects a person step whose relation is outside the contract', () => {
        expect(() =>
            reviewablePlanSteps([
                {
                    id: 1,
                    action: 'Ask someone else',
                    assignee: {
                        kind: 'person',
                        name: 'Taylor Reed',
                        relation: 'director',
                        simulated: true,
                    },
                } as never,
            ]),
        ).toThrow('Unknown person relation: director');
    });

    it('derives the send-back suggestions from the plan in front of the associate', () => {
        expect(revisionSuggestionsFor(STEPS)).toEqual([
            'Ask somebody other than Marcus Bell.',
            'Change the order people are asked.',
            'Use a different specialist.',
        ]);
    });

    it('offers a different set once the plan names a different peer', () => {
        const rewritten = STEPS.map((step) =>
            step.assignee?.kind === 'person' && step.assignee.relation === 'peer'
                ? { ...step, assignee: { ...step.assignee, name: 'Dana Okafor' } }
                : step,
        );

        expect(revisionSuggestionsFor(rewritten)).toContain(
            'Ask somebody other than Dana Okafor.',
        );
    });

    it('offers nothing about people when the plan asks none of them', () => {
        expect(revisionSuggestionsFor([STEPS[0]])).toEqual(['Use a different specialist.']);
    });

    it('folds each send-back into the revision lineage', () => {
        const revised = applyPlanVerdict(pendingVerdict(), {
            kind: 'revise',
            feedback: 'Ask Marcus instead.',
        });

        expect(revised).toEqual({
            revision: 2,
            feedback: ['Ask Marcus instead.'],
            verdict: 'pending',
        });
        expect(
            applyPlanVerdict(revised, { kind: 'revise', feedback: 'Actually, ask Dana.' }),
        ).toEqual({
            revision: 3,
            feedback: ['Ask Marcus instead.', 'Actually, ask Dana.'],
            verdict: 'pending',
        });
    });

    it('sends nothing back on an empty box', () => {
        const pending = pendingVerdict();

        expect(applyPlanVerdict(pending, { kind: 'revise', feedback: '   ' })).toBe(pending);
    });

    it('makes approval terminal', () => {
        const approved = applyPlanVerdict(pendingVerdict(), { kind: 'approve' });

        expect(approved.verdict).toBe('approved');
        expect(applyPlanVerdict(approved, { kind: 'revise', feedback: 'Ask Dana.' })).toBe(
            approved,
        );
        expect(applyPlanVerdict(approved, { kind: 'approve' })).toBe(approved);
    });

    it('starts from the lineage the arriving plan carries', () => {
        expect(
            pendingVerdictFor({ revision: 3, revision_feedback: ['Ask Marcus instead.'] }),
        ).toEqual({
            revision: 3,
            feedback: ['Ask Marcus instead.'],
            verdict: 'pending',
        });
        expect(pendingVerdictFor({})).toEqual({ revision: 1, feedback: [], verdict: 'pending' });
    });
});
