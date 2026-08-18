/**
 * The **Progress narration**'s phase (issue #64, ADR-023).
 *
 * One slice, and it survives the navigation from the home surface to the plan
 * page, because that navigation is the seam the story used to run backwards
 * across: `HomeInput` toasted *"Plan created — Fast lane"* and then `PlanPage`
 * mounted and said *"Loading plan data..."* over *"Initializing AI agents..."*.
 * Two independent narrations cannot enforce monotonicity — across two
 * components "only advances" is a coincidence, not a property — so the phase is
 * held in one place and `advancesTo` is the only way it moves.
 *
 * Every reducer here is named for the **signal** that reports it, not for the
 * words it produces. The words are `progressNarration.ts`'s.
 */
import { createSelector, createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../store';
import { Lane } from '@/models/lane';
import { advancesTo, narrate, RequestPhase } from '@/models/progressNarration';
import { planApprovalAccepted } from './planSlice';

export interface ProgressState {
    phase: RequestPhase;
    /**
     * The plan this narration is about, once the response has named one.
     *
     * Not for display — it is what stops a request in flight narrating over an
     * earlier conversation the presenter opened from the left panel.
     */
    planId: string | null;
    lane: Lane | null;
    executor: string | null;
    /** The next Person step the approved plan is waiting on. */
    waitingOn: string | null;
    /** Executors that have spoken in the answer the surface is currently showing. */
    participatingExecutors: string[];
}

const initialState: ProgressState = {
    phase: 'idle',
    planId: null,
    lane: null,
    executor: null,
    waitingOn: null,
    participatingExecutors: [],
};

const progressSlice = createSlice({
    name: 'progress',
    initialState,
    reducers: {
        /**
         * A question has been submitted and the `createPlan` POST is in flight.
         *
         * The one reducer that does **not** advance: a new question is a new
         * request, not a step backwards through the old one.
         */
        requestSent(state, action: PayloadAction<string | undefined>) {
            state.phase = 'sent';
            state.planId = action.payload ?? null;
            state.lane = null;
            state.executor = null;
            state.waitingOn = null;
            state.participatingExecutors = [];
        },
        /**
         * The `createPlan` response came back, naming the plan and — usually —
         * the lane it was routed into.
         *
         * The lane is optional because the router failing to report one is not
         * the router reporting `fast`. The plan is recorded either way: without
         * it the narration is reset by the very navigation it caused, and the
         * surface falls silent on a request that is still in flight.
         */
        requestRouted(
            state,
            action: PayloadAction<{ lane?: Lane | null; planId?: string | null }>,
        ) {
            if (action.payload.lane) state.lane = action.payload.lane;
            if (action.payload.planId) state.planId = action.payload.planId;
            if (advancesTo(state.phase, 'routed')) state.phase = 'routed';
        },
        /** `connection_status`. Plumbing — it moves the phase and says nothing. */
        socketConnected(state) {
            if (advancesTo(state.phase, 'connected')) state.phase = 'connected';
        },
        /** `agent_message_streaming`, which carries the executor's own name. */
        agentResponding(state, action: PayloadAction<string | null | undefined>) {
            if (state.phase === 'done') return;
            const executor = action.payload?.trim() || null;
            state.executor = executor;
            if (executor && !state.participatingExecutors.includes(executor)) {
                state.participatingExecutors.push(executor);
            }
            state.phase = 'working';
        },
        /** The approved Reviewable plan names the Person step still unresolved. */
        waitingOnPerson(state, action: PayloadAction<string | null | undefined>) {
            const person = action.payload?.trim() || null;
            if (!person || state.phase === 'done') return;
            state.waitingOn = person;
            state.phase = 'waiting';
        },
        /**
         * The plan, or the answer, or the error — the request is no longer in
         * flight and the surface stops saying that it is.
         */
        requestSettled(state) {
            state.phase = 'done';
            state.waitingOn = null;
        },
        /**
         * The chat page opened a conversation.
         *
         * A no-op for the plan this narration is already about, which is how it
         * survives the navigation it caused. Any other plan is somebody else's
         * conversation and this narration has nothing true to say about it.
         */
        planOpened(state, action: PayloadAction<string | undefined>) {
            if (state.planId && state.planId === action.payload) return;
            return { ...initialState };
        },
    },
    extraReducers: (builder) => {
        /**
         * The associate approved the plan, so a second request is in flight.
         *
         * Read off the plan slice's own action rather than dispatched beside
         * it, for this slice's whole reason for existing: an approval that
         * narrated only when the chat page remembered to say so is a second
         * place to disagree about whether a request is in flight. It re-arms
         * rather than advances — an approval is a new request, and the phase
         * bound is within a request.
         */
        builder.addCase(planApprovalAccepted, (state) => {
            state.phase = 'sent';
            state.executor = null;
            state.waitingOn = null;
            state.participatingExecutors = [];
        });
    },
});

export const {
    requestSent,
    requestRouted,
    socketConnected,
    agentResponding,
    waitingOnPerson,
    requestSettled,
    planOpened,
} = progressSlice.actions;

export const selectRequestPhase = (s: RootState) => s.progress.phase;
export const selectRoutedLane = (s: RootState) => s.progress.lane;
export const selectRespondingExecutor = (s: RootState) => s.progress.executor;
export const selectWaitingOnPerson = (s: RootState) => s.progress.waitingOn;
export const selectParticipatingExecutors = (s: RootState) => s.progress.participatingExecutors;

/** What the surface says right now, or `null` for say nothing. */
export const selectProgressNarration = createSelector(
    selectRequestPhase,
    selectRoutedLane,
    selectRespondingExecutor,
    selectWaitingOnPerson,
    (phase, lane, executor, waitingOn) => narrate({ phase, lane, executor, waitingOn }),
);

/**
 * Whether a request is still in flight.
 *
 * The one predicate every in-flight indicator on the surface is gated on, so
 * that "the narration stops" is a single fact rather than a habit each
 * component has to remember (#69).
 */
export const selectRequestInFlight = createSelector(
    selectProgressNarration,
    (narration) => narration !== null,
);

export default progressSlice.reducer;
