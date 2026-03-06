<div align="center">
  <img src="docs/logos/noesium-logo-light.png" alt="Noesium Logo" width="350" />

  #

  [![Python](https://img.shields.io/pypi/pyversions/noesium)](https://pypi.org/project/noesium/)
  [![PyPI Version](https://img.shields.io/pypi/v/noesium)](https://pypi.org/project/noesium/)
  [![License](https://img.shields.io/github/license/mirasoth/noesium)](https://github.com/mirasoth/noesium/blob/main/LICENSE)
  [![GitHub Stars](https://img.shields.io/github/stars/mirasoth/noesium)](https://github.com/mirasoth/noesium)

</div>

# Noesium Workspace

A monorepo workspace containing the Noesium framework and applications built on it.

## Projects

```
noesium/
├── noesium/        # Core cognitive agentic framework
├── noeagent/       # Multi-agent system implementation
├── voyager/        # 24/7 digital companion application
└── docs/           # Shared documentation
```

### [Noesium](noesium/) — The Framework

**A computation-driven cognitive agentic framework** for building custom autonomous systems with event-sourced architecture, reusable subagents, and 17+ toolkits.

Provides the foundation for building AI agents with:
- Event-sourced multi-agent kernel architecture
- Built-in toolkits (bash, python, web search, file editing, etc.)
- Multi-provider LLM support (OpenAI, Anthropic, Google, Ollama)
- Persistent memory and state management
- Subagent coordination and delegation

**Quick Guide**: [docs/quick_guide_noesium.md](docs/quick_guide_noesium.md)

### [NoeAgent](noeagent/) — Multi-Agent System

**An examplified multi-agent system** built on the Noesium framework, demonstrating advanced agent orchestration and coordination patterns.

Features:
- Dual-mode operation (Ask/Agent)
- Interactive TUI with rich terminal interface
- Task planning and decomposition
- Subagent coordination and delegation
- Multi-provider LLM support

**Quick Guide**: [docs/quick_guide_noeagent.md](docs/quick_guide_noeagent.md)

### [Voyager](voyager/) — Digital Companion

**A 24/7 digital companion** (formerly NoeCoder) built on NoeAgent, providing continuous assistance through web-based interface.

Features:
- Web-based coding assistant
- Continuous availability
- Session management
- Project context awareness

**Quick Guide**: [docs/quick_guide_voyager.md](docs/quick_guide_voyager.md)

## Design Philosophy

Noesium follows an **event-sourced multi-agent kernel architecture** for durability, replayability, and distributed coordination:

- **Single execution authority** — One Agent Kernel per agent; all reasoning, planning, tool use, and delegation happen inside it. No external layer mutates agent state.
- **Event-sourced state** — State is derived from an append-only event log. Enables replay, deterministic reconstruction, audit, and crash recovery.
- **Delegation via events** — Agents publish task events to capability topics; subscribers process them. Loose coupling, capability-based coordination.
- **Separation of concerns** — Cognition (Kernel), transport (Event Bus), persistence (Event Store), memory (Projection), routing (Topic subscriptions).

Goals: long-running autonomous agents, durable/resumable execution, multi-agent collaboration, horizontal scalability.

## Global Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Applications Layer                        │
│                                                                  │
│  ┌──────────────────┐              ┌────────────────────────┐  │
│  │    NoeAgent      │              │       Voyager          │  │
│  │ Multi-Agent      │──────────────│   Digital Companion    │  │
│  │ System           │              │   (24/7 Assistant)     │  │
│  └────────┬─────────┘              └───────────┬────────────┘  │
│           │                                    │                │
│           │  Built on                          │  Built on      │
│           │                                    │                │
└───────────┼────────────────────────────────────┼────────────────┘
            │                                    │
            └────────────────┬───────────────────┘
                             │
                             ▼
            ┌────────────────────────────────────┐
            │     Noesium Framework Core         │
            │                                    │
            │  ┌──────────────┬────────────────┐ │
            │  │  Toolkits    │  Subagents     │ │
            │  │  (17+ tools) │  (reusable)    │ │
            │  └──────────────┴────────────────┘ │
            │                                    │
            │  ┌────────────────────────────────┐ │
            │  │  Core Framework                │ │
            │  │  - Agent Kernel                │ │
            │  │  - Event Bus & Store           │ │
            │  │  - Memory Management           │ │
            │  │  - LLM Integration             │ │
            │  │  - Tool Registry               │ │
            │  └────────────────────────────────┘ │
            └────────────────────────────────────┘
```

### Architecture Layers

| Project | Layer | Purpose | Technology |
|---------|-------|---------|------------|
| **Noesium** | Framework | Core primitives, tools, memory, events | Python, LangGraph |
| **NoeAgent** | Application | Multi-agent orchestration, TUI | Python, Rich |
| **Voyager** | Application | Web interface, continuous service | FastAPI, React |

### Data Flow

```
User Request → NoeAgent/Voyager → Noesium Framework
                                        ↓
                                   Agent Kernel
                                        ↓
                               Tool Execution
                                        ↓
                            Subagent Delegation (if needed)
                                        ↓
                              Memory Update
                                        ↓
                                Response
```

## Installation and Usage

### Noesium Framework

**Install the framework:**

```bash
# Basic installation
pip install noesium

# Full installation with all features
pip install noesium[all]

# Specific feature sets
pip install noesium[llm]             # OpenAI, LiteLLM, Instructor
pip install noesium[local-llm]       # Ollama, LlamaCPP
pip install noesium[agents]          # LangChain, LangGraph
pip install noesium[tools]           # 17+ toolkits
pip install noesium[browser-use]     # Browser automation
```

**Use the framework:**

```python
from noesium.core.agent import BaseGraphicAgent
from noesium.core.llm import get_llm_client

class MyAgent(BaseGraphicAgent):
    def __init__(self, llm_client=None):
        super().__init__(llm_client or get_llm_client())

    def build_graph(self):
        # Define your LangGraph workflow
        pass

agent = MyAgent()
result = await agent.run("Your task")
```

📖 **[Full Quick Guide](docs/quick_guide_noesium.md)**

### NoeAgent

**Install NoeAgent:**

```bash
pip install noeagent

# With all dependencies
pip install noeagent[all]
```

**Use NoeAgent:**

```bash
# Start interactive TUI
noeagent

# Start in Ask mode
noeagent --mode ask

# Use in library mode
python
>>> from noeagent import NoeAgent
>>> agent = NoeAgent(model="gpt-4", mode="agent")
>>> result = await agent.run("Research AI trends")
```

📖 **[Full Quick Guide](docs/quick_guide_noeagent.md)**

### Voyager

**Run Voyager:**

```bash
# Backend
cd voyager/backend
uv run uvicorn main:app --reload

# Frontend
cd voyager/frontend
npm install && npm run dev
```

📖 **[Full Quick Guide](docs/quick_guide_voyager.md)**

## Development

### Workspace Setup

This is a **uv workspace** with three member packages:

```bash
# Clone the repository
git clone https://github.com/mirasoth/noesium.git
cd noesium

# Install all workspace packages with dev dependencies
make setup

# Or manually
uv sync --all-packages --extra dev --extra all
```

### Development Commands

```bash
# Show all commands
make help

# Install dependencies
make install

# Run tests
make test              # All tests
make test-noesium      # Noesium tests only
make test-noeagent     # NoeAgent tests only
make test-voyager      # Voyager tests only

# Code quality
make quality           # Run all quality checks
make format            # Format code
make lint              # Run linters

# Build
make build-all         # Build all packages
make build-noesium     # Build noesium only
make build-noeagent    # Build noeagent only
```

### Project Structure

```
noesium/
├── .github/
│   └── workflows/
│       └── ci.yml               # CI/CD pipeline
├── docs/
│   ├── quick_guide_noesium.md   # Framework guide
│   ├── quick_guide_noeagent.md  # NoeAgent guide
│   ├── quick_guide_voyager.md   # Voyager guide
│   ├── dev_guide.md             # Development guide
│   └── specs/                   # Specifications
├── examples/                     # Usage examples
├── noesium/                      # Framework package
│   ├── src/noesium/
│   ├── tests/
│   ├── README.md
│   └── pyproject.toml
├── noeagent/                     # NoeAgent application
│   ├── src/noeagent/
│   ├── tests/
│   ├── README.md
│   └── pyproject.toml
├── voyager/                      # Voyager application
│   ├── backend/
│   ├── frontend/
│   └── README.md
├── scripts/                      # Utility scripts
├── Makefile                      # Build automation
├── pyproject.toml               # Workspace config
└── README.md                    # This file
```

## Environment Variables

```bash
# LLM Provider Configuration
export NOESIUM_LLM_PROVIDER="openai"   # Required
export OPENAI_API_KEY="sk-..."         # Required for OpenAI

# Alternative providers
export NOESIUM_LLM_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="sk-ant-..."

export NOESIUM_LLM_PROVIDER="ollama"
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3"

# Optional toolkit configurations
export SERPER_API_KEY="..."            # Web search
```

## Documentation

- **[Quick Start Guides](docs/)**:
  - [Noesium Framework](docs/quick_guide_noesium.md)
  - [NoeAgent](docs/quick_guide_noeagent.md)
  - [Voyager](docs/quick_guide_voyager.md)
- **[Development Guide](docs/dev_guide.md)** - Framework development
- **[AGENTS.md](AGENTS.md)** - AI agent development guide
- **[Specifications](docs/specs/)** - Technical specifications
- **[Examples](examples/)** - Usage examples

## License and Support

- **License** — MIT. See [LICENSE](LICENSE) for details.
- **Issues** — [GitHub Issues](https://github.com/mirasoth/noesium/issues)
- **Repository** — [GitHub](https://github.com/mirasoth/noesium)
- **PyPI Packages**:
  - [noesium](https://pypi.org/project/noesium/)
  - [noeagent](https://pypi.org/project/noeagent/)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.