import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';

// Task hooks
export function useTasks(filters?: { status?: string; repository_id?: string }) {
  return useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => api.listTasks(filters),
  });
}

export function useTask(taskId: string | undefined) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.getTask(taskId!),
    enabled: !!taskId,
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.createTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.deleteTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

export function useCancelTask() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.cancelTask,
    onSuccess: (_, taskId) => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

// Repository hooks
export function useRepositories() {
  return useQuery({
    queryKey: ['repositories'],
    queryFn: api.listRepositories,
  });
}

export function useRepository(repoId: string | undefined) {
  return useQuery({
    queryKey: ['repository', repoId],
    queryFn: () => api.getRepository(repoId!),
    enabled: !!repoId,
  });
}

export function useAddRepository() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.addRepository,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
    },
  });
}

export function useDeleteRepository() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.deleteRepository,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] });
    },
  });
}

export function useSyncRepository() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: api.syncRepository,
    onSuccess: (_, repoId) => {
      queryClient.invalidateQueries({ queryKey: ['repository', repoId] });
    },
  });
}

// File hooks
export function useFiles(repoId: string | undefined, path?: string) {
  return useQuery({
    queryKey: ['files', repoId, path],
    queryFn: () => api.listFiles(repoId!, path),
    enabled: !!repoId,
  });
}

export function useFileContent(repoId: string | undefined, filePath: string | undefined) {
  return useQuery({
    queryKey: ['file', repoId, filePath],
    queryFn: () => api.getFileContent(repoId!, filePath!),
    enabled: !!repoId && !!filePath,
  });
}
