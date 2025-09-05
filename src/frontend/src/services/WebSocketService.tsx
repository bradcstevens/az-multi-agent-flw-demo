import { headerBuilder } from '../api/config';
import { PlanDataService } from './PlanDataService';
import { MPlanData } from '../models';

export interface StreamMessage {
    type: 'plan_update' | 'step_update' | 'agent_message' | 'error' | 'connection_status' | 'plan_approval_request' | 'final_result' | 'parsed_plan_approval_request' | 'streaming_message';
    plan_id?: string;
    session_id?: string;
    data?: any;
    timestamp?: string;
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

// New interface for structured plan approval request
export interface ParsedPlanApprovalRequest {
    type: 'parsed_plan_approval_request';
    plan_id: string;
    parsedData: MPlanData;
    rawData: string;
}

class WebSocketService {
    private ws: WebSocket | null = null;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 12000;
    private listeners: Map<string, Set<(message: StreamMessage) => void>> = new Map();
    private planSubscriptions: Set<string> = new Set();
    private reconnectTimer: NodeJS.Timeout | null = null;
    private isConnecting = false;
    private baseWsUrl = process.env.REACT_APP_BACKEND_URL?.replace('http', 'ws') || 'ws://localhost:8000';

    /**
     * Connect to WebSocket server
     */
    connect(sessionId: string, processId?: string): Promise<void> {
        return new Promise((resolve, reject) => {
            if (this.isConnecting) {
                console.log('Connection already in progress');
                reject(new Error('Connection already in progress'));
                return;
            }

            if (this.ws?.readyState === WebSocket.OPEN) {
                console.log('WebSocket already connected');
                resolve();
                return;
            }

            try {
                this.isConnecting = true;

                // Use v3 WebSocket endpoint format
                const wsUrl = processId
                    ? `${this.baseWsUrl}/api/v3/socket/${processId}`
                    : `${this.baseWsUrl}/api/v3/socket/${sessionId}`;

                console.log('Connecting to WebSocket:', wsUrl);
                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = (event) => {
                    console.log('WebSocket connected successfully');
                    this.isConnecting = false;
                    this.reconnectAttempts = 0;

                    if (this.reconnectTimer) {
                        clearTimeout(this.reconnectTimer);
                        this.reconnectTimer = null;
                    }

                    this.emit('connection_status', { connected: true });
                    resolve();
                };

                this.ws.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        this.handleMessage(message);
                    } catch (error) {
                        console.error('Failed to parse WebSocket message:', error);
                    }
                };

                this.ws.onclose = (event) => {
                    console.log(`WebSocket disconnected: ${event.code} - ${event.reason}`);
                    this.isConnecting = false;
                    this.ws = null;
                    this.emit('connection_status', { connected: false });

                    if (this.reconnectAttempts < this.maxReconnectAttempts && event.code !== 1000) {
                        this.attemptReconnect();
                    }
                };

                this.ws.onerror = (event) => {
                    console.error('WebSocket error:', event);
                    this.isConnecting = false;

                    if (this.reconnectAttempts === 0) {
                        reject(new Error('WebSocket connection failed'));
                    }

                    this.emit('error', { error: 'WebSocket connection error' });
                };

            } catch (error) {
                this.isConnecting = false;
                console.error('Failed to create WebSocket connection:', error);
                reject(error);
            }
        });
    }

    /**
     * Disconnect from WebSocket server
     */
    disconnect(): void {
        console.log('Manually disconnecting WebSocket');

        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        this.reconnectAttempts = this.maxReconnectAttempts;

        if (this.ws) {
            this.ws.close(1000, 'Manual disconnect');
            this.ws = null;
        }
        this.planSubscriptions.clear();
        this.isConnecting = false;
    }

    /**
     * Subscribe to plan updates
     */
    subscribeToPlan(planId: string): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = {
                type: 'subscribe_plan',
                plan_id: planId
            };

            this.ws.send(JSON.stringify(message));
            this.planSubscriptions.add(planId);
            console.log(`Subscribed to plan updates: ${planId}`);
        }
    }

    /**
     * Unsubscribe from plan updates
     */
    unsubscribeFromPlan(planId: string): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = {
                type: 'unsubscribe_plan',
                plan_id: planId
            };

            this.ws.send(JSON.stringify(message));
            this.planSubscriptions.delete(planId);
            console.log(`Unsubscribed from plan updates: ${planId}`);
        }
    }

    /**
     * Add event listener
     */
    on(eventType: string, callback: (message: StreamMessage) => void): () => void {
        if (!this.listeners.has(eventType)) {
            this.listeners.set(eventType, new Set());
        }

        this.listeners.get(eventType)!.add(callback);

        return () => {
            const eventListeners = this.listeners.get(eventType);
            if (eventListeners) {
                eventListeners.delete(callback);
                if (eventListeners.size === 0) {
                    this.listeners.delete(eventType);
                }
            }
        };
    }

    /**
     * Remove event listener
     */
    off(eventType: string, callback: (message: StreamMessage) => void): void {
        const eventListeners = this.listeners.get(eventType);
        if (eventListeners) {
            eventListeners.delete(callback);
            if (eventListeners.size === 0) {
                this.listeners.delete(eventType);
            }
        }
    }

    /**
     * Connection change event handler
     */
    onConnectionChange(callback: (connected: boolean) => void): () => void {
        return this.on('connection_status', (message: StreamMessage) => {
            callback(message.data?.connected || false);
        });
    }

    /**
     * Streaming message event handler
     */
    onStreamingMessage(callback: (message: StreamingPlanUpdate) => void): () => void {
        return this.on('agent_message', (message: StreamMessage) => {
            if (message.data) {
                callback(message.data);
            }
        });
    }

    /**
     * Plan approval request event handler
     */
    onPlanApprovalRequest(callback: (approvalRequest: ParsedPlanApprovalRequest) => void): () => void {
        return this.on('parsed_plan_approval_request', (message: StreamMessage) => {
            if (message.data) {
                callback(message.data);
            }
        });
    }

    /**
     * Plan approval response event handler
     */
    onPlanApprovalResponse(callback: (response: any) => void): () => void {
        return this.on('plan_approval_response', (message: StreamMessage) => {
            if (message.data) {
                callback(message.data);
            }
        });
    }

    /**
     * Emit event to listeners
     */
    private emit(eventType: string, data: any): void {
        const message: StreamMessage = {
            type: eventType as any,
            data,
            timestamp: new Date().toISOString()
        };

        const eventListeners = this.listeners.get(eventType);
        if (eventListeners) {
            eventListeners.forEach(callback => {
                try {
                    callback(message);
                } catch (error) {
                    console.error('Error in WebSocket event listener:', error);
                }
            });
        }
    }

    /**
     * Handle incoming WebSocket messages
     */
    private handleMessage(message: StreamMessage): void {
        console.log('WebSocket message received:', message);

        if (message.type === 'plan_approval_request') {
            console.log('Plan approval request received via WebSocket:', message.data);

            // Parse the raw Python object string using PlanDataService
            const parsedData = PlanDataService.parsePlanApprovalRequest(message.data);

            if (parsedData) {
                // Emit a structured plan approval request
                const structuredMessage: ParsedPlanApprovalRequest = {
                    type: 'parsed_plan_approval_request',
                    plan_id: parsedData.id,
                    parsedData: parsedData,
                    rawData: message.data
                };

                this.emit('parsed_plan_approval_request', structuredMessage);
                console.log('Parsed plan approval request:', structuredMessage);
            } else {
                console.error('Failed to parse plan approval request data');
                this.emit('error', { error: 'Failed to parse plan approval request' });
            }
        }

        // Handle agent messages from the callback system (without plan_id)
        else if (message.type === 'agent_message' && message.data && !message.data.plan_id) {
            console.log('Agent callback message received:', message.data);

            // Transform the callback message format to match the expected streaming format
            // We'll need to get the current plan_id from somewhere - let's use the current subscription
            const currentPlanIds = Array.from(this.planSubscriptions);

            if (currentPlanIds.length > 0) {
                const transformedMessage: StreamMessage = {
                    ...message,
                    data: {
                        plan_id: currentPlanIds[0], // Use the first subscribed plan
                        agent_name: message.data.agent_name || 'Unknown Agent',
                        content: message.data.content || '',
                        message_type: 'thinking',
                        status: 'in_progress',
                        timestamp: Date.now() / 1000
                    }
                };

                console.log('Transformed agent message for plan:', transformedMessage.data.plan_id);
                this.emit(message.type, transformedMessage);
            } else {
                console.warn('Received agent message but no plan subscriptions active');
            }
        }

        // Handle streaming messages from the callback system
        else if (message.type === 'streaming_message' && message.data && !message.data.plan_id) {
            console.log('Streaming callback message received:', message.data);

            // Transform streaming message format
            const currentPlanIds = Array.from(this.planSubscriptions);

            if (currentPlanIds.length > 0) {
                const transformedMessage: StreamMessage = {
                    type: 'agent_message', // Convert streaming_message to agent_message
                    data: {
                        plan_id: currentPlanIds[0],
                        agent_name: message.data.agent_name || 'Unknown Agent',
                        content: message.data.content || '',
                        message_type: message.data.is_final ? 'result' : 'thinking',
                        status: message.data.is_final ? 'completed' : 'in_progress',
                        timestamp: Date.now() / 1000
                    }
                };

                console.log('Transformed streaming message for plan:', transformedMessage.data.plan_id);
                this.emit('agent_message', transformedMessage);
            }
        }

        // Handle regular streaming messages (already have plan_id)
        else {
            // Emit the message as-is for other types or when plan_id is present
            this.emit(message.type, message);
        }
    }

    /**
     * Attempt to reconnect with exponential backoff
     */
    private attemptReconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnection attempts reached - stopping reconnect attempts');
            this.emit('error', { error: 'Max reconnection attempts reached' });
            return;
        }

        if (this.isConnecting || this.reconnectTimer) {
            console.log('Reconnection attempt already in progress');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`Scheduling reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay / 1000}s`);

        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            console.log(`Attempting reconnection (attempt ${this.reconnectAttempts})`);

            // We need to store the original session/process IDs for reconnection
            // For now, we'll emit an error and let the parent component handle reconnection
            this.emit('error', { error: 'Connection lost - manual reconnection required' });
        }, delay);
    }

    /**
     * Get connection status
     */
    isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    /**
     * Send message to server
     */
    send(message: any): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket is not connected. Cannot send message:', message);
        }
    }

    /**
     * Send plan approval response for v3 backend
     */
    sendPlanApprovalResponse(response: {
        plan_id: string;
        session_id: string;
        approved: boolean;
        feedback?: string;
        user_response?: string;
        human_clarification?: string;
    }): void {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket not connected - cannot send plan approval response');
            this.emit('error', { error: 'Cannot send plan approval response - WebSocket not connected' });
            return;
        }

        try {
            // Send in v3 expected format
            const v3Response = {
                m_plan_id: response.plan_id, // v3 backend expects 'm_plan_id'
                approved: response.approved,
                feedback: response.feedback || response.user_response || response.human_clarification || '',
            };

            console.log('📤 Sending v3 plan approval response:', v3Response);

            const message = {
                type: 'plan_approval_response',
                data: v3Response
            };

            this.ws.send(JSON.stringify(message));
            console.log('Plan approval response sent successfully');
        } catch (error) {
            console.error('Failed to send plan approval response:', error);
            this.emit('error', { error: 'Failed to send plan approval response' });
        }
    }
}

export const webSocketService = new WebSocketService();
export default webSocketService;