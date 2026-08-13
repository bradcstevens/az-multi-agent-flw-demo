/**
 * The Simulated ticket, as it arrives in the browser (issue #22).
 *
 * The backend's `src/backend/escalation/payloads.py` decides what the ticket
 * may claim; this file is the same contract read from the other end of the
 * socket, and it carries the rule across: **a surface may say nothing, but it
 * may not say something that is not so.** A ticket is the one artefact this
 * assistant produces that leaves the conversation — an associate can read its
 * number down a telephone — so the parser is total and returns `null` rather
 * than a partly-filled ticket.
 *
 * The **field order is the payload's**, not this file's. TKT-001's order is the
 * order the associate read the ticket back in before approving it, and a card
 * that re-ordered the rows between the reading and the record would be showing
 * them a different document. So the rows arrive as a list and are rendered in
 * the order they arrive; a copy of the order kept here would be a second
 * template, agreeing with itself.
 */

/** One row of the ticket, in TKT-001's own field name. */
export interface TicketField {
    name: string;
    value: string;
}

/**
 * A ticket that has been confirmed and persisted (R4).
 *
 * Only ever pushed by the plan-approval seam after the container took the
 * write, so a card on screen is evidence of a stored ticket rather than of an
 * intention. There is no `simulated` flag and deliberately so: every ticket
 * this system raises is simulated, there is no other kind, so the badge is a
 * property of the card. A flag would be one omission away from an unbadged
 * ticket.
 */
export interface RaisedTicket {
    ticketId: string;
    status: string;
    fields: TicketField[];
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
    value !== null && typeof value === 'object' && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : null;

const asText = (value: unknown): string => (typeof value === 'string' ? value : '');

/** One row, or null if it names no field. */
export const parseTicketField = (value: unknown): TicketField | null => {
    const record = asRecord(value);
    if (!record) return null;
    const name = asText(record.name).trim();
    if (!name) return null;
    return { name, value: asText(record.value) };
};

/**
 * A raised ticket, or null.
 *
 * A ticket with **no rows** is refused. A card headed with a ticket number and
 * carrying nothing under it reads as a ticket that was raised empty, which is a
 * claim about what was sent to a service desk — and the number is the part of
 * it an associate would repeat.
 */
export const parseRaisedTicket = (value: unknown): RaisedTicket | null => {
    const record = asRecord(value);
    if (!record) return null;

    const ticketId = asText(record.ticket_id).trim();
    if (!ticketId) return null;

    const rows = Array.isArray(record.fields) ? record.fields : [];
    const fields = rows
        .map(parseTicketField)
        .filter((field): field is TicketField => field !== null);
    if (fields.length === 0) return null;

    return {
        ticketId,
        status: asText(record.status).trim(),
        fields,
    };
};
