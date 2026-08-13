import { describe, expect, it } from 'vitest';

import { parseRaisedTicket, parseTicketField } from './ticket';

/**
 * The ticket contract, read from the browser's end (issue #22).
 *
 * The rule these carry is the build's: a surface may say nothing, but it may
 * not say something that is not so. Sharper here than anywhere else, because a
 * ticket number is the one thing on screen an associate can read down a
 * telephone to somebody who was never in the room.
 */
const raised = (overrides: Record<string, unknown> = {}) => ({
    ticket_id: 'SIM-223-0041',
    status: 'submitted',
    fields: [
        { name: 'ticket_id', value: 'SIM-223-0041' },
        { name: 'symptom', value: 'left head runs cold and slow' },
        { name: 'steps_attempted', value: 'Fitted a fresh paper filter' },
    ],
    ...overrides,
});

describe('parseRaisedTicket', () => {
    it('reads a ticket the approval seam pushed', () => {
        const ticket = parseRaisedTicket(raised());

        expect(ticket?.ticketId).toBe('SIM-223-0041');
        expect(ticket?.status).toBe('submitted');
        expect(ticket?.fields).toHaveLength(3);
    });

    it('keeps the rows in the order they arrived', () => {
        // TKT-001's order is the order the associate read the ticket back in
        // before approving it. A card that re-ordered them would be showing
        // them a different document from the one they approved.
        const ticket = parseRaisedTicket(raised());

        expect(ticket?.fields.map((field) => field.name)).toEqual([
            'ticket_id',
            'symptom',
            'steps_attempted',
        ]);
    });

    it('carries the attempted steps through untouched', () => {
        // The requirement, at the last seam it can be lost at.
        const ticket = parseRaisedTicket(raised());

        expect(
            ticket?.fields.find((field) => field.name === 'steps_attempted')?.value,
        ).toBe('Fitted a fresh paper filter');
    });

    it.each([null, undefined, 'a ticket', 42, []])(
        'refuses %s rather than rendering a partly-filled ticket',
        (payload) => {
            expect(parseRaisedTicket(payload)).toBeNull();
        },
    );

    it('refuses a ticket with no number', () => {
        // The number is issued by the confirmation. A card without one is a
        // card for a ticket that was never confirmed.
        expect(parseRaisedTicket(raised({ ticket_id: '' }))).toBeNull();
        expect(parseRaisedTicket(raised({ ticket_id: undefined }))).toBeNull();
    });

    it('refuses a ticket with no rows', () => {
        // A number with nothing under it reads as a ticket raised empty — a
        // claim about what a service desk received.
        expect(parseRaisedTicket(raised({ fields: [] }))).toBeNull();
        expect(parseRaisedTicket(raised({ fields: 'none' }))).toBeNull();
    });

    it('drops a row that names no field but keeps the ticket', () => {
        const ticket = parseRaisedTicket(
            raised({
                fields: [
                    { value: 'orphaned' },
                    { name: 'symptom', value: 'cold coffee' },
                ],
            }),
        );

        expect(ticket?.fields).toEqual([{ name: 'symptom', value: 'cold coffee' }]);
    });

    it('keeps a row whose value is empty', () => {
        // The backend writes "not reported" rather than leaving a field blank,
        // so an empty value is a payload this side should not have received —
        // but hiding the row would hide the field the associate is best placed
        // to notice is missing.
        const ticket = parseRaisedTicket(
            raised({ fields: [{ name: 'notes', value: '' }] }),
        );

        expect(ticket?.fields).toEqual([{ name: 'notes', value: '' }]);
    });
});

describe('parseTicketField', () => {
    it('reads a row', () => {
        expect(parseTicketField({ name: 'symptom', value: 'cold coffee' })).toEqual({
            name: 'symptom',
            value: 'cold coffee',
        });
    });

    it('refuses a row with no field name', () => {
        expect(parseTicketField({ value: 'cold coffee' })).toBeNull();
        expect(parseTicketField({ name: '   ', value: 'cold coffee' })).toBeNull();
    });

    it('never invents a value', () => {
        expect(parseTicketField({ name: 'notes' })?.value).toBe('');
    });
});
