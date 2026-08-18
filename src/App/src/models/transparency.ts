/**
 * The three transparency signals, as they arrive in the browser (issue #24).
 *
 * The backend's `src/backend/transparency/payloads.py` decides what each signal
 * may claim; this file is the same contract read from the other end of the
 * socket. It carries the rule across with it: **a surface may say nothing, but
 * it may not say something that is not so.** So every parser here is total and
 * returns `null` rather than a partly-filled object — the same convention
 * `parsePolicyBlock` follows, and for the same reason. A panel with nothing to
 * render goes dark; a panel rendering a number nobody sent is a lie told to a
 * customer in a room.
 *
 * Counts especially are never defaulted to zero. #23's emission rule is that no
 * usage reported means no event at all, because a zero on the meter reads as
 * *this agent was free*. Defaulting here would reintroduce exactly the zero the
 * backend refused to send.
 */

/** One cited document, as `/sop/ask` puts it on the `source_used` payload. */
export interface SourceCitation {
    position: number;
    name: string;
    /** Truncated from the citation's `text`; see CONTEXT.md, "Citation appearance". */
    snippet: string;
    /** Always null for a Dataverse-uploaded document (ADR-011, confirmed #17). */
    url: string | null;
}

/**
 * Which platform answered, and out of what (R6).
 *
 * Carries `platform` and not only `source`: "Dataverse" alone does not
 * distinguish the cross-platform hop from any other retrieval, and the claim
 * the Grounding panel exists to make is that *this one answer left Foundry*.
 */
export interface SourceUsed {
    platform: string;
    source: string;
    agentName: string;
    /** Query received from the Foundry orchestration tool call. */
    toolQuery: string;
    /** Query used to retrieve from the SOP corpus. */
    retrievalQuery: string;
    citations: SourceCitation[];
    conversationId: string | null;
}

/** One executor's reported token cost (R7). */
export interface TokenUsage {
    agentName: string;
    executorId: string;
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
}

/** A proactive shift-task message that answers nothing (R8). */
export interface PresenterAlert {
    title: string;
    content: string;
    timestamp: string;
    provenance: string;
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
    value !== null && typeof value === 'object' && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : null;

const asText = (value: unknown): string => (typeof value === 'string' ? value : '');

/** A count, or null. Never a zero standing in for "we were not told". */
const asCount = (value: unknown): number | null =>
    typeof value === 'number' && Number.isFinite(value) ? value : null;

/**
 * One cited document, or null if it carries nothing to show.
 *
 * A citation with **no name** is kept. `citations_from_activity` emits
 * `name: ""` when the appearance metadata has none, and discarding it would
 * empty the citation list — which the panel renders as *found no matching
 * procedure*. That converts a document the hop actually returned into an honest
 * miss that did not happen. Only a citation with neither a name nor a snippet
 * is dropped: there is nothing there to render, and nothing is what it gets.
 */
const parseCitation = (value: unknown, index: number): SourceCitation | null => {
    const raw = asRecord(value);
    if (!raw) return null;

    const name = asText(raw.name);
    const snippet = asText(raw.snippet);
    if (!name && !snippet) return null;

    return {
        position: asCount(raw.position) ?? index + 1,
        name,
        snippet,
        url: typeof raw.url === 'string' && raw.url ? raw.url : null,
    };
};

/**
 * Read a `source_used` payload, or return null.
 *
 * A payload naming **no platform** is refused: the panel only ever claims a
 * platform it was told about. An empty citation list is *not* refused — that is
 * the rehearsed out-of-corpus probe, where the hop happened and nothing came
 * back, and deleting it would delete the honest miss.
 */
export function parseSourceUsed(data: unknown): SourceUsed | null {
    const raw = asRecord(data);
    if (!raw) return null;

    const platform = asText(raw.platform);
    if (!platform) return null;

    const citations = Array.isArray(raw.citations)
        ? raw.citations
              .map(parseCitation)
              .filter((citation): citation is SourceCitation => citation !== null)
        : [];

    return {
        platform,
        source: asText(raw.source),
        agentName: asText(raw.agent_name),
        toolQuery: asText(raw.tool_query),
        retrievalQuery: asText(raw.retrieval_query),
        citations,
        conversationId: typeof raw.conversation_id === 'string' ? raw.conversation_id : null,
    };
}

/**
 * Read a `token_usage` payload, or return null.
 *
 * Refused without an `executor_id`, because a cost the meter cannot attribute
 * is a row with no name on it. Refused when a count is not a number, rather
 * than coerced to zero — see the note at the top of this file.
 */
export function parseTokenUsage(data: unknown): TokenUsage | null {
    const raw = asRecord(data);
    if (!raw) return null;

    const executorId = asText(raw.executor_id);
    if (!executorId) return null;

    const inputTokens = asCount(raw.input_tokens);
    const outputTokens = asCount(raw.output_tokens);
    const totalTokens = asCount(raw.total_tokens);
    if (inputTokens === null || outputTokens === null || totalTokens === null) return null;

    return {
        agentName: asText(raw.agent_name) || executorId,
        executorId,
        inputTokens,
        outputTokens,
        totalTokens,
    };
}

/**
 * Read a `presenter_alert` payload, or return null.
 *
 * An alert with no words is not an alert. The words are the server's — the
 * hidden route chooses them from a rehearsed roster — so an empty one here
 * means something went wrong upstream, and a titled empty card on stage looks
 * like a bug rather than a beat.
 */
export function parsePresenterAlert(data: unknown): PresenterAlert | null {
    const raw = asRecord(data);
    if (!raw) return null;

    const title = asText(raw.title);
    const content = asText(raw.content);
    if (!title || !content) return null;

    return {
        title,
        content,
        timestamp: asText(raw.timestamp),
        provenance: asText(raw.provenance),
    };
}
