import { Lane } from './lane';

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
     * The Lane this request declares (issue #16, ADR-013), carried through
     * from the Quick Task that was tapped. Omit it for free-typed input: the
     * backend's lane router then selects the lane by its keyword fallback, and
     * fails open to the Deliberate lane when nothing matches.
     */
    lane?: string;
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
    /**
     * The Lane actually taken, as decided by the backend's lane router. Not
     * the same thing as the lane declared: free-typed input declares nothing,
     * and an unreadable declaration falls open to the Deliberate lane.
     */
    lane?: Lane;
}
