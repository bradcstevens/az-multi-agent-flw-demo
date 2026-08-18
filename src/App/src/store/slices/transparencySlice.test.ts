import { describe, it, expect } from 'vitest';

import reducer, {
    conversationStarted,
    presenterAlertReceived,
    refusalRecorded,
    requestStarted,
    sourceUsedReceived,
    transparencyRailToggled,
    tokenUsageReceived,
} from './transparencySlice';
import { COPILOT_CREDITS_PER_GENERATIVE_ANSWER, GUARDRAIL_ROW_KEY } from '../../models/meter';

/**
 * The panels, driven from the WebSocket message contract.
 *
 * Every payload here is what `send_status_update_async` puts on the wire as
 * `data`, so this suite fails if the backend's payload shape and the frontend's
 * reading of it ever drift apart.
 */
const sourceUsed = {
    platform: 'Copilot Studio',
    source: 'Dataverse',
    agent_name: 'Store SOP Assistant',
    conversation_id: 'abc123',
    citations: [
        { position: 1, name: 'SOP-102 Store Closing Procedure.docx', snippet: 'Cash up…', url: null },
    ],
};

const tokenUsage = {
    agent_name: 'Shift Tasks Agent',
    executor_id: 'shift_tasks_agent',
    input_tokens: 900,
    output_tokens: 100,
    total_tokens: 1000,
};

const alert = {
    title: 'Shift task due',
    content: 'The coffee station deep clean is due before the 15:00 handover.',
    timestamp: '2026-08-13T09:00:00+00:00',
};

const initial = () => reducer(undefined, { type: '@@init' });

