import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import PersonalAnswerCard from './PersonalAnswerCard';
import { parsePersonalAnswer, PERSONAL_ANSWER_KIND } from '../../models/personalAnswer';

const answer = parsePersonalAnswer({
    personal_answer: {
        kind: PERSONAL_ANSWER_KIND,
        display_name: 'Tanya Alvarez',
        role: 'Store associate, Store 223',
        facts: [
            { label: 'PTO balance', value: '34.5 hours' },
            { label: 'Hours scheduled this week', value: '32' },
        ],
        provenance_line:
            'No payroll system was queried — these figures were authored for this walkthrough.',
    },
})!;

describe('the personal answer card', () => {
    it('names the associate the record answers for', () => {
        render(<PersonalAnswerCard answer={answer} />);

        expect(screen.getByTestId('personal-answer-name')).toHaveTextContent(
            'Tanya Alvarez',
        );
    });

    it('shows the record whole, in the order the backend stated it', () => {
        // Picking out the field the question asked about would be a third
        // classifier behind the two the gate already has, and a third
        // classifier can report the wrong number — for a claim about somebody's
        // pay, the worst thing this system could say.
        render(<PersonalAnswerCard answer={answer} />);

        expect(screen.getAllByRole('term').map((node) => node.textContent)).toEqual([
            'PTO balance',
            'Hours scheduled this week',
        ]);
    });

    it('renders the provenance line the associate record carried', () => {
        render(<PersonalAnswerCard answer={answer} />);

        expect(screen.getByTestId('personal-answer')).toHaveTextContent(
            /No payroll system was queried/i,
        );
    });

    it('renders a record that holds nothing but a name', () => {
        // A thin record still answers: it says who is signed in and lists
        // nothing, which is true. An empty card is better than a claim.
        render(
            <PersonalAnswerCard
                answer={{ displayName: 'Tanya Alvarez', role: '', facts: [], provenanceLine: '' }}
            />,
        );

        expect(screen.getByTestId('personal-answer-name')).toHaveTextContent(
            'Tanya Alvarez',
        );
        expect(screen.queryAllByRole('term')).toEqual([]);
    });
});
