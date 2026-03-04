import { Link } from 'react-router-dom'
import type { Task } from '../../types'
import clsx from 'clsx'

const statusColors: Record<string, string> = {
  created: 'bg-gray-600',
  planning: 'bg-blue-600',
  executing: 'bg-yellow-600',
  reflecting: 'bg-purple-600',
  completed: 'bg-green-600',
  failed: 'bg-red-600',
  cancelled: 'bg-gray-500',
}

export default function TaskCard({ task }: { task: Task }) {
  const createdDate = new Date(task.created_at).toLocaleDateString()
  
  return (
    <Link
      to={`/tasks/${task.task_id}`}
      className="block bg-gray-800 rounded-lg p-4 hover:bg-gray-750 transition-colors border border-gray-700"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={clsx(
                'inline-block w-2 h-2 rounded-full',
                statusColors[task.status]
              )}
            />
            <h3 className="text-gray-100 font-medium truncate">
              {task.title}
            </h3>
          </div>
          
          <p className="text-sm text-gray-400 truncate mb-2">
            {task.description}
          </p>
          
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span>{createdDate}</span>
            {task.repository_id && (
              <span className="text-gray-600">Repository linked</span>
            )}
            {task.code_changes.length > 0 && (
              <span className="text-green-500">
                +{task.code_changes.reduce((sum, c) => sum + c.lines_added, 0)} lines
              </span>
            )}
          </div>
        </div>
        
        {task.status === 'executing' && (
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-gray-400">
              Step {task.current_step_index + 1}/{task.steps.length}
            </span>
          </div>
        )}
        
        {task.status === 'failed' && task.error_message && (
          <span className="text-xs text-red-400 bg-red-900/30 px-2 py-1 rounded">
            Error
          </span>
        )}
      </div>
    </Link>
  )
}
