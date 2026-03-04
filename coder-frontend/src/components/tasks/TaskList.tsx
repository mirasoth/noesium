import { useTasks } from '../../hooks/useApi'
import TaskCard from './TaskCard'
import type { TaskStatus } from '../../types'
import { useState } from 'react'

const statusFilters: { value: TaskStatus | ''; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'created', label: 'Created' },
  { value: 'executing', label: 'Executing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]

export default function TaskList() {
  const [status, setStatus] = useState<TaskStatus | ''>('')
  const { data: tasks, isLoading, error } = useTasks(
    status ? { status } : undefined
  )
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-400">Loading tasks...</div>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-red-400">Error loading tasks: {error.message}</div>
      </div>
    )
  }
  
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-100">Tasks</h1>
        
        <div className="flex items-center gap-2">
          {statusFilters.map((filter) => (
            <button
              key={filter.value}
              onClick={() => setStatus(filter.value)}
              className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                status === filter.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200'
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>
      
      {tasks && tasks.length > 0 ? (
        <div className="space-y-3">
          {tasks.map((task) => (
            <TaskCard key={task.task_id} task={task} />
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <div className="text-gray-500 mb-2">No tasks found</div>
          <div className="text-sm text-gray-600">
            Create your first task using the input below
          </div>
        </div>
      )}
    </div>
  )
}
