import { BaseModel } from './plan';

/**
 * Represents a message from an agent
 */
export interface AgentMessage extends BaseModel {
    /** The type of data model */
    data_type: "agent_message";
    /** Session identifier */
    session_id: string;
    /** Plan identifier */
    plan_id: string;
    /** Content of the message */
    content: string;
    /** Source of the message (e.g., agent type) */
    source: string;
    /** Optional step identifier associated with the message */
    step_id?: string;
}

export interface AgentMessageData {
    agent: string;
    timestamp: number;
    steps: any[];       // intentionally always empty
    next_steps: [];  // intentionally always empty
    raw_content: string;
    raw_data: string;
}