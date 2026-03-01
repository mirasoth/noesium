<div align="center">
  <img src="docs/logos/noesium-logo.jpg" alt="Noesium Logo" width="200" />

  #

  ![Python](https://img.shields.io/pypi/pyversions/noesium)
  ![PyPI version](https://img.shields.io/pypi/v/noesium)
  ![License](https://img.shields.io/github/license/mirasoth/noesium)
  ![GitHub Stars](https://img.shields.io/github/stars/mirasoth/noesium)

</div>

**Noesium** is a computation-driven cognitive agentic framework providing foundational abstractions for building autonomous AI agents with planning, memory, tools, and orchestration capabilities.

## Installation

```bash
pip install -U noesium
```

### Optional Dependencies

```bash
# Recommended: all features
pip install noesium[all]

# AI providers
pip install noesium[llm]             # OpenAI, LiteLLM, Instructor
pip install noesium[local-llm]       # Ollama, LlamaCPP
pip install noesium[ai-providers-all] # All AI providers

# Frameworks
pip install noesium[agents]          # LangChain + Bubus

# Tools & data
pip install noesium[tools]           # 17+ toolkits
pip install noesium[datascience]     # Pandas, NetworkX
pip install noesium[browser-use]     # Browser automation
```

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

### Build an Agent

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

### Use Toolkits

```python
from noesium.core.toolify import get_toolkit, ToolkitConfig

# Search toolkit
search_config = ToolkitConfig(name="search", config={"SERPER_API_KEY": "..."})
search = get_toolkit("search", search_config)
results = await search.search_google_api("Python async programming")

# Bash toolkit
bash = get_toolkit("bash")
files = await bash.list_directory(".")
```

## Core Modules

| Module | Description |
|--------|-------------|
| **Agents** (`noesium.core.agent`) | BaseAgent, BaseGraphicAgent, BaseHitlAgent, BaseResearcher |
| **LLM** (`noesium.core.llm`) | Multi-provider support, structured output, token tracking |
| **Toolify** (`noesium.core.toolify`) | Unified tool system with 17+ built-in toolkits |
| **Memory** (`noesium.core.memory`) | Multi-tier memory with semantic search |
| **Event** (`noesium.core.event`) | Domain events, message bus, tracing |
| **Vector Store** (`noesium.core.vector_store`) | PGVector, Weaviate support |

## Built-in Agents

- **AlithiaAgent** - Autonomous research assistant with planning, execution, reflection cycles
- **BrowserUseAgent** - Web automation with DOM interaction and code execution

## Built-in Toolkits

Search, Bash, Memory, Python Executor, ArXiv, Audio, Document, File Edit, GitHub, Gmail, Image, Tabular Data, Video, Wikipedia, and more.

See [AGENTS.md](AGENTS.md) for detailed documentation.

## Environment Variables

```bash
# LLM Provider
export NOESIUM_LLM_PROVIDER="openai"
export OPENAI_API_KEY="sk-..."

# Search
export SERPER_API_KEY="..."
```

## Documentation

- **[AGENTS.md](AGENTS.md)** - Detailed agent and toolkit documentation
- **`specs/`** - Design specifications (RFCs)
- **`examples/`** - Usage examples

## License

MIT License