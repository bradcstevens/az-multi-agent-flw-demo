import { describe, it, expect } from 'vitest';

import {
    COPILOT_CREDITS_PER_GENERATIVE_ANSWER,
    GUARDRAIL_ROW_KEY,
    emptyMeter,
    recordPolicyBlock,
    recordSourceUsed,
    recordTokenUsage,
} from './meter';
import { parseSourceUsed, parseTokenUsage } from './transparency';

const usage = (executorId: string, input: number, output: number) =>
    parseTokenUsage({
        agent_name: executorId,
        executor_id: executorId,
        input_tokens: input,
        output_tokens: output,
        total_tokens: input + output,
    })!;

const sopAnswer = () =>
    parseSourceUsed({
        platform: 'Copilot Studio',
        source: 'Dataverse',
        agent_name: 'Store SOP Assistant',
        citations: [],
    })!;

describe('the meter', () => {
    it('starts with nothing on it', () => {
        expect(emptyMeter().rows).toEqual([]);
    });

    it('accumulates tokens and calls per agent', () => {
        let meter = emptyMeter();
        meter = recordTokenUsage(meter, usage('troubleshooting_agent', 1000, 200));
        meter = recordTokenUsage(meter, usage('troubleshooting_agent', 500, 100));

        expect(meter.rows).toHaveLength(1);
        const [row] = meter.rows;
        expect(row.calls).toBe(2);
        expect(row.inputTokens).toBe(1500);
        expect(row.outputTokens).toBe(300);
        expect(row.totalTokens).toBe(1800);
    });

    it('keeps agents apart and in the order they first spent', () => {
        let meter = emptyMeter();
        meter = recordTokenUsage(meter, usage('orchestrator', 10, 5));
        meter = recordTokenUsage(meter, usage('shift_tasks_agent', 20, 5));
        meter = recordTokenUsage(meter, usage('orchestrator', 10, 5));

        expect(meter.rows.map((row) => row.key)).toEqual(['orchestrator', 'shift_tasks_agent']);
        expect(meter.rows[0].calls).toBe(2);
        expect(meter.rows[1].calls).toBe(1);
    });

    it('bills the Copilot Studio hop in Copilot Credits, not tokens', () => {
        const meter = recordSourceUsed(emptyMeter(), sopAnswer());

        expect(meter.rows).toHaveLength(1);
        const [row] = meter.rows;
        expect(row.billing).toBe('credits');
        expect(row.calls).toBe(1);
        expect(row.credits).toBe(COPILOT_CREDITS_PER_GENERATIVE_ANSWER);
    });

    it('reports no token count for the Copilot Studio hop — Direct Line reports none', () => {
        const meter = recordSourceUsed(emptyMeter(), sopAnswer());

        // Not zero. A zero here would claim the hop cost no tokens, which is a
        // claim about Copilot Studio's meter that nothing on this wire supports.
        expect(meter.rows[0].totalTokens).toBeNull();
    });

    it('reports no credits for a Foundry agent — it is not billed that way', () => {
        const meter = recordTokenUsage(emptyMeter(), usage('orchestrator', 10, 5));

        expect(meter.rows[0].credits).toBeNull();
        expect(meter.rows[0].billing).toBe('tokens');
    });

    it('accumulates a second Copilot Studio answer onto the same row', () => {
        let meter = recordSourceUsed(emptyMeter(), sopAnswer());
        meter = recordSourceUsed(meter, sopAnswer());

        expect(meter.rows).toHaveLength(1);
        expect(meter.rows[0].calls).toBe(2);
        expect(meter.rows[0].credits).toBe(2 * COPILOT_CREDITS_PER_GENERATIVE_ANSWER);
    });

    it('records a refusal as a real zero — nothing ran, and we know it', () => {
        const meter = recordPolicyBlock(emptyMeter(), {
            kind: 'policy_block',
            code: 'identity_boundary',
            message: 'This assistant is set up for Store 223…',
        });

        expect(meter.rows).toHaveLength(1);
        const [row] = meter.rows;
        expect(row.key).toBe(GUARDRAIL_ROW_KEY);
        expect(row.billing).toBe('refused');
        expect(row.calls).toBe(1);
        expect(row.totalTokens).toBe(0);
        expect(row.credits).toBe(0);
    });

    it('keeps the refusal row apart from every agent that did spend', () => {
        let meter = emptyMeter();
        meter = recordTokenUsage(meter, usage('orchestrator', 10, 5));
        meter = recordPolicyBlock(meter, {
            kind: 'policy_block',
            code: 'identity_boundary',
            message: 'refused',
        });
        meter = recordPolicyBlock(meter, {
            kind: 'policy_block',
            code: 'identity_boundary',
            message: 'refused again',
        });

        expect(meter.rows).toHaveLength(2);
        expect(meter.rows[1].calls).toBe(2);
        expect(meter.rows[1].totalTokens).toBe(0);
        expect(meter.rows[0].totalTokens).toBe(15);
    });

    it('never mutates the meter it was handed', () => {
        const before = recordTokenUsage(emptyMeter(), usage('orchestrator', 10, 5));
        const after = recordTokenUsage(before, usage('orchestrator', 10, 5));

        expect(before.rows[0].calls).toBe(1);
        expect(after).not.toBe(before);
    });
});
