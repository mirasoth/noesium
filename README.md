# Noesium-core

[![CI](https://github.com/mirasoth/noesium/actions/workflows/ci.yml/badge.svg)](https://github.com/mirasoth/noesium/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/noesium.svg)](https://pypi.org/project/noesium/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/mirasoth/noesium)

Project Noesium is an initiative to develop a computation-driven, cognitive agentic system. This repo contains the foundational abstractions (Agent, Memory, Tool, Goal, Orchestration, and more) along with essential modules such as LLM clients, logging, message buses, model routing, and observability. For the underlying philosophy, refer to my talk on MAS ([link](https://github.com/caesar0301/mas-talk-2508/blob/master/mas-talk-xmingc.pdf)).

## Installation

```bash
pip install -U noesium
```

## Core Modules

| Module | Description |
|--------|-------------|
| **LLM Integration** (`noesium.core.llm`) | Multi-provider support (OpenAI, OpenRouter, Ollama, LlamaCPP, LiteLLM), dynamic routing, token tracking |
| **Goal Management** (`noesium.core.goalith`) | LLM-based goal decomposition, DAG-based goal graph, dependency tracking |
| **Tool Management** (`noesium.core.toolify`) | Tool registry, MCP integration, 17+ built-in toolkits |
| **Memory** (`noesium.core.memory`) | MemU integration, embedding-based retrieval, multi-category storage |
| **Vector Store** (`noesium.core.vector_store`) | PGVector and Weaviate support, semantic search |
| **Message Bus** (`noesium.core.msgbus`) | Event-driven architecture, watchdog patterns |
| **Routing** (`noesium.core.routing`) | Dynamic complexity-based model selection |
| **Tracing** (`noesium.core.tracing`) | Token usage monitoring, Opik integration |

## Built-in Agents

- **AskuraAgent** - Conversational agent for collecting semi-structured information via human-in-the-loop workflows
- **SearchAgent** - Web search with query polishing, multi-engine support, and optional content crawling
- **DeepResearchAgent** - Iterative research with LLM-powered reflection and citation generation
- **MemoryAgent** - Memory management with categorization, embedding search, and memory linking

## Quick Start

### LLM Client

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

### Tool Management

```python
from noesium.core.toolify import BaseToolkit, ToolkitConfig, ToolkitRegistry, register_toolkit

@register_toolkit("calculator")
class CalculatorToolkit(BaseToolkit):
    def get_tools_map(self):
        return {"add": self.add, "multiply": self.multiply}

    def add(self, a: float, b: float) -> float:
        return a + b

    def multiply(self, a: float, b: float) -> float:
        return a * b

# Use toolkit
config = ToolkitConfig(name="calculator")
calc = ToolkitRegistry.create_toolkit("calculator", config)
result = calc.call_tool("add", a=5, b=3)
```

### Goal Decomposition

```python
from noesium.core.goalith.goalgraph.node import GoalNode
from noesium.core.goalith.goalgraph.graph import GoalGraph
from noesium.core.goalith.decomposer import LLMDecomposer

# Create and decompose a goal
goal = GoalNode(description="Plan a product launch", priority=8.0)
graph = GoalGraph()
graph.add_node(goal)

decomposer = LLMDecomposer()
subgoals = decomposer.decompose(goal, context={"budget": "$50,000"})
```

### Search Agent

```python
from noesium.agents.search import SearchAgent, SearchConfig

config = SearchConfig(
    polish_query=True,
    search_engines=["tavily"],
    max_results_per_engine=5
)
agent = SearchAgent(config=config)
results = await agent.search("latest developments in quantum computing")
```

### Deep Research Agent

```python
from noesium.agents.deep_research import DeepResearchAgent, DeepResearchConfig

config = DeepResearchConfig(
    number_of_initial_queries=3,
    max_research_loops=3,
    web_search_citation_enabled=True
)
agent = DeepResearchAgent(config=config)
result = await agent.research("What are the implications of AI on healthcare?")
```

## Environment Variables

```bash
# LLM Providers
export NOESIUM_LLM_PROVIDER="openai"
export OPENAI_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-..."
export OLLAMA_BASE_URL="http://localhost:11434"
export LLAMACPP_MODEL_PATH="/path/to/model.gguf"

# Vector Store (PostgreSQL)
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_DB="vectordb"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"

# Search Tools
export SERPER_API_KEY="..."
export JINA_API_KEY="..."
```

## Examples

See the `examples/` directory for comprehensive usage examples:

- `examples/agents/` - Agent demos (Askura, Search, DeepResearch)
- `examples/llm/` - LLM provider examples and token tracking
- `examples/goals/` - Goal decomposition patterns
- `examples/memory/` - Memory agent operations
- `examples/tools/` - Toolkit demonstrations
- `examples/vector_store/` - PGVector and Weaviate usage

## Documentation

- **Design Specifications**: `specs/` directory contains RFCs for system architecture
- **Agent Details**: See `AGENTS.md` for comprehensive agent and toolkit documentation
- **Toolify System**: `noesium/core/toolify/README.md`

## License

MIT License - see [LICENSE](LICENSE) file for details.
