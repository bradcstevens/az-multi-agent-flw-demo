import { describe, expect, it } from 'vitest';

import { PlanDataService } from './PlanDataService';

describe('the team a Chat reads its one-tap controls from', () => {
    /*
      One control at a time (#131, ADR-033) is a hand-off: the **Follow-on
      task** card yields the slot and the **Rehearsed reply** chips take it. The
      chat surface resolves both from `planData.team`, which is this
      conversion's output — and it carried `follow_on` while dropping
      `rehearsed_replies`, so the card yielded the slot to nothing and the
      presenter was back to typing the one answer the chips exist to remove.
    */
    it('carries the authored rehearsed replies through to the surface', () => {
        const converted = PlanDataService.convertTeamConfiguration({
            id: 'team-config-223',
            team_id: 'team-223',
            name: 'Store Assistant',
            status: 'visible',
            created: '',
            created_by: '',
            user_id: 'user-223',
            data_type: 'team_config',
            agents: [],
            starting_tasks: [
                {
                    id: 'task-223-troubleshooting',
                    name: 'The coffee brewer is down',
                    prompt: 'The coffee brewer is down.',
                    created: '',
                    creator: '',
                    logo: 'Wrench',
                    lane: 'fast',
                    follow_on: 'task-223-escalation',
                    rehearsed_replies: [
                        'I switched it off at the wall and back on again.',
                    ],
                },
            ],
        } as never);

        expect(converted?.starting_tasks[0]).toMatchObject({
            follow_on: 'task-223-escalation',
            rehearsed_replies: ['I switched it off at the wall and back on again.'],
        });
    });
});

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
