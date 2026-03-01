# Agents and Tools in Noesium

Comprehensive documentation of available agents, toolkits, and architecture in the Noesium cognitive agentic framework.

## Table of Contents

- [Agents](#agents)
  - [NoeAgent](#noeagent)
  - [BrowserUseAgent](#browseruseagent)
  - [TacitusAgent](#tacitusagent)
- [Toolkits](#toolkits)
  - [Search Toolkit](#search-toolkit)
  - [Bash Toolkit](#bash-toolkit)
  - [Memory Toolkit](#memory-toolkit)
  - [Python Executor Toolkit](#python-executor-toolkit)
  - [Other Toolkits](#other-toolkits)
- [Agent Architecture](#agent-architecture)
- [Tool System Architecture](#tool-system-architecture)
- [Configuration](#configuration)

---

## Agents

### NoeAgent

**Location:** `noesium/agents/noe/`

**Purpose:** Autonomous research assistant with dual modes (Ask/Agent) featuring planning, execution, and reflection cycles using LangGraph.

**Key Features:**
- Dual operation modes: Ask (Q&A) and Agent (autonomous)
- LLM-powered task planning and decomposition
- Tool usage with permission system
- Reflection-based quality control
- LangGraph stateful workflow

**Components:**
- `agent.py` - Main agent implementation with LangGraph workflow
- `task_planner.py` - Task decomposition and planning
- `schemas.py` - State classes (AskState, AgentState)
- `prompts.py` - Prompt templates

**Graph Workflow:**
```
START → task_planner → tool_executor → reflection → [conditional]
    → (loop for more actions if needed) OR finalize_answer → END
```

**Demo:** `examples/agents/noe_demo.py`

---

### BrowserUseAgent

**Location:** `noesium/agents/browser_use/`

**Purpose:** Web automation agent for browser interaction, DOM manipulation, and code execution.

**Key Features:**
- Browser session management with CDP
- DOM interaction and element manipulation
- Code execution in browser context
- Page navigation and scraping

---

### TacitusAgent

**Location:** `noesium/agents/tacitus/`

**Purpose:** Advanced autonomous research agent with iterative query generation, web search, reflection, and answer synthesis using LangGraph and structured LLM output.

**Key Features:**
- Multi-loop research workflow with reflection-based quality control
- Structured LLM output using Instructor for precise query generation and evaluation
- Multi-engine web search support (Tavily, DuckDuckGo, etc.)
- Automatic citation handling and source tracking
- Configurable research depth and breadth parameters
- LangGraph stateful workflow with conditional branching

**Components:**
- `agent.py` - Main agent implementation with LangGraph workflow
- `schemas.py` - Pydantic schemas for structured LLM output (SearchQueryList, Reflection)
- `prompts.py` - Prompt templates for query generation, reflection, and answer synthesis
- `state.py` - State classes for research workflow management

**Graph Workflow:**
```
START → generate_query → [web_research nodes] → reflection → [conditional]
    → (loop for more research if needed) OR finalize_answer → END
```

**Research Loop:**
1. **Query Generation**: Generate focused search queries based on user request
2. **Web Research**: Execute parallel searches across multiple engines
3. **Reflection**: Evaluate results for sufficiency and identify knowledge gaps
4. **Iteration**: Generate follow-up queries if needed (up to max_research_loops)
5. **Finalization**: Synthesize comprehensive answer with citations

**Demo:** `examples/agents/tacitus_demo.py`

---

## Toolkits

All toolkits are located in `noesium/toolkits/` and managed through the Toolify system.

### Search Toolkit

**Registration Name:** `search`
**Location:** `noesium/toolkits/search_toolkit.py`

**Tools:**
- `search_google_api` - Google search via Serper API
- `get_web_content` - Extract content from web pages via Jina Reader
- `web_qa` - Ask questions about web content with LLM
- `tavily_search` - Tavily search with AI-powered summaries
- `google_ai_search` - Google AI search with Gemini models

**Features:**
- Intelligent content filtering (banned sites)
- LLM-powered Q&A on web content
- Related link extraction
- Multiple search engine support

---

### Bash Toolkit

**Registration Name:** `bash`
**Location:** `noesium/toolkits/bash_toolkit.py`

**Tools:**
- `run_bash` - Execute bash commands
- `get_current_directory` - Get current working directory
- `list_directory` - List directory contents

**Features:**
- Persistent shell session
- Command filtering and security checks
- ANSI escape sequence cleaning
- Workspace isolation

---

### Memory Toolkit

**Registration Name:** `memory`
**Location:** `noesium/toolkits/memory_toolkit.py`

**Tools:**
- `read_memory` - Read from memory slot
- `write_memory` - Write to memory slot
- `edit_memory` - Edit memory content
- `append_to_memory` - Append to memory slot
- `clear_memory` - Clear memory slot
- `list_memory_slots` - List all memory slots
- `search_memory` - Search within memory slots
- `get_memory_stats` - Get memory statistics

**Features:**
- Multiple named memory slots
- File-based persistence
- Versioning support
- Search and filtering capabilities

---

### Python Executor Toolkit

**Registration Name:** `python_executor`
**Location:** `noesium/toolkits/python_executor_toolkit.py`

**Tools:**
- `execute_python_code` - Execute Python code

**Features:**
- IPython-based execution
- Automatic matplotlib plot saving
- File creation tracking
- Timeout protection
- ANSI escape sequence cleaning

---

### Other Toolkits

| Toolkit | Registration Name | Description |
|---------|------------------|-------------|
| ArXiv Toolkit | `arxiv` | ArXiv paper search and retrieval |
| Aliyun Audio Toolkit | `audio_aliyun` | Aliyun audio processing (TTS, STT) |
| Audio Toolkit | `audio` | General audio processing |
| Document Toolkit | `document` | Document processing (PDF, Word, etc.) |
| File Edit Toolkit | `file_edit` | File editing operations |
| GitHub Toolkit | `github` | GitHub API operations |
| Gmail Toolkit | `gmail` | Gmail email operations |
| Image Toolkit | `image` | Image processing and generation |
| Serper Toolkit | `serper` | Google search via Serper API |
| Tabular Data Toolkit | `tabular_data` | CSV/Excel data processing |
| User Interaction Toolkit | `user_interaction` | User input/output operations |
| Video Toolkit | `video` | Video processing |
| Wikipedia Toolkit | `wikipedia` | Wikipedia search and retrieval |

---

## Agent Architecture

The agent system is built on a hierarchical class structure located in `noesium/core/agent/`:

```
BaseAgent (abstract)
├── BaseGraphicAgent (LangGraph-based)
│   ├── BaseHitlAgent (conversation-style agents)
│   └── BaseResearcher (research-style agents)
```

### Base Classes

**BaseAgent** - Provides common functionality:
- LLM client management with instructor support
- Token usage tracking
- Logging capabilities
- Configuration management
- Error handling patterns

**BaseGraphicAgent** - Extends BaseAgent with LangGraph support:
- LangGraph state management
- Graph building abstractions
- Graph export functionality (PNG/Mermaid formats)

**BaseHitlAgent** - For conversation-style agents:
- Session management patterns
- Message handling abstractions
- Conversation state management
- Response generation patterns

**BaseResearcher** - For research-style agents:
- Research workflow patterns
- Source management
- Query generation abstractions
- Result compilation patterns

---

## Tool System Architecture

The tool system (**Toolify**) is located in `noesium/core/toolify/` and provides:

- **Unified Configuration**: Single `ToolkitConfig` class for all toolkit types
- **LangChain Integration**: Seamless conversion to LangChain `BaseTool` format
- **MCP Support**: Integration with Model Context Protocol servers
- **Registry System**: Automatic discovery and registration of toolkits
- **Permission System**: Secure tool execution with permission checking

### Base Classes

**BaseToolkit** - Synchronous toolkit base class:
- Configuration management
- LangChain tool conversion
- MCP tool conversion
- Tool execution with error handling

**AsyncBaseToolkit** - Asynchronous toolkit base class:
- Extends BaseToolkit with async support
- Lifecycle management (`build()`, `cleanup()`)
- Async context manager support

### Tool Registry

The `ToolkitRegistry` in `noesium/core/toolify/registry.py` manages toolkit registration:

```python
# List all registered toolkits
toolkits = ToolkitRegistry.list_toolkits()

# Check if toolkit is registered
if ToolkitRegistry.is_registered("bash"):
    toolkit_class = ToolkitRegistry.get_toolkit_class("bash")

# Create toolkit instance
toolkit = ToolkitRegistry.create_toolkit("bash", config)
```

### Creating Custom Toolkits

```python
from noesium.core.toolify import AsyncBaseToolkit, register_toolkit

@register_toolkit("my_custom")
class MyCustomToolkit(AsyncBaseToolkit):
    async def get_tools_map(self):
        return {
            "my_tool": self.my_tool_function
        }

    async def my_tool_function(self, input_text: str) -> str:
        return f"Processed: {input_text}"
```

---

## Configuration

### Development Guidelines

**Important:** This project requires Python 3.11+. Always use `uv run` to execute Python scripts or install packages:

```bash
# Run Python scripts
uv run python examples/agents/noe_demo.py

# Install packages
uv run pip install package-name

# Run tests
uv run pytest
```

Do not use `python`, `python3`, or `pip` directly - use `uv run` instead.

### Environment Variables

```bash
# LLM Provider
export NOESIUM_LLM_PROVIDER="openai"  # or "openrouter", "ollama", "llamacpp"

# OpenAI
export OPENAI_API_KEY="sk-..."

# OpenRouter
export OPENROUTER_API_KEY="sk-..."

# Ollama
export OLLAMA_BASE_URL="http://localhost:11434"

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

### ToolkitConfig Structure

```python
from noesium.core.toolify import ToolkitConfig

config = ToolkitConfig(
    name="my_toolkit",
    mode="builtin",  # or "mcp"
    activated_tools=["tool1", "tool2"],  # None for all tools
    config={"api_key": "value"},  # Toolkit-specific config
    llm_provider="openai",
    llm_model="gpt-4",
    llm_config={"temperature": 0.1},
    log_level="INFO",
    enable_tracing=True
)
```

---

## Project Structure

```
noesium/
├── noesium/
│   ├── agents/              # Agent implementations
│   │   ├── noe/         # Research agent with planning
│   │   └── browser_use/     # Browser automation
│   ├── core/
│   │   ├── agent/           # Base agent classes
│   │   ├── toolify/         # Tool system
│   │   ├── llm/             # LLM integration
│   │   ├── memory/          # Memory system
│   │   ├── vector_store/    # Vector storage
│   │   ├── msgbus/          # Message bus
│   ├── toolkits/            # 17+ built-in toolkits
├── examples/                # Usage examples
├── specs/                   # Design specifications
└── tests/                   # Test suites
```