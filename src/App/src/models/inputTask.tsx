/**
 * Represents an input task sent by a user to initiate a plan
 */
export interface InputTask {
    /** Optional session identifier (will be generated if not provided) */
    session_id?: string;
    /** The task description or goal */
    description: string;
    /** MANDATORY team identifier to use for this plan */
    team_id?: string;
    /**
     * Plan review, per request rather than per build (ADR-013). Omit or send
     * `true` for the Deliberate lane, which keeps the approval gate; send
     * `false` for the Fast lane. The backend defaults to `true`, so omitting
     * it never loses the gate.
     */
    plan_review?: boolean;
}

/**
 * Response from the input task endpoint
 */
export interface InputTaskResponse {
    /** Status message */
    status: string;
    /** Session identifier */
    session_id: string;
    /** Plan identifier */
    plan_id: string;
    /** The original task description */
    description: string;
}
