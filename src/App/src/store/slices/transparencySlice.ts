/**
 * Transparency Slice — the three signals the panels render (issue #24).
 *
 * The parsing happens **here**, at the reducer, rather than in the subscription
 * that dispatches: it makes the whole contract between the backend's payloads
 * and the panels testable without a socket, a store provider or a rendered
 * page, and it means an unreadable payload is dropped in exactly one place.
 *
 * A payload that cannot be read is **ignored**, not partly applied. #23's rule
 * about what a surface may claim survives only if the browser refuses the same
 * things the backend refused to send.
 */
import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../store';

import { PolicyBlock } from '@/api/policyBlock';
import {
    MeterState,
    emptyMeter,
    recordPolicyBlock,
    recordSourceUsed,
    recordTokenUsage,
} from '@/models/meter';
import {
    PresenterAlert,
    SourceUsed,
    parsePresenterAlert,
    parseSourceUsed,
    parseTokenUsage,
} from '@/models/transparency';

export interface TransparencyState {
    /** The most recent cross-platform hop, for the Grounding panel. */
    source: SourceUsed | null;
    /** The running total for the Token meter, across the whole walkthrough. */
    meter: MeterState;
    /** Proactive alerts, which are never replies. */
    alerts: PresenterAlert[];
}

const initialState: TransparencyState = {
    source: null,
    meter: emptyMeter(),
    alerts: [],
};

const transparencySlice = createSlice({
    name: 'transparency',
    initialState,
    reducers: {
        /** `WebsocketMessageType.SOURCE_USED` — lights R6 and bills R7. */
        sourceUsedReceived(state, action: PayloadAction<unknown>) {
            const source = parseSourceUsed(action.payload);
            if (!source) return;
            state.source = source;
            state.meter = recordSourceUsed(state.meter, source);
        },
        /** `WebsocketMessageType.TOKEN_USAGE` — one executor's reported cost. */
        tokenUsageReceived(state, action: PayloadAction<unknown>) {
            const usage = parseTokenUsage(action.payload);
            if (!usage) return;
            state.meter = recordTokenUsage(state.meter, usage);
        },
        /** `WebsocketMessageType.PRESENTER_ALERT` — R8's proactive message. */
        presenterAlertReceived(state, action: PayloadAction<unknown>) {
            const alert = parsePresenterAlert(action.payload);
            if (!alert) return;
            state.alerts.push(alert);
        },
        /**
         * The Identity boundary gate refused a request.
         *
         * Not a WebSocket signal: the refusal is an HTTP 403 on the submission
         * itself (ADR-014), so it is recorded where it is caught. It reaches
         * the meter and nothing else — a refusal is not an answer and lights no
         * Grounding panel.
         */
        refusalRecorded(state, action: PayloadAction<PolicyBlock>) {
            state.meter = recordPolicyBlock(state.meter, action.payload);
        },
        /**
         * A new question was asked.
         *
         * The Grounding panel's claim is about **one answer** — *this* one left
         * Foundry — so it goes dark the moment the next question is in flight.
         * A troubleshooting question answered inside Foundry emits no
         * `source_used` at all, and leaving the previous hop on screen would
         * credit Copilot Studio on stage with an answer it never gave.
         *
         * Alerts survive: an alert answered no question, so a new question does
         * not make it untrue. The meter survives because it is the
         * walkthrough's running total, not this request's.
         */
        requestStarted(state) {
            state.source = null;
        },
        /**
         * A new conversation started.
         *
         * Everything scoped to the previous conversation goes — provenance and
         * the alerts pushed into it — but **not** the meter. The refusal
         * happens on the home surface and the answers happen on the plan
         * surface, so a meter cleared at the conversation boundary would never
         * show the guardrail's zero beside a row that cost something.
         */
        conversationStarted(state) {
            state.source = null;
            state.alerts = [];
        },
        /** A new conversation, and every panel back to claiming nothing. */
        transparencyReset() {
            return { source: null, meter: emptyMeter(), alerts: [] };
        },
    },
});

export const {
    sourceUsedReceived,
    tokenUsageReceived,
    presenterAlertReceived,
    refusalRecorded,
    requestStarted,
    conversationStarted,
    transparencyReset,
} = transparencySlice.actions;

export const selectGroundingSource = (state: RootState): SourceUsed | null =>
    state.transparency.source;
export const selectMeter = (state: RootState): MeterState => state.transparency.meter;
export const selectPresenterAlerts = (state: RootState): PresenterAlert[] =>
    state.transparency.alerts;

export default transparencySlice.reducer;
