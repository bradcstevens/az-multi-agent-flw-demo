// Warning: Vibe coded as a simple websocket test

import { useEffect, useRef, useState } from 'react';
import { webSocketService, StreamMessage } from '../services/WebSocketService';

export interface WebSocketState {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
}

export const useWebSocket = () => {
  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isConnecting: false,
    error: null
  });
  
  const hasConnected = useRef(false);

  useEffect(() => {
    // Prevent multiple connections
    if (hasConnected.current) return;
    hasConnected.current = true;

    const connectWebSocket = async () => {
      setState(prev => ({ ...prev, isConnecting: true, error: null }));
      
      try {
        await webSocketService.connect();
        setState(prev => ({ ...prev, isConnected: true, isConnecting: false }));
      } catch (error) {
        console.error('Failed to connect to WebSocket:', error);
        setState(prev => ({ 
          ...prev, 
          isConnected: false, 
          isConnecting: false, 
          error: 'Failed to connect to server' 
        }));
      }
    };

    // Set up connection status listener
    const unsubscribeStatus = webSocketService.on('connection_status', (message: StreamMessage) => {
      if (message.data?.connected !== undefined) {
        setState(prev => ({ 
          ...prev, 
          isConnected: message.data.connected,
          isConnecting: false,
          error: message.data.connected ? null : prev.error
        }));
      }
    });

    // Set up error listener
    const unsubscribeError = webSocketService.on('error', (message: StreamMessage) => {
      setState(prev => ({ 
        ...prev, 
        error: message.data?.error || 'WebSocket error occurred' 
      }));
    });

    // Connect
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      unsubscribeStatus();
      unsubscribeError();
      webSocketService.disconnect();
      hasConnected.current = false;
    };
  }, []);

  return {
    ...state,
    webSocketService,
    reconnect: () => {
      setState(prev => ({ ...prev, isConnecting: true, error: null }));
      return webSocketService.connect();
    }
  };
};