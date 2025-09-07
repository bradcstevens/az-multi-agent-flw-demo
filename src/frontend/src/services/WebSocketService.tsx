import { headerBuilder } from '../api/config';
import { PlanDataService } from './PlanDataService';
import { MPlanData, ParsedPlanApprovalRequest, StreamingPlanUpdate, StreamMessage, WebsocketMessageType } from '../models';


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

    connect(sessionId: string, processId?: string): Promise<void> {
        return new Promise((resolve, reject) => {
            if (this.isConnecting) {
                reject(new Error('Connection already in progress'));
                return;
            }
            if (this.ws?.readyState === WebSocket.OPEN) {
                resolve();
                return;
            }
            try {
                this.isConnecting = true;
                const wsUrl = processId
                    ? `${this.baseWsUrl}/api/v3/socket/${processId}`
                    : `${this.baseWsUrl}/api/v3/socket/${sessionId}`;
                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => {
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
                    this.isConnecting = false;
                    this.ws = null;
                    this.emit('connection_status', { connected: false });
                    if (this.reconnectAttempts < this.maxReconnectAttempts && event.code !== 1000) {
                        this.attemptReconnect();
                    }
                };

                this.ws.onerror = () => {
                    this.isConnecting = false;
                    if (this.reconnectAttempts === 0) {
                        reject(new Error('WebSocket connection failed'));
                    }
                    this.emit('error', { error: 'WebSocket connection error' });
                };
            } catch (error) {
                this.isConnecting = false;
                reject(error);
            }
        });
    }

    disconnect(): void {
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

    subscribeToPlan(planId: string): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = { type: 'subscribe_plan', plan_id: planId };
            this.ws.send(JSON.stringify(message));
            this.planSubscriptions.add(planId);
        }
    }

    unsubscribeFromPlan(planId: string): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = { type: 'unsubscribe_plan', plan_id: planId };
            this.ws.send(JSON.stringify(message));
            this.planSubscriptions.delete(planId);
        }
    }

    on(eventType: string, callback: (message: StreamMessage) => void): () => void {
        if (!this.listeners.has(eventType)) {
            this.listeners.set(eventType, new Set());
        }
        this.listeners.get(eventType)!.add(callback);
        return () => {
            const setRef = this.listeners.get(eventType);
            if (setRef) {
                setRef.delete(callback);
                if (setRef.size === 0) this.listeners.delete(eventType);
            }
        };
    }

    off(eventType: string, callback: (message: StreamMessage) => void): void {
        const setRef = this.listeners.get(eventType);
        if (setRef) {
            setRef.delete(callback);
            if (setRef.size === 0) this.listeners.delete(eventType);
        }
    }

    onConnectionChange(callback: (connected: boolean) => void): () => void {
        return this.on('connection_status', (message: StreamMessage) => {
            callback(message.data?.connected || false);
        });
    }

    onStreamingMessage(callback: (message: StreamingPlanUpdate) => void): () => void {
        return this.on(WebsocketMessageType.AGENT_MESSAGE, (message: StreamMessage) => {
            if (message.data) callback(message.data);
        });
    }

    onPlanApprovalRequest(callback: (approvalRequest: ParsedPlanApprovalRequest) => void): () => void {
        return this.on(WebsocketMessageType.PLAN_APPROVAL_REQUEST, (message: StreamMessage) => {
            if (message.data) callback(message.data);
        });
    }

    onPlanApprovalResponse(callback: (response: any) => void): () => void {
        return this.on(WebsocketMessageType.PLAN_APPROVAL_RESPONSE, (message: StreamMessage) => {
            if (message.data) callback(message.data);
        });
    }

    private emit(eventType: string, data: any): void {
        const message: StreamMessage = {
            type: eventType as any,
            data,
            timestamp: new Date().toISOString()
        };
        const setRef = this.listeners.get(eventType);
        if (setRef) {
            setRef.forEach(cb => {
                try { cb(message); } catch (e) { console.error('Listener error:', e); }
            });
        }
    }

    private handleMessage(message: StreamMessage): void {
        console.log('WebSocket message received:', message);
        const currentPlanIds = Array.from(this.planSubscriptions);
        const firstPlanId = currentPlanIds[0];

        switch (message.type) {
            case WebsocketMessageType.PLAN_APPROVAL_REQUEST: {
                const parsedData = PlanDataService.parsePlanApprovalRequest(message.data);
                if (parsedData) {
                    const structuredMessage: ParsedPlanApprovalRequest = {
                        type: WebsocketMessageType.PLAN_APPROVAL_REQUEST,
                        plan_id: parsedData.id,
                        parsedData,
                        rawData: message.data
                    };
                    this.emit(WebsocketMessageType.PLAN_APPROVAL_REQUEST, structuredMessage);
                } else {
                    this.emit('error', { error: 'Failed to parse plan approval request' });
                }
                break;
            }

            case WebsocketMessageType.AGENT_MESSAGE: {
                if (message.data && !message.data.plan_id && firstPlanId) {
                    const transformed: StreamMessage = {
                        ...message,
                        data: {
                            plan_id: firstPlanId,
                            agent_name: message.data.agent_name || 'Unknown Agent',
                            content: message.data.content || '',
                            message_type: 'thinking',
                            status: 'in_progress',
                            timestamp: Date.now() / 1000
                        }
                    };
                    this.emit(WebsocketMessageType.AGENT_MESSAGE, transformed);
                } else {
                    this.emit(WebsocketMessageType.AGENT_MESSAGE, message);
                }
                break;
            }

            case WebsocketMessageType.AGENT_MESSAGE_STREAMING: {
                if (message.data) {
                    const isFinal = !!message.data.is_final;
                    const transformed: StreamMessage = {
                        type: WebsocketMessageType.AGENT_MESSAGE,
                        data: {
                            plan_id: message.data.plan_id || firstPlanId,
                            agent_name: message.data.agent_name || 'Unknown Agent',
                            content: message.data.content || '',
                            message_type: isFinal ? 'result' : 'thinking',
                            status: isFinal ? 'completed' : 'in_progress',
                            timestamp: Date.now() / 1000,
                            is_final: isFinal
                        }
                    };
                    if (!transformed.data.plan_id) {
                        console.warn('Streaming message missing plan_id and no subscription context.');
                        break;
                    }
                    this.emit(WebsocketMessageType.AGENT_MESSAGE, transformed);
                }
                break;
            }

            case WebsocketMessageType.AGENT_TOOL_MESSAGE:
            case WebsocketMessageType.USER_CLARIFICATION_REQUEST:
            case WebsocketMessageType.USER_CLARIFICATION_RESPONSE:
            case WebsocketMessageType.REPLAN_APPROVAL_REQUEST:
            case WebsocketMessageType.REPLAN_APPROVAL_RESPONSE:
            case WebsocketMessageType.PLAN_APPROVAL_RESPONSE:
            case WebsocketMessageType.FINAL_RESULT_MESSAGE:
            case WebsocketMessageType.AGENT_STREAM_START:
            case WebsocketMessageType.AGENT_STREAM_END:
            case WebsocketMessageType.SYSTEM_MESSAGE: {
                this.emit(message.type, message);
                break;
            }

            default: {
                this.emit(message.type, message);
                break;
            }
        }
    }

    private attemptReconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.emit('error', { error: 'Max reconnection attempts reached' });
            return;
        }
        if (this.isConnecting || this.reconnectTimer) return;
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.emit('error', { error: 'Connection lost - manual reconnection required' });
        }, delay);
    }

    isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    send(message: any): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not connected. Cannot send:', message);
        }
    }

    sendPlanApprovalResponse(response: {
        plan_id: string;
        session_id: string;
        approved: boolean;
        feedback?: string;
        user_response?: string;
        human_clarification?: string;
    }): void {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.emit('error', { error: 'Cannot send plan approval response - WebSocket not connected' });
            return;
        }
        try {
            const v3Response = {
                m_plan_id: response.plan_id,
                approved: response.approved,
                feedback: response.feedback || response.user_response || response.human_clarification || '',
            };
            const message = {
                type: WebsocketMessageType.PLAN_APPROVAL_RESPONSE,
                data: v3Response
            };
            this.ws.send(JSON.stringify(message));
        } catch {
            this.emit('error', { error: 'Failed to send plan approval response' });
        }
    }
}

export const webSocketService = new WebSocketService();
export default webSocketService;