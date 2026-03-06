import type { Task, Repository, FileItem } from '../types';

const API_BASE = '/api';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`HTTP ${response.status}: ${error}`);
  }
  return response.json();
}

export const api = {
  // Tasks
  listTasks: async (params?: { status?: string; repository_id?: string }) => {
    const query = new URLSearchParams(params as Record<string, string>);
    return fetchJSON<Task[]>(`${API_BASE}/tasks?${query}`);
  },
  
  getTask: async (taskId: string) => 
    fetchJSON<Task>(`${API_BASE}/tasks/${taskId}`),
  
  createTask: async (data: { description: string; repository_id?: string; branch?: string }) =>
    fetchJSON<Task>(`${API_BASE}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  
  deleteTask: async (taskId: string) =>
    fetchJSON<{ deleted: boolean }>(`${API_BASE}/tasks/${taskId}`, {
      method: 'DELETE',
    }),
  
  cancelTask: async (taskId: string) =>
    fetchJSON<{ cancelled: boolean }>(`${API_BASE}/tasks/${taskId}/cancel`, {
      method: 'POST',
    }),
  
  getTaskEvents: async (taskId: string, limit: number = 100) =>
    fetchJSON<{ events: unknown[] }>(`${API_BASE}/tasks/${taskId}/events?limit=${limit}`),
  
  // Repositories
  listRepositories: async () => 
    fetchJSON<Repository[]>(`${API_BASE}/repositories`),
  
  addRepository: async (data: { url: string; name?: string }) =>
    fetchJSON<Repository>(`${API_BASE}/repositories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  
  getRepository: async (repoId: string) =>
    fetchJSON<Repository>(`${API_BASE}/repositories/${repoId}`),
  
  deleteRepository: async (repoId: string) =>
    fetchJSON<{ deleted: boolean }>(`${API_BASE}/repositories/${repoId}`, {
      method: 'DELETE',
    }),
  
  syncRepository: async (repoId: string) =>
    fetchJSON<{ synced: boolean }>(`${API_BASE}/repositories/${repoId}/sync`, {
      method: 'POST',
    }),
  
  listFiles: async (repoId: string, path?: string) => {
    const query = path ? `?path=${encodeURIComponent(path)}` : '';
    return fetchJSON<{ files: FileItem[] }>(`${API_BASE}/repositories/${repoId}/files${query}`);
  },
  
  getFileContent: async (repoId: string, filePath: string) =>
    fetchJSON<{ path: string; content: string }>(
      `${API_BASE}/repositories/${repoId}/files/${encodeURIComponent(filePath)}`
    ),
};