describe('the transparency slice', () => {
    it('starts with every panel claiming nothing', () => {
        const state = initial();

        expect(state.source).toBeNull();
        expect(state.meter.rows).toEqual([]);
        expect(state.alerts).toEqual([]);
    });

    it('lights the Grounding panel from a source_used payload', () => {
        const state = reducer(initial(), sourceUsedReceived(sourceUsed));

        expect(state.source?.platform).toBe('Copilot Studio');
        expect(state.source?.citations).toHaveLength(1);
    });

    it('bills the same source_used to the meter in Copilot Credits', () => {
        const state = reducer(initial(), sourceUsedReceived(sourceUsed));

        expect(state.meter.rows).toHaveLength(1);
        expect(state.meter.rows[0].credits).toBe(COPILOT_CREDITS_PER_GENERATIVE_ANSWER);
        expect(state.meter.rows[0].totalTokens).toBeNull();
    });

    it('accumulates token_usage per agent across turns', () => {
        let state = reducer(initial(), tokenUsageReceived(tokenUsage));
        state = reducer(state, tokenUsageReceived(tokenUsage));

        expect(state.meter.rows).toHaveLength(1);
        expect(state.meter.rows[0].calls).toBe(2);
        expect(state.meter.rows[0].totalTokens).toBe(2000);
    });

    it('adds a refused request to the meter as a zero, and to nothing else', () => {
        const state = reducer(
            initial(),
            refusalRecorded({
                kind: 'policy_block',
                code: 'identity_boundary',
                message: 'refused',
            }),
        );

        expect(state.meter.rows[0].key).toBe(GUARDRAIL_ROW_KEY);
        expect(state.meter.rows[0].totalTokens).toBe(0);
        // A refusal is not an answer, so it lights no Grounding panel.
        expect(state.source).toBeNull();
    });

    it('keeps alerts apart from every other signal', () => {
        const state = reducer(initial(), presenterAlertReceived(alert));

        expect(state.alerts).toHaveLength(1);
        expect(state.alerts[0].title).toBe('Shift task due');
        expect(state.meter.rows).toEqual([]);
    });

    it('ignores a payload it cannot read rather than rendering a half of one', () => {
        let state = reducer(initial(), sourceUsedReceived({ source: 'Dataverse' }));
        state = reducer(state, tokenUsageReceived({ total_tokens: 'lots' }));
        state = reducer(state, presenterAlertReceived({ title: 'Shift task due' }));

        expect(state.source).toBeNull();
        expect(state.meter.rows).toEqual([]);
        expect(state.alerts).toEqual([]);
    });

    it('takes the Grounding panel dark when the next question is asked', () => {
        // The panel's claim is about *one answer*. A troubleshooting question
        // answered inside Foundry emits no source_used at all, so leaving the
        // previous SOP hop on screen credits Copilot Studio with an answer it
        // never gave — the exact lie the whole feature is shaped to refuse.
        let state = reducer(initial(), sourceUsedReceived(sourceUsed));
        state = reducer(state, tokenUsageReceived(tokenUsage));

        state = reducer(state, requestStarted());

        expect(state.source).toBeNull();
        // The meter is the walkthrough's running total and survives.
        expect(state.meter.rows).toHaveLength(2);
    });

    it('keeps alerts up across a request, because an alert answered no question', () => {
        let state = reducer(initial(), presenterAlertReceived(alert));

        state = reducer(state, requestStarted());

        expect(state.alerts).toHaveLength(1);
    });

    it('clears provenance and alerts on a new conversation, and keeps the meter', () => {
        let state = reducer(initial(), sourceUsedReceived(sourceUsed));
        state = reducer(state, tokenUsageReceived(tokenUsage));
        state = reducer(state, presenterAlertReceived(alert));

        state = reducer(state, conversationStarted('session-next'));

        expect(state.source).toBeNull();
        expect(state.alerts).toEqual([]);
        expect(state.meter.rows).toHaveLength(2);
    });

    it('keeps the meter when only the conversation moved on', () => {
        // The meter is the walkthrough's running total — a refusal on the home
        // surface has to still be on it when the next question is answered on
        // the chat surface, or the guardrail's zero is never seen beside a cost.
        let state = reducer(
            initial(),
            refusalRecorded({ kind: 'policy_block', code: 'identity_boundary', message: 'no' }),
        );
        state = reducer(state, tokenUsageReceived(tokenUsage));

        expect(state.meter.rows).toHaveLength(2);
    });

    it('opens the transparency rail by default, and closes and reopens it on request', () => {
        // Default expanded, because collapsed-by-default would silently reverse
        // #79's roster-before-a-question-is-typed (ADR-035).
        expect(initial().railExpanded).toBe(true);

        const closed = reducer(initial(), transparencyRailToggled());
        expect(closed.railExpanded).toBe(false);

        expect(reducer(closed, transparencyRailToggled()).railExpanded).toBe(true);
    });

    it('opens a closed, unpinned rail on the first Source used of a conversation', () => {
        const closed = reducer(initial(), transparencyRailToggled());
        const nextConversation = reducer(closed, conversationStarted('session-next'));

        const state = reducer(nextConversation, sourceUsedReceived(sourceUsed));

        expect(state.source).not.toBeNull();
        expect(state.railExpanded).toBe(true);
    });

    it('does not move the rail again on later Source used signals in the same conversation', () => {
        const first = reducer(initial(), sourceUsedReceived(sourceUsed));
        const second = reducer(
            first,
            sourceUsedReceived({
                ...sourceUsed,
                agent_name: 'Another specialist',
            }),
        );

        expect(first.railExpanded).toBe(true);
        expect(second.railExpanded).toBe(true);
        expect(second.railSourceUsed).toBe(true);
    });

    it('pins the rail after a presenter touch, so Source used cannot change it', () => {
        const closed = reducer(initial(), transparencyRailToggled());
        const state = reducer(closed, sourceUsedReceived(sourceUsed));

        expect(closed.railPinned).toBe(true);
        expect(state.railExpanded).toBe(false);
        expect(state.railSourceUsed).toBe(true);
    });

    it('clears the pin only when the next conversation starts', () => {
        const pinned = reducer(initial(), transparencyRailToggled());
        const duringRequest = reducer(pinned, requestStarted());
        const nextConversation = reducer(duringRequest, conversationStarted('session-next'));

        expect(duringRequest.railPinned).toBe(true);
        expect(nextConversation.railPinned).toBe(false);
        expect(nextConversation.railExpanded).toBe(false);
        expect(nextConversation.railSourceUsed).toBe(false);
    });

    it('keeps the pin across another Plan in the same Chat', () => {
        const pinned = reducer(initial(), transparencyRailToggled());
        const state = {
            ...pinned,
            conversationId: 'session-223',
        };

        const nextPlan = reducer(state, {
            type: conversationStarted.type,
            payload: 'session-223',
        });

        expect(nextPlan.railPinned).toBe(true);
        expect(nextPlan.railExpanded).toBe(false);
    });
});
