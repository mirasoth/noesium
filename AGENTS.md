# Agents and Tools in Noesium

This document provides an overview of all available agents and tools in the Noesium framework.

## Table of Contents

- [Agents](#agents)
  - [AskuraAgent](#askuraagent)
  - [SearchAgent](#searchagent)
  - [DeepResearchAgent](#deepresearchagent)
  - [MemoryAgent](#memoryagent)
- [Toolkits](#toolkits)
  - [Search Toolkit](#search-toolkit)
  - [Bash Toolkit](#bash-toolkit)
  - [Memory Toolkit](#memory-toolkit)
  - [Python Executor Toolkit](#python-executor-toolkit)
  - [Other Toolkits](#other-toolkits)
- [Agent Architecture](#agent-architecture)
- [Tool System Architecture](#tool-system-architecture)
- [Configuration](#configuration)
- [Examples](#examples)

---

## Agents

### AskuraAgent

**Location:** `noesium/agents/askura_agent/`

**Purpose:** A dynamic agent designed to collect target semi-structured information via conversation. The agent adapts to user communication styles and maintains conversation purpose alignment through human-in-the-loop workflows.

**Key Features:**
- Human-in-the-loop (HITL) conversation flow
- LLM-enhanced context analysis and message routing
- Information extraction with configurable slots
- Memory retrieval and retention
- Reflection-based knowledge gap analysis
- Automatic summarization when conversation completes
- Session management with persistence

**Components:**
- `askura_agent.py` - Main agent implementation
- `conversation.py` - Conversation management
- `extractor.py` - Information extraction
- `reflection.py` - Knowledge reflection
- `summarizer.py` - Conversation summarization
- `memory.py` - Memory management
- `models.py` - Data models (AskuraConfig, InformationSlot, etc.)
- `prompts.py` - Prompt templates

**Graph Workflow:**
```
START → context_analysis → message_dispatcher → [conditional routing]
    → start_deep_thinking → information_extractor → memory_retrival
    → reflection → memory_retention → next_action → [conditional routing]
    → response_generator → human_review → summarizer → END
```

**Demo:** `examples/agents/askura_agent_demo.py`

---

### SearchAgent

**Location:** `noesium/agents/search/`

**Purpose:** Web search agent with optional AI crawling capabilities for finding and processing web content.

**Key Features:**
- Query polishing using LLM for better search effectiveness
- Multi-engine search support (Tavily, DuckDuckGo)
- Optional web content crawling
- Result reranking using LLM
- Configurable search depth and timeout
- Support for adaptive crawling

**Graph Workflow:**
```
START → polish_query → web_search → crawl_web → [conditional routing]
    → rank_results → finalize_search → END
```

**Configuration Options:**
- `polish_query` - Enable/disable query polishing
- `rerank_results` - Enable/disable result reranking
- `search_engines` - List of search engines to use
- `max_results_per_engine` - Maximum results per engine
- `crawl_content` - Enable content crawling
- `content_format` - Output format (markdown, html, text)
- `adaptive_crawl` - Enable adaptive crawling
- `crawl_depth` - Maximum crawl depth

**Demo:** `examples/agents/search_agent_demo.py`

---

### DeepResearchAgent

**Location:** `noesium/agents/deep_research/`

**Purpose:** Advanced research agent using LangGraph and LLM integration for comprehensive, iterative research tasks with citations.

**Key Features:**
- Iterative query generation with structured output
- Multi-source web research with citations
- LLM-powered reflection and knowledge gap analysis
- Automatic follow-up query generation
- Configurable research loops and temperature settings
- Comprehensive final answer generation

**Components:**
- `agent.py` - Main agent implementation
- `state.py` - State classes (QueryState, ResearchState, WebSearchState, ReflectionState)
- `schemas.py` - Pydantic schemas (Reflection, SearchQueryList)
- `prompts.py` - Prompt templates

**Graph Workflow:**
```
START → generate_query → web_research → reflection → [conditional evaluation]
    → web_research (if more research needed) OR finalize_answer → END
```

**Configuration Options:**
- `number_of_initial_queries` - Number of initial search queries (default: 3)
- `max_research_loops` - Maximum research iterations (default: 3)
- `query_generation_temperature` - Temperature for query generation
- `web_search_temperature` - Temperature for web search
- `reflection_temperature` - Temperature for reflection analysis
- `answer_temperature` - Temperature for final answer
- `search_engines` - List of search engines
- `web_search_citation_enabled` - Enable citation generation

**Demo:** `examples/agents/deep_research_demo.py`

---

### MemoryAgent

**Location:** `noesium/core/memory/memu/memory/memory_agent.py`

**Purpose:** Memory management agent with action-based architecture for storing, categorizing, and retrieving memories.

**Key Features:**
- Action-based architecture with independent modules
- Function calling interface for LLM integration
- Multiple memory categories (activity, event, profile, etc.)
- Embedding-based semantic search and linking
- Memory clustering and categorization
- Theory of mind analysis
- Iterative conversation processing

**Available Actions:**
- `add_activity_memory` - Store activity memories
- `get_available_categories` - Get available memory categories
- `link_related_memories` - Link related memories using embeddings
- `generate_memory_suggestions` - Generate memory suggestions
- `update_memory_with_suggestions` - Update categories with suggestions
- `run_theory_of_mind` - Analyze theory of mind
- `cluster_memories` - Cluster memories into categories

**Demos:**
- `examples/memory/memu/basic_memory_agent.py`
- `examples/memory/memu/advanced_memory_agent.py`

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
- Automatic shell recovery
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

The agent system is built on a hierarchical class structure located in `noesium/core/agent/base.py`:

```
BaseAgent (abstract)
├── BaseGraphicAgent (LangGraph-based)
│   ├── BaseConversationAgent (conversation-style agents)
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

**BaseConversationAgent** - For conversation-style agents:
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
uv run python examples/agents/search_agent_demo.py

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

## Examples

### Agent Examples

Located in `examples/agents/`:
- `askura_agent_demo.py` - Interactive trip planning demo
- `search_agent_demo.py` - Web search demo
- `deep_research_demo.py` - Deep research demo

### Tool Examples

Located in `examples/tools/tools_demo.py` - Comprehensive tool system demonstration.

### Memory Examples

Located in `examples/memory/memu/`:
- `basic_memory_agent.py` - Basic memory operations
- `advanced_memory_agent.py` - Advanced memory with embeddings

---

## Additional Documentation

- **Design Specifications (RFCs):** Located in `specs/` directory
  - [rfc-index.md](specs/rfc-index.md) - Index of all RFCs
  - [RFC-0001](specs/rfc-0001.md) - System overview
  - [RFC-0002](specs/rfc-0002.md) - Goalith (goal management)
  - [RFC-0003](specs/rfc-0003.md) - Toolify (tool management)
  - [RFC-0004](specs/rfc-0004.md) - Orchestrix (orchestration)
- **Toolify README:** `noesium/core/toolify/README.md`
- **Askura Agent README:** `noesium/agents/askura_agent/README.md`

---

## Project Structure

```
noesium/
├── noesium/
│   ├── agents/              # Agent implementations
│   │   ├── askura_agent/    # Conversation agent
│   │   ├── search/          # Search agent
│   │   └── deep_research/   # Research agent
│   ├── core/
│   │   ├── agent/           # Base agent classes
│   │   ├── toolify/         # Tool system
│   │   ├── llm/             # LLM integration
│   │   ├── memory/          # Memory system
│   │   ├── goalith/         # Goal management
│   │   ├── vector_store/    # Vector storage
│   │   ├── msgbus/          # Message bus
│   │   ├── routing/         # Model routing
│   │   └── tracing/         # Token tracking
│   └── toolkits/            # 17+ built-in toolkits
├── examples/                # Usage examples
├── specs/                   # Design specifications
└── tests/                   # Test suites
```