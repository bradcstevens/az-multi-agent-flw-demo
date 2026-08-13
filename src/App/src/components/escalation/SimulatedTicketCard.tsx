import React from 'react';
import { Body1Strong, Caption1 } from '@fluentui/react-components';
import { TicketDiagonalRegular } from '@fluentui/react-icons';

import { RaisedTicket } from '../../models/ticket';
import SimulatedBadge from '../branding/SimulatedBadge';

/**
 * The Simulated ticket, rendered (issue #22, R4).
 *
 * Every row, in the order the payload sent them — which is TKT-001's order,
 * which is the order the associate read the ticket back in before they
 * approved it. A card that hid the rows saying *not reported* would show a
 * shorter, tidier ticket and hide exactly the fields somebody downstream will
 * act on the absence of.
 *
 * The badge is unconditional and carries no flag from the wire. Every ticket
 * this assistant raises is simulated — there is no code path that produces
 * another kind — so a flag would only ever be one omission away from an
 * unbadged ticket on a stakeholder's screen.
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
            <SimulatedBadge what="This service ticket" />
        </header>
        {/*
          No real service desk receives this, and the number above is the part
          an associate could repeat to somebody who was not in the room. Said
          on the card rather than left to the reply that introduced it.
        */}
        <Caption1 className="simulated-ticket__notice">
            No service desk receives this ticket and no engineer is dispatched.
        </Caption1>
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
