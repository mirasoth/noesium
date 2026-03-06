# Voyager Quick Guide

**Voyager** is a 24/7 digital companion built on NoeAgent, providing continuous assistance through a web-based interface.

## Installation

### From Source

```bash
git clone https://github.com/mirasoth/noesium.git
cd noesium
make setup
```

## Quick Start

### Backend

```bash
cd voyager/backend
uv run uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd voyager/frontend
npm install
npm run dev
```

Access at: \`http://localhost:3000\`

## Architecture

```
┌─────────────────────────────────────┐
│         Frontend (React)             │
│    - Chat Interface                  │
│    - Code Editor                     │
│    - File Browser                    │
└────────────┬────────────────────────┘
             │ HTTP/WebSocket
             ▼
┌─────────────────────────────────────┐
│         Backend (FastAPI)            │
│    - Session Management              │
│    - NoeAgent Integration            │
│    - Project Context                 │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│      NoeAgent + Noesium Core         │
│    - Agent Execution                 │
│    - Tool Management                 │
│    - Memory Persistence              │
└─────────────────────────────────────┘
```

## Features

### 24/7 Availability

- Persistent sessions
- Background task execution
- Notification system
- Session recovery

### Web Interface

- Real-time chat
- Code editor with syntax highlighting
- File browser
- Progress tracking

### Project Awareness

- Codebase indexing
- Context retention
- Multi-project support

## Configuration

### Backend Configuration

```bash
# Environment variables
export NOESIUM_LLM_PROVIDER="openai"
export OPENAI_API_KEY="sk-..."
export DATABASE_URL="postgresql://..."
```

### Frontend Configuration

Edit \`voyager/frontend/.env\`:

```
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000/ws
```

## Usage

### Starting a Session

1. Open browser to \`http://localhost:3000\`
2. Create or select a project
3. Start chatting with the assistant

### Background Tasks

```python
# Via API
POST /api/tasks
{
  "task": "Analyze codebase and generate documentation",
  "background": true
}
```

### Session Management

```python
# List active sessions
GET /api/sessions

# Resume session
POST /api/sessions/{id}/resume

# End session
DELETE /api/sessions/{id}
```

## API Reference

### Chat Endpoint

```
POST /api/chat
{
  "message": "Explain the authentication flow",
  "session_id": "abc-123"
}
```

### Task Endpoint

```
POST /api/tasks
{
  "task": "Refactor the user service",
  "files": ["src/user_service.py"]
}
```

### File Operations

```
GET /api/files?path=src/
POST /api/files
{
  "path": "src/new_file.py",
  "content": "..."
}
```

## Deployment

### Docker

```bash
# Build
docker-compose build

# Run
docker-compose up -d
```

### Production

```bash
# Backend
cd voyager/backend
uv run gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker

# Frontend
cd voyager/frontend
npm run build
# Serve with nginx
```

## Next Steps

- **[NoeAgent Guide](quick_guide_noeagent.md)**: NoeAgent features
- **[Noesium Guide](quick_guide_noesium.md)**: Framework details
- **[Deployment Guide](../deploy/)**: Production deployment
