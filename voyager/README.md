# Voyager

Web-based coding assistant powered by the Noesium framework.

## Architecture

Voyager is a full-stack web application with:

- **Backend**: FastAPI + WebSocket server (Python)
- **Frontend**: React + TypeScript + Tailwind CSS

```
┌──────────────────────────────────────────┐
│           Voyager Frontend               │
│  React + TypeScript + Tailwind CSS       │
│  - Task Management UI                    │
│  - Real-time Progress Display            │
│  - Repository Browser                    │
└──────────────────────────────────────────┘
                  ↕ WebSocket
┌──────────────────────────────────────────┐
│           Voyager Backend                │
│  FastAPI + Python-SocketIO               │
│  - Task Orchestration                    │
│  - Git Integration                       │
│  - Noesium Agent Integration             │
└──────────────────────────────────────────┘
                  ↕
┌──────────────────────────────────────────┐
│         Noesium Framework                │
│  - Agent Execution                       │
│  - Memory Management                     │
│  - Tool System                           │
└──────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python >= 3.11
- Node.js >= 18
- uv (Python package manager)
- npm or yarn

### Development Setup

1. **Clone and install dependencies**:

```bash
# Install backend dependencies
cd voyager/backend
uv sync

# Install frontend dependencies
cd ../frontend
npm install
```

2. **Configure environment**:

Create `voyager/backend/.env`:

```bash
# LLM Configuration
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Workspace
WORKSPACE_ROOT=/path/to/your/projects
```

3. **Start the development servers**:

```bash
# Terminal 1: Start backend
cd voyager/backend
uv run noecoder

# Terminal 2: Start frontend
cd voyager/frontend
npm run dev
```

4. **Access the application**:

Open http://localhost:5173 in your browser.

### Using Docker Compose

```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop services
docker-compose -f docker-compose.dev.yml down
```

## Features

- **Task Management**: Create and manage coding tasks
- **Real-time Progress**: Live updates via WebSocket
- **Repository Integration**: Git operations and file browsing
- **Agent-Powered**: Leverages Noesium's cognitive agents
- **Modern UI**: Responsive design with Tailwind CSS

## Project Structure

```
voyager/
├── backend/           # FastAPI Python backend
│   ├── src/noecoder/  # Source code
│   ├── tests/         # Test suite
│   └── pyproject.toml # Python package config
├── frontend/          # React TypeScript frontend
│   ├── src/           # Source code
│   ├── public/        # Static assets
│   └── package.json   # Node dependencies
└── README.md          # This file
```

## Backend API

### REST Endpoints

- `GET /api/repositories` - List available repositories
- `POST /api/tasks` - Create a new task
- `GET /api/tasks/{task_id}` - Get task details
- `DELETE /api/tasks/{task_id}` - Cancel a task

### WebSocket Events

- `task:start` - Start a new task
- `task:progress` - Progress update
- `task:complete` - Task completed
- `task:error` - Error occurred

## Deployment

### Docker

Build and run with Docker:

```bash
# Build backend image
cd voyager/backend
docker build -t voyager-backend .

# Build frontend image
cd ../frontend
docker build -t voyager-frontend .

# Run with docker-compose
docker-compose up -d
```

### Production Configuration

See [deploy/voyager/](../../deploy/voyager/) for production deployment configs.

## Development

### Backend Development

```bash
cd voyager/backend

# Run tests
uv run pytest

# Format code
uv run black src tests
uv run isort src tests

# Type check
uv run mypy src
```

### Frontend Development

```bash
cd voyager/frontend

# Run development server
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Lint code
npm run lint
```

## Configuration

### Backend Configuration

See [backend/README.md](backend/README.md) for detailed backend configuration.

### Frontend Configuration

See [frontend/README.md](frontend/README.md) for frontend configuration.

## Environment Variables

### Backend

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (openai, anthropic, ollama) | Required |
| `OPENAI_API_KEY` | OpenAI API key | Required for OpenAI |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `DEBUG` | Enable debug mode | `false` |
| `WORKSPACE_ROOT` | Root directory for projects | `./workspace` |

### Frontend

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `http://localhost:8000` |
| `VITE_WS_URL` | WebSocket URL | `ws://localhost:8000` |

## Requirements

### Backend

- Python >= 3.11
- FastAPI >= 0.109.0
- Noesium >= 0.3.0

### Frontend

- Node.js >= 18
- React >= 18
- TypeScript >= 5

## License

MIT License - see [LICENSE](../../LICENSE) for details.

## Related Projects

- [Noesium](../../noesium/) - Core cognitive agentic framework
- [NoeAgent](../../noeagent/) - CLI/TUI application

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for development guidelines.