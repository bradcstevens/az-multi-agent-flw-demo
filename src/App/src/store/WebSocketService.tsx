import { getApiUrl, getUserId } from '../api/config';
import { PlanDataService } from './PlanDataService';
import { ParsedPlanApprovalRequest, StreamingPlanUpdate, StreamMessage, WebsocketMessageType } from '../models';


class WebSocketService {
    private ws: WebSocket | null = null;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000; // 1s base, exponential: 1s, 2s, 4s, 8s, 16s
    private listeners: Map<string, Set<(message: StreamMessage) => void>> = new Map();
    private planSubscriptions: Set<string> = new Set();
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private isConnecting = false;
    private pendingConnect: Promise<void> | null = null;
    private pendingPlanId: string | undefined;
    private intentionalDisconnect = false;
    private lastPlanId: string | undefined;
    private lastProcessId: string | undefined;
    private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
    private heartbeatIntervalMs = 20000; // 20s client keepalive ping


    private buildSocketUrl(processId?: string, planId?: string): string {
        const baseWsUrl = getApiUrl() || 'ws://localhost:8000';
        // Trim and remove trailing slashes
        let base = (baseWsUrl || '').trim().replace(/\/+$/, '');
        // Normalize protocol: http -> ws, https -> wss
        base = base.replace(/^http:\/\//i, 'ws://')
            .replace(/^https:\/\//i, 'wss://');

        // Leave ws/wss as-is; anything else is assumed already correct

        // Decide path addition
        let userId = getUserId();
        const hasApiSegment = /\/api(\/|$)/i.test(base);
        const socketPath = hasApiSegment ? '/v4/socket' : '/api/v4/socket';
        const url = `${base}${socketPath}${processId ? `/${processId}` : `/${planId}`}?user_id=${userId || ''}`;
        return url;
    }
    connect(planId: string, processId?: string): Promise<void> {
        /*
          One socket per plan, whichever caller asks first (ADR-021).

          The connect is initiated on the `createPlan` response and the plan
          page keeps its own for a reload of /plan/:id, so both run for a plan
          asked from the home surface — the second landing while the first is
          still handshaking. Rejecting it told that caller the connection had
          failed while the same connection was succeeding, and the plan page
          logs a reject as "continuing without real-time updates", which was
          then untrue.
        */
        if (this.isConnecting && this.pendingConnect && this.pendingPlanId === planId) {
            return this.pendingConnect;
        }
        let handshakeStarted = false;
        const connecting = new Promise<void>((resolve, reject) => {
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
                handshakeStarted = true;
                this.pendingPlanId = planId;
                this.intentionalDisconnect = false;
                this.lastPlanId = planId;
                this.lastProcessId = processId;
                const wsUrl = this.buildSocketUrl(processId, planId);
                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => {
                    this.isConnecting = false;
                    this.reconnectAttempts = 0;
                    if (this.reconnectTimer) {
                        clearTimeout(this.reconnectTimer);
                        this.reconnectTimer = null;
                    }
                    this.startHeartbeat();
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
                    this.stopHeartbeat();
                    this.emit('connection_status', { connected: false });
                    /* P1: Only auto-reconnect if not intentional and not a clean close */
                    if (!this.intentionalDisconnect && event.code !== 1000 &&
                        this.reconnectAttempts < this.maxReconnectAttempts) {
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
        // Only a connect that actually started a handshake is the pending one.
        // A refusal recorded here would retire the live handshake's book-keeping
        // and make the next caller for the right plan look like a collision.
        if (!handshakeStarted) return connecting;

        this.pendingConnect = connecting;
        const settled = () => {
            if (this.pendingConnect === connecting) {
                this.pendingConnect = null;
                this.pendingPlanId = undefined;
            }
        };
        connecting.then(settled, settled);
        return connecting;
    }

    disconnect(): void {
        this.intentionalDisconnect = true;
        this.stopHeartbeat();
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        this.reconnectAttempts = this.maxReconnectAttempts;
        if (this.ws) {
            const socket = this.ws;
            this.ws = null;

            // Detach handlers so no stale callbacks fire during/after close
            socket.onopen = null;
            socket.onmessage = null;
            socket.onerror = null;
            socket.onclose = null;

            if (socket.readyState === WebSocket.OPEN) {
                // Normal close
                socket.close(1000, 'Manual disconnect');
            } else if (socket.readyState === WebSocket.CONNECTING) {
                // Still handshaking — wait for open then close cleanly.
                // This avoids the "WebSocket closed before connection established" warning.
                socket.addEventListener('open', () => socket.close(1000, 'Manual disconnect'), { once: true });
                socket.addEventListener('error', () => { /* handshake failed — nothing to close */ }, { once: true });
            }
            // CLOSING / CLOSED — no action needed
        }
        this.planSubscriptions.clear();
        this.isConnecting = false;
        this.pendingConnect = null;
        this.pendingPlanId = undefined;
    }


    private startHeartbeat(): void {
        this.stopHeartbeat();
        this.heartbeatTimer = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                try {
                    this.ws.send(JSON.stringify({ type: WebsocketMessageType.PING }));
                } catch {
                    /* onclose handles real drops */
                }
            }
        }, this.heartbeatIntervalMs);
    }

    private stopHeartbeat(): void {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
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

    onErrorMessage(callback: (data: any) => void): () => void {
        return this.on(WebsocketMessageType.ERROR_MESSAGE, (message: StreamMessage) => {
            callback(message.data);
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
                if (message.data) {
                    const transformed = PlanDataService.parseAgentMessage(message);
                    this.emit(WebsocketMessageType.AGENT_MESSAGE, transformed);

                }
                break;
            }

            case WebsocketMessageType.AGENT_MESSAGE_STREAMING: {
                if (message.data) {
                    const streamedMessage = PlanDataService.parseAgentMessageStreaming(message);
                    this.emit(WebsocketMessageType.AGENT_MESSAGE_STREAMING, streamedMessage);
                }
                break;
            }

            case WebsocketMessageType.USER_CLARIFICATION_REQUEST: {
                if (message.data) {
                    const transformed = PlanDataService.parseUserClarificationRequest(message);
                    this.emit(WebsocketMessageType.USER_CLARIFICATION_REQUEST, transformed);
                }
                break;
            }


            case WebsocketMessageType.AGENT_TOOL_MESSAGE: {
                if (message.data) {
                    //const transformed = PlanDataService.parseUserClarificationRequest(message);
                    this.emit(WebsocketMessageType.AGENT_TOOL_MESSAGE, message);
                }
                break;
            }
            case WebsocketMessageType.FINAL_RESULT_MESSAGE: {
                if (message.data) {
                    const transformed = PlanDataService.parseFinalResultMessage(message);
                    this.emit(WebsocketMessageType.FINAL_RESULT_MESSAGE, transformed);
                }
                break;
            }
            case WebsocketMessageType.PING: {
                // Server keepalive heartbeat — ignore.
                break;
            }
            case WebsocketMessageType.TIMEOUT_NOTIFICATION: {
                this.emit(WebsocketMessageType.TIMEOUT_NOTIFICATION, message);
                break;
            }
            case WebsocketMessageType.ERROR_MESSAGE: {
            this.emit(WebsocketMessageType.ERROR_MESSAGE, message.data); // Emit the data
            break;
            }
            /*
              The four out-of-band signals: the three transparency signals (#23)
              and the Simulated ticket (#22).

              They emit `message.data` — the payload — rather than falling to the
              default branch, which re-wraps the whole frame and hands the
              listener an envelope wearing the payload's name. Every parser these
              feed is total and returns `null` rather than a half-filled object,
              so the wrapped form was read as unreadable and dropped in silence:
              the Grounding panel stayed dark, the Token meter stayed empty and
              the Presenter alert never rendered, on a deployment where the
              backend was pushing all three correctly. Found by the Demo
              validator (#47) against `rg-macae-flw-v1`.
            */
            case WebsocketMessageType.SOURCE_USED:
            case WebsocketMessageType.TOKEN_USAGE:
            case WebsocketMessageType.PRESENTER_ALERT:
            case WebsocketMessageType.TICKET_RAISED: {
                this.emit(message.type, message.data);
                break;
            }
            case WebsocketMessageType.USER_CLARIFICATION_RESPONSE:
            case WebsocketMessageType.REPLAN_APPROVAL_REQUEST:
            case WebsocketMessageType.REPLAN_APPROVAL_RESPONSE:
            case WebsocketMessageType.PLAN_APPROVAL_RESPONSE:
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
        /* P1: exponential backoff — 1s, 2s, 4s, 8s, 16s (capped) */
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            16000,
        );
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            if (this.intentionalDisconnect) return;
            if (this.lastPlanId) {
                this.connect(this.lastPlanId, this.lastProcessId).catch(() => {
                    /* If reconnect fails, onclose will trigger another attempt */
                });
            } else {
                this.emit('error', { error: 'Connection lost — no planId available for reconnection' });
            }
        }, delay);
    }

    isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    /**
     * Is this service already serving that plan — open, or still handshaking?
     *
     * The handshake counts. `HomeInput` starts the connect on the `createPlan`
     * response and navigates in the same tick (ADR-021), so by the time the
     * plan page's effects run the socket it must adopt is almost always still
     * `CONNECTING`. A check that only saw `OPEN` would call it somebody else's
     * and close it.
     */
    isServing(planId: string): boolean {
        if (this.lastPlanId !== planId) return false;
        return this.ws?.readyState === WebSocket.OPEN || this.isConnecting;
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
            const v4Response = {
                m_plan_id: response.plan_id,
                approved: response.approved,
                feedback: response.feedback || response.user_response || response.human_clarification || '',
            };
            const message = {
                type: WebsocketMessageType.PLAN_APPROVAL_RESPONSE,
                data: v4Response
            };
            this.ws.send(JSON.stringify(message));
        } catch {
            this.emit('error', { error: 'Failed to send plan approval response' });
        }
    }
}

export const webSocketService = new WebSocketService();
export default webSocketService;