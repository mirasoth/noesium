# Noesium Framework Quick Guide

**Noesium** is a computation-driven cognitive agentic framework for building custom autonomous systems with event-sourced architecture, reusable subagents, and 17+ toolkits.

## Installation

### Basic Installation

```bash
pip install noesium
```

### Full Installation

```bash
# All features
pip install noesium[all]

# Specific feature sets
pip install noesium[llm]             # OpenAI, LiteLLM, Instructor
pip install noesium[local-llm]       # Ollama, LlamaCPP
pip install noesium[agents]          # LangChain, LangGraph
pip install noesium[tools]           # 17+ toolkits
```

## Quick Start

### 1. Configure Environment

```bash
export NOESIUM_LLM_PROVIDER="openai"
export OPENAI_API_KEY="sk-..."
```

### 2. Use the LLM Client

```python
from noesium.core.llm import get_llm_client

client = get_llm_client()
response = client.completion([{"role": "user", "content": "Hello!"}])
```

### 3. Create a Simple Agent

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

## Core Concepts

### Event-Sourced Architecture

Noesium uses an **event-sourced multi-agent kernel architecture**:

- **Single execution authority**: All reasoning happens inside the Agent Kernel
- **Event-sourced state**: State derived from append-only event log
- **Delegation via events**: Agents coordinate through event topics
- **Durability**: Crash recovery and replay capability

### Agent Types

| Type | Description | Use Case |
|------|-------------|----------|
| \`BaseGraphicAgent\` | LangGraph-based with state management | Complex workflows |
| \`BaseHitlAgent\` | Conversation-style with sessions | Interactive chat |
| \`BaseResearcher\` | Research with source management | Information gathering |

## Creating Custom Agents

```python
from noesium.core.agent import BaseGraphicAgent
from langgraph.graph import StateGraph, END

class CustomAgent(BaseGraphicAgent):
    def build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("plan", self.plan_node)
        workflow.add_node("execute", self.execute_node)
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", END)
        return workflow.compile()
```

## Using Toolkits

### Available Toolkits

| Toolkit | Name | Description |
|---------|------|-------------|
| Bash | \`bash\` | File operations, shell commands |
| Python Executor | \`python_executor\` | Execute Python code |
| Search | \`search\` | Web search (Google, Tavily, DDG) |
| ArXiv | \`arxiv\` | Academic paper search |
| Memory | \`memory\` | Persistent memory operations |

### Using Toolkits

```python
from noesium.core.toolify import get_toolkit

# Get toolkit
bash = get_toolkit("bash")
files = await bash.list_directory(".")

search = get_toolkit("search", config={"SERPER_API_KEY": "..."})
results = await search.search_google_api("Python async")
```

## Next Steps

- **[Developer Guide](dev_guide.md)**: Detailed framework development
- **[Examples](../examples/)**: Real-world usage examples
- **[Specifications](specs/)**: Technical RFCs and design docs
- **[NoeAgent Guide](quick_guide_noeagent.md)**: See NoeAgent implementation
