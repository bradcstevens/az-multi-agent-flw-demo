import { describe, it, expect } from 'vitest';

import reducer, {
    presenterAlertReceived,
    refusalRecorded,
    sourceUsedReceived,
    tokenUsageReceived,
    transparencyReset,
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

    it('clears every panel when a new conversation starts', () => {
        let state = reducer(initial(), sourceUsedReceived(sourceUsed));
        state = reducer(state, tokenUsageReceived(tokenUsage));
        state = reducer(state, presenterAlertReceived(alert));

        state = reducer(state, transparencyReset());

        expect(state).toEqual(initial());
    });

    it('keeps the meter when only the conversation moved on', () => {
        // The meter is the walkthrough's running total — a refusal on the home
        // surface has to still be on it when the next question is answered on
        // the plan surface, or the guardrail's zero is never seen beside a cost.
        let state = reducer(
            initial(),
            refusalRecorded({ kind: 'policy_block', code: 'identity_boundary', message: 'no' }),
        );
        state = reducer(state, tokenUsageReceived(tokenUsage));

        expect(state.meter.rows).toHaveLength(2);
    });
});
