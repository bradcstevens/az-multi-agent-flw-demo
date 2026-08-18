import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import VerdictCard from './VerdictCard';
import { Verdict } from '@/models/verdict';

const STOPPED = 'Nothing waiting on this went ahead: Ask Dana Reyes to approve the swap.';

const declined = (overrides: Partial<Verdict> = {}): Verdict => ({
    planId: 'review-1',
    stepId: 3,
    assignee: {
        kind: 'person',
        name: 'Marcus Bell',
        relation: 'peer',
        simulated: true,
    },
    outcome: 'declined',
    words: 'I cannot make the Saturday swap.',
    stoppedLine: STOPPED,
    provenanceLine: 'No workforce management system was consulted.',
    ...overrides,
});

describe('a declined Verdict record', () => {
    it('names the colleague who declined and says the rest of the plan did not proceed', () => {
        render(<VerdictCard verdict={declined()} />);

        expect(screen.getByText('Marcus Bell declined')).toBeInTheDocument();
        expect(screen.getByTestId('verdict-plan-stopped')).toHaveTextContent(STOPPED);
        expect(screen.getByTestId('verdict-provenance')).toBeInTheDocument();
    });

    it('says nothing about what stopped when the record said nothing', () => {
        render(<VerdictCard verdict={declined({ stoppedLine: undefined })} />);

        expect(screen.queryByTestId('verdict-plan-stopped')).not.toBeInTheDocument();
    });
});
