import { useParams, Link } from 'react-router-dom'
import { useTask, useCancelTask } from '../../hooks/useApi'
import { useSocket } from '../../hooks/useSocket'
import { useState } from 'react'
import type { ProgressEvent } from '../../types'

const statusColors: Record<string, string> = {
  created: 'text-gray-400',
  planning: 'text-blue-400',
  executing: 'text-yellow-400',
  reflecting: 'text-purple-400',
  completed: 'text-green-400',
  failed: 'text-red-400',
  cancelled: 'text-gray-500',
}

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>()
  const { data: task, isLoading, error, refetch } = useTask(taskId)
  const cancelTask = useCancelTask()
  const [, setLiveEvents] = useState<ProgressEvent[]>([])
  
  const { startTask, cancelTask: socketCancel } = useSocket({
    onProgress: (event) => {
      if (event.task_id === taskId) {
        setLiveEvents((prev: ProgressEvent[]) => [...prev, event])
        refetch()
      }
    },
    onTaskCompleted: () => {
      refetch()
    },
    onTaskError: () => {
      refetch()
    },
  })
  
  const handleStart = () => {
    if (taskId) {
      startTask(taskId)
    }
  }
  
  const handleCancel = async () => {
    if (taskId) {
      await cancelTask.mutateAsync(taskId)
      socketCancel(taskId)
    }
  }
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-400">Loading task...</div>
      </div>
    )
  }
  
  if (error || !task) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-red-400">Task not found</div>
      </div>
    )
  }
  
  const isRunning = task.status === 'executing' || task.status === 'planning'
  
  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link 
          to="/" 
          className="text-sm text-gray-500 hover:text-gray-300 mb-2 inline-block"
        >
          Back to tasks
        </Link>
        
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-100 mb-2">
              {task.title}
            </h1>
            <p className="text-gray-400">{task.description}</p>
          </div>
          
          <div className="flex items-center gap-3">
            <span className={statusColors[task.status]}>
              {task.status}
            </span>
            
            {task.status === 'created' && (
              <button
                onClick={handleStart}
                className="bg-primary-600 hover:bg-primary-500 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Start
              </button>
            )}
            
            {isRunning && (
              <button
                onClick={handleCancel}
                className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      </div>
      
      {/* Steps */}
      {task.steps.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-3">
            Execution Steps
          </h2>
          <div className="space-y-2">
            {task.steps.map((step, index) => (
              <div
                key={step.step_id}
                className={`p-3 rounded-lg border ${
                  step.status === 'completed'
                    ? 'bg-green-900/20 border-green-800'
                    : step.status === 'in_progress'
                    ? 'bg-yellow-900/20 border-yellow-800'
                    : step.status === 'failed'
                    ? 'bg-red-900/20 border-red-800'
                    : 'bg-gray-800 border-gray-700'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-gray-500 text-sm w-6">{index + 1}.</span>
                  <span className="text-gray-200">{step.description}</span>
                </div>
                {step.result && (
                  <div className="mt-2 text-sm text-gray-400 ml-8">
                    {step.result}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Code Changes */}
      {task.code_changes.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-3">
            Code Changes
          </h2>
          <div className="space-y-2">
            {task.code_changes.map((change, index) => (
              <div
                key={index}
                className="bg-gray-800 rounded-lg p-3 border border-gray-700"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-gray-200 font-mono text-sm">
                    {change.file_path}
                  </span>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-green-400">+{change.lines_added}</span>
                    <span className="text-red-400">-{change.lines_removed}</span>
                  </div>
                </div>
                <pre className="text-xs text-gray-400 overflow-x-auto">
                  {change.diff.slice(0, 500)}
                  {change.diff.length > 500 && '...'}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Final Answer */}
      {task.final_answer && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-200 mb-3">
            Final Answer
          </h2>
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <p className="text-gray-300 whitespace-pre-wrap">
              {task.final_answer}
            </p>
          </div>
        </div>
      )}
      
      {/* Error */}
      {task.error_message && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-red-400 mb-3">Error</h2>
          <div className="bg-red-900/20 rounded-lg p-4 border border-red-800">
            <p className="text-red-300">{task.error_message}</p>
          </div>
        </div>
      )}
    </div>
  )
}
