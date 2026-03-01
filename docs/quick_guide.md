# Noesium Quick Guide

Comprehensive guide for users and developers of the Noesium cognitive agentic framework.

## Table of Contents

- [For Users](#for-users)
  - [Installation](#installation)
  - [Basic Usage](#basic-usage)
  - [Using Built-in Agents](#using-built-in-agents)
  - [Environment Configuration](#environment-configuration)
- [For Developers](#for-developers)
  - [Creating Custom Agents](#creating-custom-agents)
  - [Using Toolkits](#using-toolkits)
  - [Agent Architecture](#agent-architecture)
  - [Memory System](#memory-system)
  - [Event System](#event-system)
- [Advanced Features](#advanced-features)
  - [Structured Output](#structured-output)
  - [Multi-Agent Coordination](#multi-agent-coordination)
  - [Durable Execution](#durable-execution)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## For Users

### Installation

Install Noesium with pip:

```bash
# Basic installation
pip install -U noesium

# Recommended: all features
pip install noesium[all]

# Selective installation
pip install noesium[llm]             # OpenAI, LiteLLM, Instructor
pip install noesium[local-llm]       # Ollama, LlamaCPP
pip install noesium[agents]          # LangChain + Bubus
pip install noesium[tools]           # 17+ toolkits
pip install noesium[browser-use]     # Browser automation
```

### Basic Usage

#### LLM Client

Create and use an LLM client:

```python
from noesium.core.llm import get_llm_client

# Create client (supports openai, openrouter, ollama, llamacpp)
client = get_llm_client(provider="openai", api_key="sk-...")

# Chat completion
response = client.completion([{"role": "user", "content": "Hello!"}])

# Structured output
from pydantic import BaseModel

class Answer(BaseModel):
    text: str
    confidence: float

client = get_llm_client(provider="openai", structured_output=True)
result = client.structured_completion(messages, Answer)
```

### Using Built-in Agents

#### AlithiaAgent

Autonomous research assistant with planning capabilities:

```python
from noesium.agents.alithia.agent import AlithiaAgent

agent = AlithiaAgent()
result = await agent.run("Research quantum computing applications")
```

#### BrowserUseAgent

Web automation agent:

```python
from noesium.agents.browser_use.agent import BrowserUseAgent

agent = BrowserUseAgent()
result = await agent.run("Navigate to example.com and extract content")
```

#### TacitusAgent

Advanced research agent with iterative refinement:

```python
from noesium.agents.tacitus.agent import TacitusAgent

agent = TacitusAgent(max_research_loops=3, number_of_initial_queries=2)
result = await agent.research("Latest developments in renewable energy")
```

### Environment Configuration

Set environment variables for configuration:

```bash
# LLM Provider
export NOESIUM_LLM_PROVIDER="openai"  # or "openrouter", "ollama", "llamacpp"
export OPENAI_API_KEY="sk-..."

# Search Toolkit
export SERPER_API_KEY="..."
export JINA_API_KEY="..."

# PostgreSQL (for vector store)
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_DB="vectordb"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"
```

---

## For Developers

### Creating Custom Agents

Extend the base agent classes to create custom agents:

```python
from noesium.core.agent.base import BaseGraphicAgent
from noesium.core.llm import get_llm_client

class MyAgent(BaseGraphicAgent):
    def __init__(self, llm_client=None):
        super().__init__(llm_client or get_llm_client())

    def build_graph(self):
        # Define your agent's workflow graph
        pass

agent = MyAgent()
result = await agent.run("What is the meaning of life?")
```

#### Agent Types

- **BaseAgent**: Abstract base class with common functionality
- **BaseGraphicAgent**: LangGraph-based agents with state management
- **BaseHitlAgent**: Conversation-style agents with session management
- **BaseResearcher**: Research-style agents with source management

### Using Toolkits

Access built-in toolkits through the Toolify system:

```python
from noesium.core.toolify import get_toolkit, ToolkitConfig

# Search toolkit
search_config = ToolkitConfig(name="search", config={"SERPER_API_KEY": "..."})
search = get_toolkit("search", search_config)
results = await search.search_google_api("Python async programming")

# Bash toolkit
bash = get_toolkit("bash")
files = await bash.list_directory(".")

# Memory toolkit
memory = get_toolkit("memory")
await memory.write_memory("my_slot", "Hello, World!")
content = await memory.read_memory("my_slot")
```

#### Available Toolkits

| Toolkit | Registration Name | Description |
|---------|------------------|-------------|
| Search | `search` | Google, Tavily, DuckDuckGo search |
| Bash | `bash` | File system and shell operations |
| Memory | `memory` | Persistent memory operations |
| Python Executor | `python_executor` | Python code execution |
| ArXiv | `arxiv` | Academic paper search |
| Audio | `audio` | Audio processing |
| Document | `document` | PDF/Word document processing |
| GitHub | `github` | GitHub API operations |
| Image | `image` | Image processing |
| Wikipedia | `wikipedia` | Wikipedia search |

### Agent Architecture

Noesium follows an **Event-Sourced Multi-Agent Kernel Architecture**:

```
            Event Bus
                 |
---------------------------------
|                               |
Agent Kernel A                Agent Kernel B
|                               |
Event Store A                 Event Store B
```

Each agent consists of:
1. **Event Subscriber**: Receives events from the bus
2. **Agent Kernel**: Graph-based execution runtime
3. **Event Store**: Append-only event log
4. **Projection Engine**: Derives current state from events
5. **Event Publisher**: Publishes new events to the bus

### Memory System

The memory system provides multi-tier storage:

- **Working Memory**: Derived projection from event log
- **Persistent Semantic Memory**: Vector store/database integration

All memory operations are event-backed for durability and replayability.

### Event System

The event system enables distributed coordination:

- **Topic-based routing**: Agents subscribe to capability topics
- **Correlation tracking**: Events include correlation IDs for tracing
- **At-least-once delivery**: Ensures no events are lost
- **Ordered processing**: Events processed in logical time order

---

## Advanced Features

### Structured Output

Use Pydantic models with Instructor for precise LLM output:

```python
from pydantic import BaseModel, Field

class ResearchQuery(BaseModel):
    queries: list[str] = Field(description="Search queries")
    rationale: str = Field(description="Why these queries are relevant")

client = get_llm_client(provider="openai", structured_output=True)
result = client.structured_completion(messages, ResearchQuery)
```

### Multi-Agent Coordination

Agents coordinate through event emission:

1. Agent A emits `TaskRequested(topic="analysis")`
2. Agent B subscribes to "analysis" topic
3. Agent B processes task and emits `TaskCompleted`
4. Agent A consumes `TaskCompleted` and continues workflow

### Durable Execution

Agents support crash recovery and resumable execution:

- **Event log replay**: Rebuild state from event history
- **Checkpoint boundaries**: Save progress at key points
- **Idempotent handlers**: Safe duplicate event processing

---

## Best Practices

### Agent Design

- **Single responsibility**: Each agent should have one clear purpose
- **Event-driven**: Use events for all state changes and coordination
- **Immutable state**: Derive state from event projections, not direct mutation
- **Capability declaration**: Subscribe to topics that match your agent's abilities

### Error Handling

- **Graceful degradation**: Handle missing dependencies gracefully
- **Retry semantics**: Implement exponential backoff for transient failures
- **Circuit breakers**: Prevent cascading failures in distributed systems

### Performance

- **Batch operations**: Group related operations when possible
- **Caching**: Cache expensive computations with proper invalidation
- **Pagination**: Handle large datasets with pagination

---

## Troubleshooting

### Common Issues

**LLM Provider Configuration**
- Ensure the correct provider is set in `NOESIUM_LLM_PROVIDER`
- Verify API keys are properly configured as environment variables

**Toolkit Activation**
- Check that required dependencies are installed (`noesium[tools]`)
- Verify toolkit configuration in `ToolkitConfig`

**Agent Execution**
- Ensure LangGraph dependencies are installed (`noesium[agents]`)
- Check event bus connectivity for multi-agent scenarios

### Debugging

Enable debug logging:

```python
import os
os.environ["LOG_LEVEL"] = "DEBUG"

from noesium.core.utils.logging import configure_logging
configure_logging(level="DEBUG")
```

### Support

- **Documentation**: See [AGENTS.md](../AGENTS.md) for detailed documentation
- **Specifications**: Review RFCs in the [`specs/`](../specs/) directory
- **Examples**: Run examples from the [`examples/`](../examples/) directory
- **Issues**: Report problems at the [GitHub repository](https://github.com/mirasoth/noesium)