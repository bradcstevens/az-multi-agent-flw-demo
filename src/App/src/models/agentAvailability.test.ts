import { describe, it, expect } from 'vitest';

import {
    AVAILABILITY_NOTE,
    NO_ROSTER_MESSAGE,
    availabilityHeading,
    resolveAvailability,
} from './agentAvailability';
import { TeamConfig } from './Team';

const team = (names: string[]): TeamConfig =>
    ({
        agents: names.map((name) => ({ input_key: '', type: '', name })),
    }) as unknown as TeamConfig;

const ROSTER = team(['TroubleshootingAgent', 'ShiftTasksAgent', 'EscalationAgent']);

describe('who the Agent Team panel says is available', () => {
    it('names the store assistant roster while the plan is still on its way', () => {
        // The whole point of the ticket: `planData` is null for the entire
        // loading window, and the roster has been in Redux since HomePage's
        // mount. The panel has something true to say and was saying nothing.
        const available = resolveAvailability(null, null, ROSTER, 3);

        expect(available.agents.map((agent) => agent.name)).toEqual([
            'TroubleshootingAgent',
            'ShiftTasksAgent',
            'EscalationAgent',
        ]);
        expect(available.source).toBe('roster');
    });

    it('takes the count from the roster selector rather than recounting the list', () => {
        // `selectTeamAgentCount` is the count; a second one derived here is a
        // second thing to disagree with it.
        expect(resolveAvailability(null, null, ROSTER, 7).count).toBe(7);
    });

    it('prefers the conversation roster once the plan fetch has returned', () => {
        const conversation = team(['ShiftTasksAgent']);

        const available = resolveAvailability(conversation, null, ROSTER, 3);

        expect(available.agents.map((agent) => agent.name)).toEqual(['ShiftTasksAgent']);
        expect(available.count).toBe(1);
        expect(available.source).toBe('conversation');
    });

    it('falls back to a historical plan roster before the selected team', () => {
        const available = resolveAvailability(null, ['EscalationAgent'], ROSTER, 3);

        expect(available.agents.map((agent) => agent.name)).toEqual(['EscalationAgent']);
        expect(available.source).toBe('conversation');
    });

    it('knows of nobody when there is genuinely no roster anywhere', () => {
        const available = resolveAvailability(null, null, null, 0);

        expect(available.agents).toEqual([]);
        expect(available.count).toBe(0);
        expect(available.source).toBe('none');
    });

    it('does not treat a team with an empty roster as a roster', () => {
        expect(resolveAvailability(null, null, team([]), 0).source).toBe('none');
    });
});

describe('what the panel is allowed to claim', () => {
    it('counts the specialists in the heading', () => {
        expect(availabilityHeading(3)).toBe('3 specialists available');
    });

    it('reads as English for a roster of one', () => {
        expect(availabilityHeading(1)).toBe('1 specialist available');
    });

    it('states availability and never selection', () => {
        // CONTEXT.md, **Available vs participating**: the roster says who
        // *could* answer. On the boundary-probe beat the number that
        // participate is zero, and the Token meter renders a real `0` two
        // inches below. Copy claiming these three were chosen for the question
        // contradicts the panel beneath it.
        const claims = [availabilityHeading(3), AVAILABILITY_NOTE].join(' ').toLowerCase();

        for (const forbidden of ['assigned', 'identified', 'selected', 'chosen', 'working on']) {
            expect(claims, `claims selection: ${forbidden}`).not.toContain(forbidden);
        }
        expect(claims).toContain('available');
    });

    it('keeps the empty state, because no roster is a real state', () => {
        expect(NO_ROSTER_MESSAGE).toBe('No agent roster loaded for this conversation.');
    });

    it('presupposes no question, because the rail says it before one is typed', () => {
        // Since #79 the note is on the home surface too, where nothing has been
        // asked yet. "Which of them take *this question*" there describes a
        // question that does not exist — the same failure as claiming
        // participation, in the grammar rather than in the verb.
        expect(AVAILABILITY_NOTE).not.toMatch(/this question/i);
        expect(AVAILABILITY_NOTE.toLowerCase()).toContain('available to answer');
    });
});
