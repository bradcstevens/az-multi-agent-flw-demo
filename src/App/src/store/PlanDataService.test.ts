import { describe, expect, it } from 'vitest';

import { PlanDataService } from './PlanDataService';

describe('Reviewable plan approval frames', () => {
    it('keeps revision lineage from structured frames', () => {
        const parsed = PlanDataService.parsePlanApprovalRequest({
            status: 'PENDING_APPROVAL',
            plan: {
                id: 'mplan-1',
                user_request: 'Swap Saturday with Marcus.',
                team: [],
                facts: '',
                steps: [],
                revision: 2,
                revision_feedback: ['Ask somebody other than Marcus.'],
            },
        });

        expect(parsed).toMatchObject({
            revision: 2,
            revision_feedback: ['Ask somebody other than Marcus.'],
        });
    });

    it('keeps revision lineage from legacy string frames', () => {
        const parsed = PlanDataService.parsePlanApprovalRequest(
            "PlanApprovalRequest(plan=MPlan(id='mplan-1', user_request='Swap Saturday with Marcus.', team=[], facts='', steps=[], revision=3, revision_feedback=['Ask somebody other than Marcus.', 'Ask Dana.']), status='PENDING_APPROVAL')",
        );

        expect(parsed).toMatchObject({
            revision: 3,
            revision_feedback: ['Ask somebody other than Marcus.', 'Ask Dana.'],
        });
    });
});
