/**
 * The Policy block the Identity boundary gate returns (issue #14, ADR-014).
 *
 * A policy block is **not** an error and **not** a retrieval miss. Rendering it
 * through the error toast would make the demo's centerpiece look like a bug,
 * which is exactly the confusion ADR-014 exists to prevent — so it is parsed
 * out of the failed response and given its own surface.
 *
 * The backend answers a refused request with HTTP 403 and a body of
 * `{"detail": {"kind": "policy_block", "code": "...", "message": "..."}}`.
 * `httpClient` throws that body as the message of a plain `Error`, so parsing
 * happens here rather than being threaded through every call site.
 */

export const POLICY_BLOCK_KIND = 'policy_block';

export interface PolicyBlock {
    kind: typeof POLICY_BLOCK_KIND;
    code: string;
    message: string;
}

/** An error that carries a policy block, so callers can render it as policy. */
export class PolicyBlockError extends Error {
    readonly policyBlock: PolicyBlock;

    constructor(policyBlock: PolicyBlock) {
        super(policyBlock.message);
        this.name = 'PolicyBlockError';
        this.policyBlock = policyBlock;
    }
}

/**
 * Read a policy block out of a thrown error, or return null.
 *
 * Total: anything that is not recognisably a policy block — a network failure,
 * a 500, an RAI block, unparseable text — returns null and is left to the
 * ordinary error path. Only a body that names itself a policy block and
 * carries a message is treated as one.
 */
export function parsePolicyBlock(error: unknown): PolicyBlock | null {
    if (error instanceof PolicyBlockError) {
        return error.policyBlock;
    }

    const raw = error instanceof Error ? error.message : error;
    if (typeof raw !== 'string') {
        return null;
    }

    let body: unknown;
    try {
        body = JSON.parse(raw);
    } catch {
        return null;
    }

    const detail = (body as { detail?: unknown })?.detail;
    if (!detail || typeof detail !== 'object') {
        return null;
    }

    const { kind, code, message } = detail as Record<string, unknown>;
    if (kind !== POLICY_BLOCK_KIND || typeof message !== 'string' || !message) {
        return null;
    }

    return {
        kind: POLICY_BLOCK_KIND,
        code: typeof code === 'string' ? code : 'unknown',
        message,
    };
}
