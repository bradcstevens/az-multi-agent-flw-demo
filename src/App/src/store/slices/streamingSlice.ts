/**
 * Streaming Slice — the reply preview assembled from WebSocket deltas.
 */
import { createSlice, createSelector, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../store';
import { StreamingPlanUpdate } from '@/models';

export interface StreamingState {
    /** Streaming plan updates from WebSocket */
    streamingMessages: StreamingPlanUpdate[];
    /** The reply being progressively rendered in the conversation. */
    streamedReply: { agent: string; content: string } | null;
    /** Set only by the stream's explicit final delta. */
    isReplyComplete: boolean;
    /** The final reply to announce after the whole result supersedes the preview. */
    settledReply: string | null;
}

const initialState: StreamingState = {
    streamingMessages: [],
    streamedReply: null,
    isReplyComplete: false,
    settledReply: null,
};

const streamingSlice = createSlice({
    name: 'streaming',
    initialState,
    reducers: {
        setStreamingMessages(state, action: PayloadAction<StreamingPlanUpdate[]>) {
            state.streamingMessages = action.payload as any;
        },
        addStreamingMessage(state, action: PayloadAction<StreamingPlanUpdate>) {
            state.streamingMessages.push(action.payload as any);
        },
        restoreStreamedReply(state, action: PayloadAction<string>) {
            state.streamedReply = { agent: 'Assistant', content: action.payload };
            state.isReplyComplete = false;
            state.settledReply = null;
        },
        appendToStreamedReply(state, action: PayloadAction<{ agent: string; content: string }>) {
            const { agent, content } = action.payload;
            const current = state.streamedReply;
            state.streamedReply = {
                agent,
                content: current?.agent === agent && !state.isReplyComplete
                    ? current.content + content
                    : content,
            };
            state.isReplyComplete = false;
            state.settledReply = null;
        },
        completeStreamedReply(state) {
            state.isReplyComplete = true;
        },
        settleStreamedReply(state, action: PayloadAction<string>) {
            state.streamedReply = null;
            state.isReplyComplete = false;
            state.settledReply = action.payload;
        },
        clearStreamedReply(state) {
            state.streamedReply = null;
            state.isReplyComplete = false;
            state.settledReply = null;
        },
        resetStreaming() {
            return { ...initialState };
        },
    },
});

export const {
    setStreamingMessages,
    addStreamingMessage,
    restoreStreamedReply,
    appendToStreamedReply,
    completeStreamedReply,
    settleStreamedReply,
    clearStreamedReply,
    resetStreaming,
} = streamingSlice.actions;

/* ── Granular Selectors ───────────────────────────────────────── */
export const selectStreamingMessages = (s: RootState) => s.streaming.streamingMessages;
export const selectStreamedReply = (s: RootState) => s.streaming.streamedReply;
export const selectIsReplyComplete = (s: RootState) => s.streaming.isReplyComplete;
export const selectSettledReply = (s: RootState) => s.streaming.settledReply;

/* ── Memoized Derived Selectors ───────────────────────────────── */

/** Number of streaming messages (stable primitive — avoids child re-renders) */
export const selectStreamingMessageCount = createSelector(
    selectStreamingMessages,
    (messages) => messages.length,
);

/** Whether we have buffered content ready to display */
export const selectHasStreamedReply = createSelector(
    selectStreamedReply,
    (reply) => Boolean(reply?.content),
);

export default streamingSlice.reducer;
