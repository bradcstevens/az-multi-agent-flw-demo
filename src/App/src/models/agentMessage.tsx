import { BaseModel } from './plan';
import { AgentMessageType, WebsocketMessageType } from './enums';

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
    agent_type: AgentMessageType;
    timestamp: number;
    steps: any[];
    next_steps: any[];
    content: string;
    raw_data: string;
    /** The answer is still receiving deltas and is not yet transcript history. */
    is_streaming?: boolean;
    /** Announce the complete answer once when it replaces the stream preview. */
    announce?: boolean;
}

/**
 * Message sent to HumanAgent to request approval for a step.
 * Corresponds to the Python AgentMessageResponse class.
 */
export interface AgentMessageResponse {

    /** Plan identifier */
    plan_id: string;
    /** Agent name or identifier */
    agent: string;
    /** Message content */
    content: string;
    /** Type of agent (Human or AI) */
    agent_type: AgentMessageType;
    /** Raw data associated with the message */
    raw_data: string;

    /**
     * The streamed reply as it stood, on the turn's last message.
     *
     * Nothing else persists it, which is why the echo survives at all. What the
     * echo no longer carries is whether the turn ended: the server settles the
     * turn it ended (#158, ADR-043 decision 7), so this surface stopped being a
     * second writer of a fact it learned second-hand.
     */
    streaming_message: string;

}

export interface FinalMessage {
    type: WebsocketMessageType;
    content: string;
    status: string;
    timestamp: number | null;
    raw_data: any;
}

export interface StreamingMessage {
    type: WebsocketMessageType;
    agent: string;
    content: string;
    is_final: boolean;
    raw_data: any;
}