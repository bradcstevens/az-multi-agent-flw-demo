/**
 * StreamingService - Handles real-time streaming of plan generation process
 * This service can be enhanced to connect to actual WebSocket or Server-Sent Events
 */

export interface StreamMessage {
    type: 'progress' | 'thought' | 'action' | 'complete' | 'error';
    content: string;
    timestamp: Date;
    planId?: string;
    stepId?: string;
}

export type StreamMessageHandler = (message: StreamMessage) => void;

export class StreamingService {
    private static instance: StreamingService;
    private handlers: Map<string, StreamMessageHandler[]> = new Map();
    private connections: Map<string, WebSocket | EventSource> = new Map();

    static getInstance(): StreamingService {
        if (!StreamingService.instance) {
            StreamingService.instance = new StreamingService();
        }
        return StreamingService.instance;
    }

    /**
     * Subscribe to streaming updates for a specific plan
     * @param planId Plan ID to subscribe to
     * @param handler Message handler function
     * @returns Cleanup function to unsubscribe
     */
    subscribe(planId: string, handler: StreamMessageHandler): () => void {
        if (!this.handlers.has(planId)) {
            this.handlers.set(planId, []);
        }
        
        this.handlers.get(planId)!.push(handler);

        // TODO: Establish real WebSocket/SSE connection here
        // For now, we return a cleanup function
        return () => {
            const handlers = this.handlers.get(planId);
            if (handlers) {
                const index = handlers.indexOf(handler);
                if (index > -1) {
                    handlers.splice(index, 1);
                }
                if (handlers.length === 0) {
                    this.handlers.delete(planId);
                    this.disconnect(planId);
                }
            }
        };
    }

    /**
     * Connect to real-time stream for plan generation (future implementation)
     * @param planId Plan ID to connect to
     */
    private async connect(planId: string): Promise<void> {
        // TODO: Implement WebSocket or Server-Sent Events connection
        // Example WebSocket implementation:
        /*
        const ws = new WebSocket(`${WEBSOCKET_URL}/plan/${planId}/stream`);
        
        ws.onmessage = (event) => {
            const message: StreamMessage = JSON.parse(event.data);
            this.broadcastMessage(planId, message);
        };
        
        ws.onerror = (error) => {
            this.broadcastMessage(planId, {
                type: 'error',
                content: 'Connection error occurred',
                timestamp: new Date()
            });
        };
        
        this.connections.set(planId, ws);
        */
    }

    /**
     * Disconnect from real-time stream
     * @param planId Plan ID to disconnect from
     */
    private disconnect(planId: string): void {
        const connection = this.connections.get(planId);
        if (connection) {
            if (connection instanceof WebSocket) {
                connection.close();
            } else if (connection instanceof EventSource) {
                connection.close();
            }
            this.connections.delete(planId);
        }
    }

    /**
     * Broadcast message to all subscribers of a plan
     * @param planId Plan ID
     * @param message Stream message
     */
    private broadcastMessage(planId: string, message: StreamMessage): void {
        const handlers = this.handlers.get(planId);
        if (handlers) {
            handlers.forEach(handler => handler(message));
        }
    }

    /**
     * Simulate streaming for development/testing purposes
     * @param planId Plan ID
     * @param messages Array of messages to simulate
     */
    async simulateStreaming(planId: string, messages: Omit<StreamMessage, 'timestamp'>[]): Promise<void> {
        for (let i = 0; i < messages.length; i++) {
            const message: StreamMessage = {
                ...messages[i],
                timestamp: new Date(),
                planId
            };

            // Simulate network delay
            await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000));
            
            this.broadcastMessage(planId, message);
        }
    }

    /**
     * Send a manual message (useful for testing)
     * @param planId Plan ID
     * @param message Message to send
     */
    sendMessage(planId: string, message: Omit<StreamMessage, 'timestamp'>): void {
        this.broadcastMessage(planId, {
            ...message,
            timestamp: new Date(),
            planId
        });
    }

    /**
     * Clean up all connections and handlers
     */
    cleanup(): void {
        this.connections.forEach((connection, planId) => {
            this.disconnect(planId);
        });
        this.handlers.clear();
    }
}

// Export singleton instance
export const streamingService = StreamingService.getInstance();
