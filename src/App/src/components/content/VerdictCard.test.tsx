import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import VerdictCard from './VerdictCard';

describe('a declined Verdict record', () => {
    it('names the colleague who declined and says the rest of the plan did not proceed', () => {
        render(
            <VerdictCard
                verdict={{
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
                    provenanceLine: 'No workforce management system was consulted.',
                }}
            />,
        );

        expect(screen.getByText('Marcus Bell declined')).toBeInTheDocument();
        expect(screen.getByTestId('verdict-plan-stopped')).toHaveTextContent(
            'The rest of this plan did not proceed.',
        );
        expect(screen.getByTestId('verdict-provenance')).toBeInTheDocument();
    });
});
