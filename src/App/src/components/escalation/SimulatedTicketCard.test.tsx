import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import SimulatedTicketCard from './SimulatedTicketCard';
import { parseRaisedTicket } from '../../models/ticket';

const ticket = parseRaisedTicket({
    ticket_id: 'SIM-223-0041',
    status: 'submitted',
    fields: [
        { name: 'ticket_id', value: 'SIM-223-0041' },
        { name: 'priority', value: '2' },
        { name: 'asset', value: 'front counter coffee brewer, left head' },
        { name: 'symptom', value: 'left head runs cold and slow' },
        { name: 'steps_attempted', value: 'Fitted a fresh paper filter; checked the grind' },
        { name: 'notes', value: 'not reported' },
    ],
})!;

describe('the Simulated ticket card', () => {
    it('shows the ticket number the confirmation issued', () => {
        render(<SimulatedTicketCard ticket={ticket} />);

        expect(screen.getByTestId('simulated-ticket-id')).toHaveTextContent(
            'SIM-223-0041',
        );
    });

    it('shows the steps the associate already reported, never re-typed', () => {
        // The requirement, at the surface it is finally claimed on.
        render(<SimulatedTicketCard ticket={ticket} />);

        expect(screen.getByText(/Fitted a fresh paper filter/)).toBeInTheDocument();
    });

    it('shows every field, in the order the ticket template states them', () => {
        // The order the associate read the ticket back in before approving it.
        // A card that re-ordered the rows would be showing a different
        // document from the one they approved.
        render(<SimulatedTicketCard ticket={ticket} />);

        const names = screen
            .getAllByRole('term')
            .map((node) => node.textContent);
        expect(names).toEqual([
            'ticket_id',
            'priority',
            'asset',
            'symptom',
            'steps_attempted',
            'notes',
        ]);
    });

    it('shows a field that says not reported rather than hiding the row', () => {
        // Hiding it would show a shorter, tidier ticket and hide exactly the
        // field somebody downstream will act on the absence of.
        render(<SimulatedTicketCard ticket={ticket} />);

        expect(screen.getByText('notes')).toBeInTheDocument();
        expect(screen.getByText('not reported')).toBeInTheDocument();
    });

    it('renders no component-authored service-desk notice', () => {
        render(<SimulatedTicketCard ticket={ticket} />);

        expect(screen.queryByText(/No service desk receives this ticket/)).not.toBeInTheDocument();
    });
});
