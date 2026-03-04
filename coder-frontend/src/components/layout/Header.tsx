import { Link } from 'react-router-dom'
import { useRepositories } from '../../hooks/useApi'

export default function Header() {
  const { data: repositories } = useRepositories()
  
  return (
    <header className="border-b border-gray-800 bg-gray-900/95 backdrop-blur supports-[backdrop-filter]:bg-gray-900/60">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="text-xl font-bold text-primary-400 hover:text-primary-300">
            NoeCoder
          </Link>
          <nav className="flex items-center gap-4">
            <Link 
              to="/" 
              className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
            >
              Tasks
            </Link>
            <span className="text-gray-600">|</span>
            <span className="text-sm text-gray-500">
              {repositories?.length || 0} repos
            </span>
          </nav>
        </div>
        
        <div className="flex items-center gap-4">
          <button className="text-sm text-gray-400 hover:text-gray-200 transition-colors">
            Settings
          </button>
        </div>
      </div>
    </header>
  )
}
