import { describe, expect, it } from 'vitest';

import { parseVerdict } from './verdict';

const DECLINED = {
    m_plan_id: 'plan-223',
    step_id: 3,
    assignee: {
        kind: 'person',
        name: 'Marcus Bell',
        relation: 'peer',
        simulated: true,
    },
    outcome: 'declined',
    words: "I'm away that weekend after all.",
    provenance_line: 'Record-provided test provenance.',
    stopped_line:
        'Nothing waiting on this went ahead: Ask Dana Reyes to approve the swap; '
        + 'Put the swap on the schedule.',
};

/**
 * What did not happen is authored on the record, never here (ADR-036 decision
 * 4): a component that composed the sentence would be an invented person's
 * consequence written outside the seam that discloses it.
 */
describe('a declined Verdict record', () => {
    it('carries the words for what did not happen, exactly as the record wrote them', () => {
        expect(parseVerdict(DECLINED)?.stoppedLine).toBe(DECLINED.stopped_line);
    });

    it('carries no such words when the record sent none', () => {
        const { stopped_line: _omitted, ...withoutLine } = DECLINED;

        expect(parseVerdict(withoutLine)?.stoppedLine).toBeUndefined();
    });

    it('is still readable when the record sent an empty line', () => {
        const verdict = parseVerdict({ ...DECLINED, stopped_line: '' });

        expect(verdict?.outcome).toBe('declined');
        expect(verdict?.stoppedLine).toBeUndefined();
    });
});
