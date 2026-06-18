import { useEffect, useRef, useState, useCallback } from 'react';

export const useWebSocket = (url: string) => {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  const [readyState, setReadyState] = useState<number>(WebSocket.CONNECTING);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const connect = () => {
      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        setReadyState(WebSocket.OPEN);
        console.log('WebSocket connected');
      };

      ws.current.onmessage = (event) => {
        setLastMessage(event);
      };

      ws.current.onclose = () => {
        setReadyState(WebSocket.CLOSED);
        console.log('WebSocket disconnected, retrying...');
        setTimeout(connect, 3000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    };

    connect();

    return () => {
      ws.current?.close();
    };
  }, [url]);

  const sendMessage = useCallback((data: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(data);
    }
  }, []);

  return { lastMessage, readyState, sendMessage };
};
