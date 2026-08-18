import React from 'react';
import { Body1Strong, Caption1 } from '@fluentui/react-components';
import { TicketDiagonalRegular } from '@fluentui/react-icons';

import { RaisedTicket } from '../../models/ticket';

/**
 * The Simulated ticket, rendered (issue #22, R4).
 *
 * Every row, in the order the payload sent them — which is TKT-001's order,
 * which is the order the associate read the ticket back in before they
 * approved it. A card that hid the rows saying *not reported* would show a
 * shorter, tidier ticket and hide exactly the fields somebody downstream will
 * act on the absence of.
 *
 */
export interface SimulatedTicketCardProps {
    ticket: RaisedTicket;
}

const SimulatedTicketCard: React.FC<SimulatedTicketCardProps> = ({ ticket }) => (
    <section
        className="simulated-ticket"
        aria-label="Service ticket"
        data-testid="simulated-ticket"
    >
        <header className="simulated-ticket__header">
            <TicketDiagonalRegular aria-hidden="true" />
            <Body1Strong data-testid="simulated-ticket-id">{ticket.ticketId}</Body1Strong>
            {ticket.status ? (
                <Caption1 data-testid="simulated-ticket-status">{ticket.status}</Caption1>
            ) : null}
        </header>
        <dl className="simulated-ticket__fields">
            {ticket.fields.map((field) => (
                <div className="simulated-ticket__row" key={field.name}>
                    <dt>{field.name}</dt>
                    <dd>{field.value}</dd>
                </div>
            ))}
        </dl>
    </section>
);

export default SimulatedTicketCard;
