import { useState } from 'react'
import { useRepositories, useCreateTask } from '../../hooks/useApi'
import { useNavigate } from 'react-router-dom'

export default function TaskInput() {
  const [description, setDescription] = useState('')
  const [repoId, setRepoId] = useState<string>('')
  const { data: repositories } = useRepositories()
  const createTask = useCreateTask()
  const navigate = useNavigate()
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!description.trim()) return
    
    try {
      const task = await createTask.mutateAsync({
        description: description.trim(),
        repository_id: repoId || undefined,
      })
      setDescription('')
      navigate(`/tasks/${task.task_id}`)
    } catch (error) {
      console.error('Failed to create task:', error)
    }
  }
  
  return (
    <form onSubmit={handleSubmit} className="flex gap-3 items-center">
      <div className="flex-1 relative">
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What code should we write?"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
      </div>
      
      <select
        value={repoId}
        onChange={(e) => setRepoId(e.target.value)}
        className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-3 text-gray-300 focus:outline-none focus:ring-2 focus:ring-primary-500"
      >
        <option value="">No repository</option>
        {repositories?.map((repo) => (
          <option key={repo.id} value={repo.id}>
            {repo.name}
          </option>
        ))}
      </select>
      
      <button
        type="submit"
        disabled={!description.trim() || createTask.isPending}
        className="bg-primary-600 hover:bg-primary-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-medium px-6 py-3 rounded-lg transition-colors"
      >
        {createTask.isPending ? 'Creating...' : 'Create Task'}
      </button>
    </form>
  )
}
