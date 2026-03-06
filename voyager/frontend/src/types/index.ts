export type TaskStatus = 
  | 'created' 
  | 'planning' 
  | 'executing' 
  | 'reflecting' 
  | 'completed' 
  | 'failed' 
  | 'cancelled';

export interface TaskStep {
  step_id: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  result: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface CodeChange {
  file_path: string;
  change_type: 'created' | 'modified' | 'deleted';
  diff: string;
  lines_added: number;
  lines_removed: number;
}

export interface Task {
  task_id: string;
  title: string;
  description: string;
  status: TaskStatus;
  repository_id: string | null;
  branch: string | null;
  steps: TaskStep[];
  current_step_index: number;
  code_changes: CodeChange[];
  final_answer: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface Repository {
  id: string;
  name: string;
  url: string;
  local_path: string;
  default_branch: string;
  last_synced: string | null;
  is_cloned: boolean;
}

export interface ProgressEvent {
  task_id: string;
  event: {
    type: string;
    session_id: string;
    sequence: number;
    summary: string | null;
    detail: string | null;
    step_index: number | null;
    step_desc: string | null;
    tool_name: string | null;
    tool_args: Record<string, unknown> | null;
    tool_result: string | null;
    text: string | null;
    error: string | null;
  };
}

export interface FileItem {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
}
