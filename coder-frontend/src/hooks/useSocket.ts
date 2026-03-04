import { useEffect, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import type { ProgressEvent } from '../types';

const SOCKET_URL = '/';

interface UseSocketOptions {
  onProgress?: (event: ProgressEvent) => void;
  onTaskStarted?: (data: { task_id: string }) => void;
  onTaskCompleted?: (data: { task_id: string; final_answer: string }) => void;
  onTaskError?: (data: { task_id: string; error: string }) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export function useSocket(options: UseSocketOptions = {}) {
  const socketRef = useRef<Socket | null>(null);
  const optionsRef = useRef(options);
  
  // Keep options ref updated
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);
  
  useEffect(() => {
    socketRef.current = io(SOCKET_URL, {
      transports: ['websocket'],
      autoConnect: true,
    });
    
    const socket = socketRef.current;
    
    socket.on('connect', () => {
      console.log('Socket connected');
      optionsRef.current.onConnect?.();
    });
    
    socket.on('disconnect', () => {
      console.log('Socket disconnected');
      optionsRef.current.onDisconnect?.();
    });
    
    socket.on('progress', (event: ProgressEvent) => {
      optionsRef.current.onProgress?.(event);
    });
    
    socket.on('task.started', (data) => {
      optionsRef.current.onTaskStarted?.(data);
    });
    
    socket.on('task.completed', (data) => {
      optionsRef.current.onTaskCompleted?.(data);
    });
    
    socket.on('task.error', (data) => {
      optionsRef.current.onTaskError?.(data);
    });
    
    return () => {
      socket.disconnect();
    };
  }, []);
  
  const startTask = useCallback((taskId: string) => {
    socketRef.current?.emit('task_start', { task_id: taskId });
  }, []);
  
  const cancelTask = useCallback((taskId: string) => {
    socketRef.current?.emit('task_cancel', { task_id: taskId });
  }, []);
  
  return { startTask, cancelTask };
}
