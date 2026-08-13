/**
 * Ticket Slice — the Simulated ticket the associate raised (issue #22).
 *
 * A slice of its own rather than a corner of the transparency slice. The
 * transparency panels are an argument being made to an audience about how the
 * architecture works; a ticket is a record of something that happened to the
 * store. They clear on different boundaries and they mean different things.
 *
 * But the **conversation boundary is shared**, and this slice listens for the
 * transparency slice's `conversationStarted` rather than declaring one of its
 * own. That boundary is already dispatched from more than one place — the
 * `planId` effect and `resetPlanVariables` — and a second action to dispatch
 * beside it is a second thing to forget at one of them, which would leave one
 * conversation's ticket on the next conversation's screen.
 *
 * `requestStarted` is deliberately **not** honoured. A raised ticket is not a
 * claim about the question in flight: asking another one does not unraise it,
 * the same reasoning the presenter alerts survive a new question on.
 */
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

import type { RootState } from '../store';
import { RaisedTicket, parseRaisedTicket } from '@/models/ticket';
import { conversationStarted } from './transparencySlice';

export interface TicketState {
    /** The ticket this conversation raised, if it raised one. */
    ticket: RaisedTicket | null;
}

const initialState: TicketState = { ticket: null };

const ticketSlice = createSlice({
    name: 'ticket',
    initialState,
    reducers: {
        /**
         * `WebsocketMessageType.TICKET_RAISED` — the plan approval confirmed a
         * ticket and the container took it.
         *
         * An unreadable payload is dropped rather than partly applied. The
         * backend only pushes this after a successful write, so a card on
         * screen is evidence of a stored ticket; a card assembled from a
         * payload this side could not read would not be.
         */
        ticketRaised(state, action: PayloadAction<unknown>) {
            const ticket = parseRaisedTicket(action.payload);
            if (!ticket) return;
            state.ticket = ticket;
        },
        /** Every surface back to claiming nothing. */
        ticketReset() {
            return { ticket: null };
        },
    },
    extraReducers: (builder) => {
        builder.addCase(conversationStarted, () => ({ ticket: null }));
    },
});

export const { ticketRaised, ticketReset } = ticketSlice.actions;

export const selectRaisedTicket = (state: RootState): RaisedTicket | null =>
    state.ticket.ticket;

export default ticketSlice.reducer;
