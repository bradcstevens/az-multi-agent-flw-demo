/**
 * Chat Slice — user input, submission state, agent messages,
 * and clarification handling.
 */
import { createSlice, createSelector, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../store';
import { AgentMessageData, ParsedUserClarification } from '@/models';

export interface ChatState {
    /** Current chat input value */
    input: string;
    /**
     * Disable the input while a submission is in flight.
     *
     * Exactly that, since #77. It began `true` and was released only when a
     * **Clarification** arrived, which made it a second, quieter answer to
     * *may the box be used at all* — and that answer only ever agreed with
     * `turnModeFor`'s by coincidence. **Resume** removes the coincidence: a
     * chat nobody is waiting on is one a turn can be typed into, so a lock
     * that defaults closed would leave the box permanently shut with a
     * placeholder inviting a question.
     */
    submittingChatDisableInput: boolean;
    /** Clarification request from the backend */
    clarificationMessage: ParsedUserClarification | null;
    /** All agent messages rendered in the chat panel */
    agentMessages: AgentMessageData[];
}

const initialState: ChatState = {
    input: '',
    // Nothing is in flight on a page that has just loaded (#77, ADR-027).
    submittingChatDisableInput: false,
    clarificationMessage: null,
    agentMessages: [],
};

const chatSlice = createSlice({
    name: 'chat',
    initialState,
    reducers: {
        setInput(state, action: PayloadAction<string>) {
            state.input = action.payload;
        },
        setSubmittingChatDisableInput(state, action: PayloadAction<boolean>) {
            state.submittingChatDisableInput = action.payload;
        },
        setClarificationMessage(state, action: PayloadAction<ParsedUserClarification | null>) {
            state.clarificationMessage = action.payload as any;
        },
        /**
         * The associate answered — but only the question they answered is
         * settled (#68).
         *
         * Clearing whatever happens to be stored would let a POST that has
         * been in flight since the previous question retire the one now on
         * screen, closing the box while the backend waits on it.
         */
        clarificationAnswered(state, action: PayloadAction<string>) {
            if (state.clarificationMessage?.request_id === action.payload) {
                state.clarificationMessage = null;
            }
        },
        setAgentMessages(state, action: PayloadAction<AgentMessageData[]>) {
            state.agentMessages = action.payload as any;
        },
        addAgentMessage(state, action: PayloadAction<AgentMessageData>) {
            state.agentMessages.push(action.payload as any);
        },
        /** Reset chat state (used when navigating to a new plan) */
        resetChat() {
            return { ...initialState };
        },
    },
});

export const {
    setInput,
    setSubmittingChatDisableInput,
    setClarificationMessage,
    clarificationAnswered,
    setAgentMessages,
    addAgentMessage,
    resetChat,
} = chatSlice.actions;

/* ── Granular Selectors ───────────────────────────────────────── */
export const selectInput = (s: RootState) => s.chat.input;
export const selectSubmittingChatDisable = (s: RootState) => s.chat.submittingChatDisableInput;
export const selectClarificationMessage = (s: RootState) => s.chat.clarificationMessage;
export const selectAgentMessages = (s: RootState) => s.chat.agentMessages;

/* ── Memoized Derived Selectors ───────────────────────────────── */

/**
 * The `request_id` of the clarification this surface can answer, or `null` if
 * there is none (#68).
 *
 * One claim, read in one place: what makes the box available and what the
 * answer is posted against have to be the same thing. They were two — the
 * in-flight lock decided availability and the payload defaulted a missing
 * identifier to `''` — so a submit reaching the path outside a clarification
 * posted a request answering nothing. A question carrying no identifier is not
 * one this surface can answer, so it is not pending either.
 */
export const selectPendingClarificationRequestId = createSelector(
    selectClarificationMessage,
    (msg) => {
        const requestId = msg?.request_id?.trim();
        return requestId ? requestId : null;
    },
);

/** Number of agent messages (avoids re-render on array identity change when count is same) */
export const selectAgentMessageCount = createSelector(
    selectAgentMessages,
    (messages) => messages.length,
);

/** Whether a clarification is currently pending */
export const selectHasPendingClarification = createSelector(
    selectPendingClarificationRequestId,
    (requestId) => requestId !== null,
);

export default chatSlice.reducer;
