/**
 * The Token meter's accumulator (issue #24, R7).
 *
 * R7's point is not "here is a bill". It is that **two billing models are
 * visibly not uniform**: a Foundry agent is billed in tokens, the Copilot
 * Studio agent is billed in Copilot Credits, and the identity boundary gate is
 * billed nothing at all. Putting them in one table with one number per row
 * would flatten exactly the distinction the panel exists to show, so a row
 * declares which meter it is on and leaves the other column empty.
 *
 * Empty means two different things and the meter keeps them apart:
 *
 * - `null` — **not reported**. Nobody told us. Rendered `—`.
 * - `0` — **known to be nothing**. Rendered `0`.
 *
 * That is #23's rule, carried into the pixels. A refused request adds nothing
 * to the meter, and the row that proves it only proves it if nothing is the
 * only thing that looks like nothing. If an unreported cost also rendered `0`,
 * the guardrail's zero would prove nothing at all.
 *
 * Pure, and separate from the Redux slice that holds it: this is the whole of
 * the meter's arithmetic and it is testable without a store or a socket.
 */

import { PolicyBlock } from '../api/policyBlock';
import { SourceUsed, TokenUsage } from './transparency';

/**
 * What one Copilot Studio generative answer costs.
 *
 * Microsoft Learn, [Billing rates and
 * management](https://learn.microsoft.com/microsoft-copilot-studio/requirements-messages-management):
 * a **generative answer is 2 Copilot Credits** (a classic answer is 1). The SOP
 * agent answers with `GenerativeAIRecognizer` over its uploaded Dataverse
 * documents, so every answer it gives is a generative answer.
 *
 * The panel labels this **estimated**, and it is one constant rather than a
 * number scattered through the render, because the rate is Microsoft's to
 * change and the demo's claim is only as good as its ability to be corrected.
 */
export const COPILOT_CREDITS_PER_GENERATIVE_ANSWER = 2;

/** The single row every identity-boundary refusal accumulates onto. */
export const GUARDRAIL_ROW_KEY = 'guardrail:identity_boundary';

/** How the store shows this row's name to the audience. */
export const GUARDRAIL_ROW_NAME = 'Identity boundary gate';

/** Which meter a row is on. */
export type MeterBilling = 'tokens' | 'credits' | 'refused';

export interface MeterRow {
    /** Stable identity: an executor id, a platform, or the guardrail. */
    key: string;
    agentName: string;
    billing: MeterBilling;
    /** How many times this row was reached. */
    calls: number;
    /** Tokens, or `null` where tokens are not the meter this row is on. */
    inputTokens: number | null;
    outputTokens: number | null;
    totalTokens: number | null;
    /** Copilot Credits, or `null` where credits are not this row's meter. */
    credits: number | null;
}

export interface MeterState {
    /** In the order each row first spent, so the table reads as a timeline. */
    rows: MeterRow[];
}

export const emptyMeter = (): MeterState => ({ rows: [] });

/** Replace one row, or append it, without mutating the state handed in. */
function upsert(
    state: MeterState,
    key: string,
    create: () => MeterRow,
    update: (row: MeterRow) => MeterRow,
): MeterState {
    const index = state.rows.findIndex((row) => row.key === key);
    if (index === -1) {
        return { rows: [...state.rows, update(create())] };
    }
    const rows = [...state.rows];
    rows[index] = update(rows[index]);
    return { rows };
}

/**
 * A Foundry executor reported what it spent.
 *
 * `credits` stays `null`: a Foundry agent is not billed in Copilot Credits, and
 * a `0` in that column would read as *this agent used the Copilot Studio meter
 * and used none of it*.
 */
export function recordTokenUsage(state: MeterState, usage: TokenUsage): MeterState {
    return upsert(
        state,
        usage.executorId,
        () => ({
            key: usage.executorId,
            agentName: usage.agentName,
            billing: 'tokens',
            calls: 0,
            inputTokens: 0,
            outputTokens: 0,
            totalTokens: 0,
            credits: null,
        }),
        (row) => ({
            ...row,
            agentName: usage.agentName || row.agentName,
            calls: row.calls + 1,
            inputTokens: (row.inputTokens ?? 0) + usage.inputTokens,
            outputTokens: (row.outputTokens ?? 0) + usage.outputTokens,
            totalTokens: (row.totalTokens ?? 0) + usage.totalTokens,
        }),
    );
}

/**
 * The cross-platform hop happened, so it cost Copilot Credits.
 *
 * The token columns stay `null` and are never zeroed. Direct Line reports no
 * token counts to us at all — Copilot Studio meters the answer, not the
 * tokens — so a `0` there would be the panel inventing a measurement.
 */
export function recordSourceUsed(state: MeterState, source: SourceUsed): MeterState {
    const key = `${source.platform}:${source.agentName}`;
    return upsert(
        state,
        key,
        () => ({
            key,
            agentName: source.agentName || source.platform,
            billing: 'credits',
            calls: 0,
            inputTokens: null,
            outputTokens: null,
            totalTokens: null,
            credits: 0,
        }),
        (row) => ({
            ...row,
            calls: row.calls + 1,
            credits: (row.credits ?? 0) + COPILOT_CREDITS_PER_GENERATIVE_ANSWER,
        }),
    );
}

/**
 * The Identity boundary gate refused a request (ADR-014).
 *
 * This is the one row whose zeros are **measurements**. The gate is
 * deterministic code in the request path, executed before the lane router and
 * before orchestration, so when it refuses no agent runs, no orchestrator turn
 * is taken and no Copilot Studio answer is generated: nothing on either meter,
 * known rather than merely unreported.
 *
 * (The gate's own embedding-similarity tier is a model call, and a small one;
 * it is not an agent and does not appear on this table. The panel says which
 * zero this is.)
 */
export function recordPolicyBlock(state: MeterState, _block: PolicyBlock): MeterState {
    return upsert(
        state,
        GUARDRAIL_ROW_KEY,
        () => ({
            key: GUARDRAIL_ROW_KEY,
            agentName: GUARDRAIL_ROW_NAME,
            billing: 'refused',
            calls: 0,
            inputTokens: 0,
            outputTokens: 0,
            totalTokens: 0,
            credits: 0,
        }),
        (row) => ({ ...row, calls: row.calls + 1 }),
    );
}
