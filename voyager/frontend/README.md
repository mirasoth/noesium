# Voyager Frontend

React + TypeScript frontend for the Voyager coding assistant.

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS framework
- **Vite** - Fast build tool
- **Socket.io-client** - WebSocket communication

## Development Setup

### Prerequisites

- Node.js >= 18
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The application will be available at http://localhost:5173

### Environment Variables

Create `.env` file:

```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

## Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

Built files will be in the `dist/` directory.

## Project Structure

```
src/
├── components/          # React components
│   ├── layout/         # Layout components
│   │   ├── Header.tsx
│   │   └── TaskInput.tsx
│   └── tasks/          # Task-related components
│       ├── TaskCard.tsx
│       ├── TaskDetail.tsx
│       └── TaskList.tsx
├── hooks/              # Custom React hooks
│   ├── useApi.ts       # REST API hook
│   └── useSocket.ts    # WebSocket hook
├── services/           # API services
│   └── api.ts          # Axios client
├── types/              # TypeScript types
│   └── index.ts
├── App.tsx             # Main app component
├── main.tsx            # Entry point
└── index.css           # Global styles
```

## Components

### Layout Components

#### Header
Main navigation and branding component.

#### TaskInput
Form component for creating new tasks with input validation.

### Task Components

#### TaskCard
Card component displaying task summary and status.

#### TaskList
Container component showing all active tasks.

#### TaskDetail
Detailed view of a single task with progress tracking.

## Hooks

### useApi

Custom hook for REST API calls:

```typescript
const { data, loading, error } = useApi<Task[]>('/api/tasks');
```

### useSocket

WebSocket hook for real-time updates:

```typescript
const { socket, connected } = useSocket('ws://localhost:8000');

socket.emit('task:start', { description: '...' });
socket.on('task:progress', (data) => { ... });
```

## API Integration

### REST API

Uses Axios for HTTP requests:

```typescript
import { api } from './services/api';

// GET request
const tasks = await api.get<Task[]>('/api/tasks');

// POST request
const newTask = await api.post<Task>('/api/tasks', {
  description: 'Create a REST API'
});
```

### WebSocket Events

Real-time communication via Socket.io:

**Emitted Events:**
- `task:start` - Start a new task
- `task:cancel` - Cancel running task

**Received Events:**
- `task:progress` - Progress updates
- `task:complete` - Task completion
- `task:error` - Error notification

## Styling

### Tailwind Configuration

Tailwind is configured in `tailwind.config.js`:

```javascript
module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '...',
        secondary: '...',
      }
    }
  }
}
```

### Global Styles

Global styles are in `src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Custom styles */
```

## Testing

```bash
# Run tests
npm test

# Run tests with coverage
npm test -- --coverage

# Run tests in watch mode
npm test -- --watch
```

## Linting

```bash
# Run ESLint
npm run lint

# Fix linting issues
npm run lint -- --fix
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm test` | Run tests |
| `npm run lint` | Run ESLint |

## Dependencies

### Production Dependencies

- `react` - UI framework
- `react-dom` - React DOM renderer
- `react-router-dom` - Client-side routing
- `socket.io-client` - WebSocket client
- `axios` - HTTP client

### Development Dependencies

- `typescript` - TypeScript compiler
- `vite` - Build tool
- `tailwindcss` - CSS framework
- `eslint` - Linting
- `@types/*` - TypeScript type definitions

## Browser Support

Supports modern browsers:
- Chrome >= 90
- Firefox >= 88
- Safari >= 14
- Edge >= 90

## Performance

- **Code Splitting**: Lazy loading with React.lazy()
- **Tree Shaking**: Vite removes unused code
- **Caching**: Static assets cached by Vite
- **Optimization**: Minification and compression in production build

## Troubleshooting

### Common Issues

**WebSocket connection fails:**
- Check backend is running on correct port
- Verify `VITE_WS_URL` environment variable
- Check CORS settings on backend

**Build errors:**
- Delete `node_modules/` and `dist/`
- Run `npm install` again
- Check TypeScript errors with `npm run build`

**Hot reload not working:**
- Check Vite config
- Clear browser cache
- Restart dev server

## Contributing

1. Follow TypeScript best practices
2. Write meaningful component names
3. Add types for all props and state
4. Write tests for new components
5. Run linting before committing

## Related Documentation

- [Voyager Backend](../backend/README.md)
- [Voyager Main](../README.md)
- [Contributing Guide](../../CONTRIBUTING.md)