import { describe, expect, it } from 'vitest';

import {
    isPersonRelation,
    reviewablePlanSteps,
    type ProposedStep,
} from './reviewablePlan';

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
});
