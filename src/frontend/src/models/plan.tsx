import { AgentType, PlanStatus, StepStatus, HumanFeedbackStatus } from './enums';
import { StreamingPlanUpdate } from './messages';

/**
 * Base interface with common fields
 */
export interface BaseModel {
    /** Unique identifier */
    id: string;
    /** Timestamp when created */

    /** Timestamp when last updated */
    timestamp: string;
}

/**
 * Represents a plan containing multiple steps.
 */
export interface Plan extends BaseModel {
    /** The type of data model */
    data_type: "plan";
    /** Session identifier */
    session_id: string;
    /** User identifier */
    user_id: string;
    /** Plan title */
    initial_goal: string;

    /** Current status of the plan */
    overall_status: PlanStatus;
    /** Human clarification request text */
    human_clarification_request?: string;
    /** Human clarification response text */
    human_clarification_response?: string;
}

/**
 * Represents an individual step (task) within a plan.
 */
export interface Step extends BaseModel {
    /** The type of data model */
    data_type: "step";
    /** Session identifier */
    session_id: string;
    /** User identifier */
    user_id: string;
    /** Plan identifier this step belongs to */
    plan_id: string;
    /** Step title */
    title: string;
    /** Step description */
    description: string;
    /** Agent responsible for this step */
    agent: AgentType;
    /** Current status of the step */
    status: StepStatus;
    /** Human feedback status */
    human_feedback_status: HumanFeedbackStatus;
    /** Human feedback text */
    human_feedback?: string;
    /** Step order/position in the plan */
    step_order: number;
}

export interface PlanMessage extends BaseModel {
    /** The type of data model */
    data_type: "agent_message";
    /** Session identifier */
    session_id: string;
    /** User identifier */
    user_id: string;
    /** Plan identifier */
    plan_id: string;
    /** Message content */
    content: string;
    /** Source of the message */
    source: string;
    /** Step identifier */
    step_id: string;
    /** Whether this is a streaming message */
    streaming?: boolean;
    /** Status of the streaming message */
    status?: string;
    /** Type of message (thinking, action, etc.) */
    message_type?: string;
}

/**
 * Union type for chat messages - can be either a regular plan message or a temporary streaming message
 */
export type ChatMessage = PlanMessage | { source: string; content: string; timestamp: string; streaming?: boolean; status?: string; message_type?: string; };

/**
 * Represents a plan that includes its associated steps.
 */
export interface PlanWithSteps extends Plan {
    /** Steps associated with this plan */
    steps: Step[];
    /** Total number of steps */
    total_steps: number;
    /** Count of steps in planned status */
    planned: number;
    /** Count of steps awaiting feedback */
    awaiting_feedback: number;
    /** Count of steps approved */
    approved: number;
    /** Count of steps rejected */
    rejected: number;
    /** Count of steps with action requested */
    action_requested: number;
    /** Count of steps completed */
    completed: number;
    /** Count of steps failed */
    failed: number;
}

/**
 * Interface for processed plan data
 */
export interface ProcessedPlanData {
    plan: PlanWithSteps;
    agents: AgentType[];
    steps: Step[];
    hasClarificationRequest: boolean;
    hasClarificationResponse: boolean;
    enableChat: boolean;
    enableStepButtons: boolean;
    messages: PlanMessage[];
}

export interface PlanChatProps {
    planData: ProcessedPlanData;
    input: string;
    loading: boolean;
    setInput: any;
    submittingChatDisableInput: boolean;
    OnChatSubmit: (message: string) => void;
    streamingMessages?: StreamingPlanUpdate[];
    wsConnected?: boolean;
    onPlanApproval?: (approved: boolean) => void;
}

export interface MPlanData {
    id: string;
    status: string;
    user_request: string;
    team: string[];
    facts: string;
    steps: Array<{
        id: number;
        action: string;
        cleanAction: string;
        agent?: string;
    }>;
    context: {
        task: string;
        participant_descriptions: Record<string, string>;
    };
    // Additional fields from m_plan
    user_id?: string;
    team_id?: string;
    plan_id?: string;
    overall_status?: string;
    raw_data?: any;
}

export interface PlanApprovalRequest {
    m_plan_id: string;
    plan_id: string;
    approved: boolean;
    feedback?: string;
}

export interface PlanApprovalResponse {
    status: string;
    message?: string;
}
