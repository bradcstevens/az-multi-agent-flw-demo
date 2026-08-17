import { describe, expect, it } from 'vitest';

import { PlanDataService } from './PlanDataService';

describe('PlanDataService.parsePlanApprovalRequest', () => {
    it('carries a person step and its prerequisite from the approval frame', () => {
        const plan = PlanDataService.parsePlanApprovalRequest({
            plan: {
                id: 'approval-1',
                user_request: 'Swap my Saturday shift with Marcus Bell',
                team: ['WorkforceAgent'],
                facts: '',
                steps: [
                    {
                        id: 3,
                        action: 'Ask Marcus Bell to take the shift',
                        assignee: {
                            kind: 'person',
                            name: 'Marcus Bell',
                            relation: 'peer',
                            simulated: true,
                        },
                        waitsOn: 2,
                    },
                ],
            },
            status: 'PENDING_APPROVAL',
        });

        expect(plan?.steps).toEqual([
            {
                id: 3,
                action: 'Ask Marcus Bell to take the shift',
                cleanAction: 'Ask Marcus Bell to take the shift',
                assignee: {
                    kind: 'person',
                    name: 'Marcus Bell',
                    relation: 'peer',
                    simulated: true,
                },
                waitsOn: 2,
            },
        ]);
    });
});
