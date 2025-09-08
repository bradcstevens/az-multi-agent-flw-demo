import { AgentType, StepStatus, PlanStatus, WebsocketMessageType } from './enums';
import { MPlanData } from './plan';

/**
 * Message roles compatible with Semantic Kernel
 * Currently unused but kept for potential future use
 */
// export enum MessageRole {
//     SYSTEM = "system",
//     USER = "user",
//     ASSISTANT = "assistant",
//     FUNCTION = "function"
// }

/**
 * Base class for generic chat messages with roles
 * Currently unused but kept for potential future use with Semantic Kernel integration
 */
// export interface GenericChatMessage {
//     /** Role of the message sender */
//     role: MessageRole;
//     /** Content of the message */
//     content: string;
//     /** Additional metadata */
//     metadata: Record<string, any>;
// }

/**
 * Message sent to request approval for a step
 */
export interface ApprovalRequest {
    /** Step identifier */
    step_id: string;
    /** Plan identifier */
    plan_id: string;
    /** Session identifier */
    session_id: string;
    /** User identifier */
    user_id: string;
    /** Action to be performed */
    action: string;
    /** Agent assigned to this step */
    agent: AgentType;
}

/**
 * Message containing human feedback on a step
 */
export interface HumanFeedback {
    /** Optional step identifier */
    step_id?: string;
    /** Plan identifier */
    plan_id: string;
    /** Session identifier */
    session_id: string;
    /** Whether the step is approved */
    approved: boolean;
    /** Optional feedback from human */
    human_feedback?: string;
    /** Optional updated action */
    updated_action?: string;
}

/**
 * Message containing human clarification on a plan
 */
export interface HumanClarification {
    /** Plan identifier */
    plan_id: string;
    /** Session identifier */
    session_id: string;
    /** Clarification from human */
    human_clarification: string;
}

/**
 * Message sent to an agent to perform an action
 */
export interface ActionRequest {
    /** Step identifier */
    step_id: string;
    /** Plan identifier */
    plan_id: string;
    /** Session identifier */
    session_id: string;
    /** Action to be performed */
    action: string;
    /** Agent assigned to this step */
    agent: AgentType;
}

/**
 * Message containing the response from an agent after performing an action
 */
export interface ActionResponse {
    /** Step identifier */
    step_id: string;
    /** Plan identifier */
    plan_id: string;
    /** Session identifier */
    session_id: string;
    /** Result of the action */
    result: string;
    /** Status after performing the action */
    status: StepStatus;
}

/**
 * Message for updating the plan state
 */
export interface PlanStateUpdate {
    /** Plan identifier */
    plan_id: string;
    /** Session identifier */
    session_id: string;
    /** Overall status of the plan */
    overall_status: PlanStatus;
}



export interface StreamMessage {
    type: WebsocketMessageType
    plan_id?: string;
    session_id?: string;
    data?: any;
    timestamp?: string | number;
}

export interface StreamingPlanUpdate {
    plan_id: string;
    session_id?: string;
    step_id?: string;
    agent_name?: string;
    content?: string;
    status?: 'in_progress' | 'completed' | 'error' | 'creating_plan' | 'pending_approval';
    message_type?: 'thinking' | 'action' | 'result' | 'clarification_needed' | 'plan_approval_request';
    timestamp?: number;
    is_final?: boolean;
}

export interface PlanApprovalRequestData {
    plan_id: string;
    session_id: string;
    plan: {
        steps: Array<{
            id: string;
            description: string;
            agent: string;
            estimated_duration?: string;
        }>;
        total_steps: number;
        estimated_completion?: string;
    };
    status: 'PENDING_APPROVAL';
}

export interface PlanApprovalResponseData {
    plan_id: string;
    session_id: string;
    approved: boolean;
    feedback?: string;
}

// Structured plan approval request
export interface ParsedPlanApprovalRequest {
    type: WebsocketMessageType.PLAN_APPROVAL_REQUEST;
    plan_id: string;
    parsedData: MPlanData;
    rawData: string;
}