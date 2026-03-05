import { Routes, Route } from 'react-router-dom'
import Header from './components/layout/Header'
import TaskList from './components/tasks/TaskList'
import TaskDetail from './components/tasks/TaskDetail'
import TaskInput from './components/layout/TaskInput'

function App() {
  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      <Header />
      
      <main className="flex-1 container mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<TaskList />} />
          <Route path="/tasks/:taskId" element={<TaskDetail />} />
        </Routes>
      </main>
      
      <footer className="border-t border-gray-800 p-4">
        <TaskInput />
      </footer>
    </div>
  )
}

export default App
