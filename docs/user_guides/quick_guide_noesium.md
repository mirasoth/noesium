# Noesium Quick Guide

Comprehensive guide for users and developers of the Noesium cognitive agentic framework.

## Table of Contents

- [Noesium Quick Guide](#noesium-quick-guide)
  - [Table of Contents](#table-of-contents)
  - [For Users](#for-users)
    - [Installation](#installation)
    - [Basic Usage](#basic-usage)
      - [LLM Client](#llm-client)
    - [Using Built-in Agents](#using-built-in-agents)
      - [AskuraAgent](#askuraagent)
      - [BrowserUseAgent](#browseruseagent)
      - [TacitusAgent](#tacitusagent)
    - [Environment Configuration](#environment-configuration)
    - [Configuration File](#configuration-file)
  - [For Developers](#for-developers)
    - [Creating Custom Agents](#creating-custom-agents)
      - [Agent Types](#agent-types)
    - [Using Toolkits](#using-toolkits)
      - [Available Toolkits](#available-toolkits)
    - [Agent Architecture](#agent-architecture)
    - [Subagent Interface (RFC-1008)](#subagent-interface-rfc-1008)
    - [Memory System](#memory-system)
    - [Event System](#event-system)
  - [Advanced Features](#advanced-features)
    - [Structured Output](#structured-output)
    - [Vector Stores](#vector-stores)
    - [Model Routing](#model-routing)
    - [Multi-Agent Coordination](#multi-agent-coordination)
    - [Durable Execution](#durable-execution)
  - [Error Handling](#error-handling)
    - [Exception Hierarchy](#exception-hierarchy)
    - [Content Policy Errors](#content-policy-errors)
  - [Best Practices](#best-practices)
    - [Agent Design](#agent-design)
    - [Performance](#performance)
  - [Troubleshooting](#troubleshooting)
    - [Common Issues](#common-issues)
    - [Debugging](#debugging)
    - [Exported Classes](#exported-classes)
    - [Support](#support)
  - [Next Steps](#next-steps)

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
from noesium import get_llm_client
from noesium.core.llm import BaseLLMClient

# Create client using factory (supports openai, openrouter, ollama, llamacpp, litellm)
client = get_llm_client(
    provider="openai",
    api_key="sk-...",
    chat_model="gpt-4o",        # Optional: specify model
    vision_model="gpt-4o",      # Optional: for vision tasks
    embed_model="text-embedding-3-small",  # Optional: for embeddings
)

# Chat completion
response = client.completion(messages=[{"role": "user", "content": "Hello!"}])

# Structured output with Pydantic
from pydantic import BaseModel, Field

class Answer(BaseModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)

# structured_output=True is the default
result = client.structured_completion(
    messages=[{"role": "user", "content": "What is 2+2?"}],
    response_model=Answer
)
print(result.text)  # "4"
print(result.confidence)  # 1.0
```

**Using Specific Client Classes:**

```python
from noesium.core.llm import (
    BaseLLMClient,
    OpenAIClient,
    OpenRouterClient,
    OllamaClient,
    LlamaCppClient,
    LitellmClient,
)

# Use specific client directly
client = OpenAIClient(
    api_key="sk-...",
    chat_model="gpt-4o",
    instructor=True,  # Enable structured output
)

# OpenRouter for multiple model providers
client = OpenRouterClient(
    api_key="...",
    chat_model="anthropic/claude-sonnet-4",
)

# Ollama for local models
client = OllamaClient(
    base_url="http://localhost:11434",
    chat_model="llama3.2",
)

# LlamaCPP for local GGUF models
client = LlamaCppClient(
    model_path="/path/to/model.gguf",
    n_ctx=4096,
    n_gpu_layers=35,
)

# LiteLLM proxy
client = LitellmClient(
    chat_model="gpt-4o",
    api_key="...",
)
```

**Supported Providers:**

| Provider | Description | Key Parameters |
|----------|-------------|----------------|
| `openai` | OpenAI GPT models | `api_key`, `base_url`, `chat_model` |
| `openrouter` | OpenRouter API | `api_key`, `chat_model` |
| `ollama` | Local Ollama | `base_url` (default: `http://localhost:11434`) |
| `llamacpp` | Local LlamaCPP | `model_path`, `n_ctx`, `n_gpu_layers` |
| `litellm` | LiteLLM proxy | `chat_model`, `api_key` |

**BaseLLMClient Methods:**

| Method | Description |
|--------|-------------|
| `completion(messages, **kwargs)` | Standard chat completion |
| `structured_completion(messages, response_model, **kwargs)` | Structured output with Pydantic model |
| `count_tokens(text)` | Count tokens in text |
| `get_token_usage()` | Get cumulative token usage statistics |

### Using Built-in Agents

Noesium provides several built-in subagents for common tasks:

#### AskuraAgent

General-purpose conversation agent with adaptive communication:

```python
from noesium import AskuraAgent, AskuraConfig

# Create agent with custom config
config = AskuraConfig(
    max_turns=10,
    extraction_slots=["name", "email", "purpose"],
)
agent = AskuraAgent(config)

# Start a conversation
response = agent.start_conversation(
    session_id="user_123",
    initial_message="Hello! I need help with my account."
)
print(response.message)

# Continue conversation
response = agent.continue_conversation(
    session_id="user_123",
    user_message="My name is Alice and I need to reset my password."
)

# Check extracted information
print(response.extracted_info)  # {"name": "Alice", ...}
```

#### BrowserUseAgent

Web automation agent (lazy-loaded due to heavy dependencies):

```python
from noesium import BrowserUseAgent

# Create agent
agent = BrowserUseAgent(
    llm=my_llm_client,  # Optional: uses default if not provided
    headless=True,       # Run in headless mode
)

# Run web automation task
result = await agent.run("Navigate to example.com and extract the main content")
print(result)
```

**Note:** BrowserUseAgent requires `noesium[browser-use]` extra dependencies.

#### TacitusAgent

Advanced research agent with iterative refinement:

```python
from noesium import TacitusAgent

# Create agent with custom settings
agent = TacitusAgent(
    max_research_loops=3,
    number_of_initial_queries=2,
)

# Run research
result = await agent.research("Latest developments in renewable energy")
print(result)
```

**Features:**
- Iterative query generation
- Multi-source web search
- Reflection-based quality control
- Graceful error handling for content policy violations

### Environment Configuration

Set environment variables for configuration:

```bash
# LLM Provider (default: openai)
export NOESIUM_LLM_PROVIDER="openai"  # or "openrouter", "ollama", "llamacpp", "litellm"

# OpenAI
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="..."  # Optional: custom endpoint
export OPENAI_CHAT_MODEL="gpt-4o"

# OpenRouter
export OPENROUTER_API_KEY="..."
export OPENROUTER_CHAT_MODEL="anthropic/claude-sonnet-4"

# Ollama (local)
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_CHAT_MODEL="llama3.2"

# LlamaCPP (local)
export LLAMACPP_MODEL_PATH="/path/to/model.gguf"

# Vector Store
export NOESIUM_VECTOR_STORE_PROVIDER="weaviate"  # or "pgvector"
export NOESIUM_EMBEDDING_DIMS="768"

# Tracing (OPIK)
export NOESIUM_OPIK_TRACING="true"

# Logging
export LOG_LEVEL="INFO"
export NOESIUM_FILE_LOG_LEVEL="DEBUG"
```

### Configuration File

Noesium uses a JSON configuration file located at `~/.noesium/config.json` by default:

```python
from noesium import load_config, save_config, FrameworkConfig

# Load config (creates default if not exists)
config = load_config()

# Modify settings
config.llm.provider = "openrouter"
config.agent.max_iterations = 50
config.tools.enabled_toolkits = ["bash", "web_search", "python_executor"]

# Save changes
save_config(config)

# Or create from scratch
config = FrameworkConfig(
    llm={"provider": "openai"},
    agent={"max_iterations": 30},
)
save_config(config)
```

**Configuration precedence (highest to lowest):**
1. Environment variables
2. Config file (`~/.noesium/config.json`)
3. Default values

---

## For Developers

### Creating Custom Agents

Extend the base agent classes to create custom agents:

```python
from noesium import BaseGraphicAgent, get_llm_client
from langgraph.graph import StateGraph
from typing import TypedDict

class MyState(TypedDict):
    messages: list
    result: str

class MyAgent(BaseGraphicAgent):
    def __init__(self, llm_client=None):
        super().__init__(llm_client or get_llm_client())
    
    def get_state_class(self):
        return MyState
    
    def _build_graph(self) -> StateGraph:
        # Define your agent's workflow graph
        graph = StateGraph(MyState)
        # Add nodes and edges...
        return graph

agent = MyAgent()
result = await agent.arun("What is the meaning of life?")
```

#### Agent Types

| Class | Description |
|-------|-------------|
| `BaseAgent` | Abstract base class with LLM client, logging, token tracking |
| `BaseGraphicAgent` | LangGraph-based agent with state management and graph export |
| `AskuraAgent` | Conversation agent with session management |
| `TacitusAgent` | Research agent with source management and structured output |
| `BrowserUseAgent` | Web automation agent (lazy-loaded) |

### Using Toolkits

Access built-in toolkits through the Toolify system:

```python
from noesium import get_toolkit, get_toolkits_map, ToolkitRegistry
from noesium import AtomicTool, ToolExecutor, ToolContext, ToolPermission, ToolSource
from noesium.toolkits import (
    TOOLKIT_BASH,
    TOOLKIT_WEB_SEARCH,
    TOOLKIT_PYTHON_EXECUTOR,
)

# Get a specific toolkit
bash = get_toolkit(TOOLKIT_BASH)
result = await bash.list_directory(".")

# Get all registered toolkits
toolkits = get_toolkits_map()
for name, toolkit_class in toolkits.items():
    print(f"{name}: {toolkit_class}")

# List registered toolkits
for name in ToolkitRegistry.list_toolkits():
    print(name)

# Using AtomicTool for event-wrapped execution (RFC-2004)
tool = AtomicTool(
    name="my_tool",
    description="A custom tool",
    func=lambda x: f"Processed: {x}",
    permission=ToolPermission.READ,
    source=ToolSource.BUILTIN,
)
result = await tool.execute(ToolContext(), "input data")
```

**Toolkit Base Classes:**

```python
from noesium.core.toolify import BaseToolkit, AsyncBaseToolkit, ToolkitConfig

# Create custom toolkit
class MyToolkit(AsyncBaseToolkit):
    def __init__(self, config: ToolkitConfig = None):
        super().__init__(config)
    
    async def get_tools_map(self):
        return {"my_tool": self.my_tool}
    
    async def my_tool(self, input_text: str) -> str:
        return f"Processed: {input_text}"
```

**Skill System:**

```python
from noesium.core.toolify import Skill, SkillRegistry

# Skills are reusable tool compositions
skill = Skill(
    name="data_analysis",
    description="Analyze data files",
    tools=["python_executor", "tabular_data"],
)

# Register and use skills
registry = SkillRegistry()
registry.register(skill)
```

**Tool Registry:**

```python
from noesium.core.toolify import ToolRegistry

# ToolRegistry provides unified tool lookup
registry = ToolRegistry()
tool = registry.get_tool("bash.run_bash")
```

#### Available Toolkits

| Toolkit | Registration Name | Description |
|---------|------------------|-------------|
| Bash | `bash` | Shell command execution, file operations |
| File Edit | `file_edit` | File editing operations |
| Python Executor | `python_executor` | Python code execution |
| Web Search | `web_search` | Multi-engine web search (Tavily, DuckDuckGo) |
| Document | `document` | PDF/Word document processing |
| Image | `image` | Image processing and generation |
| Tabular Data | `tabular_data` | CSV/Excel data processing |
| User Interaction | `user_interaction` | User prompts and input |
| Jina Research | `jina_research` | Research via Jina Reader API |
| Memory | `memory` | Memory slot operations |
| ArXiv | `arxiv` | Academic paper search |
| Wikipedia | `wikipedia` | Wikipedia search and retrieval |
| Serper | `serper` | Google search via Serper API |
| GitHub | `github` | GitHub API operations |
| Gmail | `gmail` | Gmail email operations |
| Video | `video` | Video processing |
| Audio | `audio` | Audio processing |
| MCP | `mcp` | Model Context Protocol integration |

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

### Subagent Interface (RFC-1008)

Noesium provides a standardized interface for subagent integration:

```python
from noesium.core.agent import (
    SubagentContext,
    SubagentDescriptor,
    SubagentProgressEvent,
    SubagentProtocol,
    BaseSubagentRuntime,
    SubagentManager,
    SubagentProvider,
)

# Define a subagent descriptor
descriptor = SubagentDescriptor(
    name="my_subagent",
    description="A custom subagent for specific tasks",
    capabilities=["analysis", "summarization"],
    input_schema={"text": "string"},
    output_schema={"result": "string"},
)

# Create subagent context
context = SubagentContext(
    session_id="session-123",
    parent_agent_id="agent-456",
    task="Analyze this document",
)

# Use SubagentManager to orchestrate subagents
manager = SubagentManager()
result = await manager.invoke(
    subagent_id="tacitus",
    context=context,
    input_data={"query": "quantum computing"},
)
```

**Subagent Interface Classes:**

| Class | Description |
|-------|-------------|
| `SubagentProtocol` | Protocol defining subagent interface |
| `SubagentDescriptor` | Metadata describing subagent capabilities |
| `SubagentContext` | Execution context with session info |
| `SubagentProgressEvent` | Progress events from subagent execution |
| `BaseSubagentRuntime` | Base class for subagent implementations |
| `SubagentManager` | Orchestrates subagent lifecycle and invocation |
| `SubagentProvider` | Factory for creating subagent instances |

**Built-in Subagent Names:**

```python
from noesium.subagents import (
    SUBAGENT_ASKURA,       # "askura"
    SUBAGENT_BROWSER_USE,  # "browser_use"
    SUBAGENT_CLAUDE,       # "claude"
    SUBAGENT_TACITUS,      # "tacitus"
)
```

### Memory System

The memory system provides multi-tier storage with provider-based architecture (RFC-2002):

```python
from noesium import (
    MemoryManager,
    DurableMemory,
    EphemeralMemory,
    SemanticMemory,
    MemoryProvider,
    MemoryTier,
    ProviderMemoryManager,
)

# Using MemoryManager (high-level API)
memory = MemoryManager()
await memory.remember("important fact", metadata={"type": "fact"})
items = await memory.recall("fact")

# Using Provider Memory Manager (provider-based API)
provider_manager = ProviderMemoryManager()
await provider_manager.register_provider(
    provider_id="working",
    provider=MemoryProvider(tier=MemoryTier.WORKING),
)

# Memory tiers
# - WORKING: Short-term, in-memory storage
# - EPHEMERAL: Session-based storage
# - DURABLE: Persistent storage with event sourcing
# - SEMANTIC: Vector-based semantic search
```

**Memory Provider Types:**

| Class | Tier | Description |
|-------|------|-------------|
| `EphemeralMemory` | EPHEMERAL | Session-based, cleared on restart |
| `DurableMemory` | DURABLE | Persistent with event sourcing |
| `SemanticMemory` | SEMANTIC | Vector-based semantic search |

**Memory Models:**

| Class | Description |
|-------|-------------|
| `MemoryItem` | Individual memory entry with content and metadata |
| `MemoryFilter` | Filter criteria for memory queries |
| `MemoryStats` | Statistics about memory usage |
| `SearchResult` | Result from memory search operations |
| `MemoryEntry` | Provider-level memory entry |
| `RecallQuery` | Query specification for recall operations |
| `RecallResult` | Result from recall operations |
| `RecallScope` | Scope definition for recall queries |

**Memory Events:**

```python
from noesium.core.memory import (
    MemoryDeleted,
    MemoryLinked,
    MemoryProviderRegistered,
)
```

All memory operations are event-backed for durability and replayability.

### Event System

The event system enables distributed coordination with event-sourced architecture:

```python
from noesium import (
    EventEnvelope,
    EventStore,
    InMemoryEventStore,
    FileEventStore,
    ProgressEvent,
    ProgressEventType,
    ProgressCallback,
)

# Create event store
store = InMemoryEventStore()  # Or FileEventStore("/path/to/events")

# Create event envelope
envelope = EventEnvelope(
    event_type="task_requested",
    payload={"task": "analyze data"},
    correlation_id="trace-123",
)

# Append and read events
await store.append(envelope)
events = await store.read_stream("stream-123")

# Progress tracking
progress = ProgressEvent(
    event_type=ProgressEventType.TASK_STARTED,
    message="Processing data...",
)
```

**Domain Events:**

```python
from noesium.core.event import (
    # Agent lifecycle
    AgentStarted,
    AgentStopped,
    # Task coordination
    TaskRequested,
    TaskCompleted,
    # Capability system
    CapabilityRegistered,
    CapabilityInvoked,
    CapabilityCompleted,
    # Memory events
    MemoryWritten,
    # Error handling
    ErrorOccurred,
    # Base class
    DomainEvent,
)
```

**Event Envelope Components:**

| Class | Description |
|-------|-------------|
| `EventEnvelope` | Container for domain events with metadata |
| `AgentRef` | Reference to an agent in the system |
| `TraceContext` | Distributed tracing context |
| `SignatureBlock` | Cryptographic signature for event integrity |

**Codec Functions:**

```python
from noesium.core.event import canonicalize, serialize, deserialize

# Serialize event for storage/transmission
data = serialize(envelope)

# Deserialize back to envelope
restored = deserialize(data)

# Canonicalize for hashing/signing
canonical = canonicalize(envelope)
```

**Event System Features:**
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

client = get_llm_client(provider="openai")  # structured_output=True by default
result = client.structured_completion(
    messages=[{"role": "user", "content": "Generate search queries about AI"}],
    response_model=ResearchQuery
)
print(result.queries)  # ["artificial intelligence history", "AI applications", ...]
```

### Vector Stores

Noesium supports multiple vector store backends:

```python
from noesium import get_vector_store, BaseVectorStore
from noesium.core.vector_store import WeaviateVectorStore, PGVectorStore

# Using factory function (recommended)
# Weaviate (cloud or local)
weaviate = get_vector_store(
    provider="weaviate",
    collection_name="my_collection",
    cluster_url="https://your-cluster.weaviate.network",
)

# PGVector (PostgreSQL with pgvector extension)
pgvector = get_vector_store(
    provider="pgvector",
    collection_name="embeddings",
    dbname="vectordb",
    user="postgres",
    password="postgres",
    host="localhost",
    port="5432",
)

# Or use specific classes directly
weaviate = WeaviateVectorStore(
    collection_name="my_collection",
    embedding_model_dims=768,
    cluster_url="https://your-cluster.weaviate.network",
)

pgvector = PGVectorStore(
    collection_name="embeddings",
    embedding_model_dims=768,
    dbname="vectordb",
    user="postgres",
    password="postgres",
)

# Add vectors
await weaviate.add_embeddings(
    ids=["doc1", "doc2"],
    embeddings=[[0.1, 0.2, ...], [0.3, 0.4, ...]],
    metadatas=[{"source": "web"}, {"source": "file"}],
)

# Search
results = await weaviate.search(query_embedding=[0.1, 0.2, ...], top_k=5)
```

**Vector Store Providers:**

| Provider | Class | Description |
|----------|-------|-------------|
| `weaviate` | `WeaviateVectorStore` | Weaviate cloud or local instance |
| `pgvector` | `PGVectorStore` | PostgreSQL with pgvector extension |

**Configuration:**

```bash
# Environment variables
export NOESIUM_VECTOR_STORE_PROVIDER="weaviate"  # or "pgvector"
export NOESIUM_EMBEDDING_DIMS="768"
```

**BaseVectorStore Methods:**

| Method | Description |
|--------|-------------|
| `add_embeddings(ids, embeddings, metadatas)` | Add vectors to store |
| `search(query_embedding, top_k)` | Search for similar vectors |
| `delete(ids)` | Delete vectors by ID |
| `get(ids)` | Retrieve vectors by ID |
| `count()` | Get total vector count |

### Model Routing

Noesium provides intelligent model routing to select appropriate LLM tiers based on query complexity:

```python
from noesium import ModelRouter
from noesium.core.routing import (
    BaseRoutingStrategy,
    ModelTier,
    ComplexityScore,
    RoutingResult,
    SelfAssessmentStrategy,
    DynamicComplexityStrategy,
)

# Create router with default strategy
router = ModelRouter()

# Route a query to appropriate model tier
result = router.route("What is the capital of France?")
print(result.tier)  # ModelTier.FAST (simple query)
print(result.model)  # "gpt-4o-mini"

# Complex query routes to more capable model
result = router.route("Analyze the philosophical implications of quantum mechanics")
print(result.tier)  # ModelTier.SMART (complex query)
```

**Model Tiers:**

| Tier | Description | Use Case |
|------|-------------|----------|
| `FAST` | Fast, cost-effective models | Simple queries, classification |
| `BALANCED` | Balance of speed and capability | General tasks |
| `SMART` | Most capable models | Complex reasoning, analysis |

**Routing Strategies:**

| Strategy | Description |
|----------|-------------|
| `SelfAssessmentStrategy` | Asks LLM to assess its own complexity |
| `DynamicComplexityStrategy` | Analyzes query features dynamically |

**Creating Custom Strategies:**

```python
from noesium.core.routing import BaseRoutingStrategy, RoutingResult, ModelTier

class MyStrategy(BaseRoutingStrategy):
    def assess(self, query: str) -> RoutingResult:
        # Custom logic to determine complexity
        if len(query) > 100:
            return RoutingResult(tier=ModelTier.SMART, model="gpt-4o")
        return RoutingResult(tier=ModelTier.FAST, model="gpt-4o-mini")

router = ModelRouter(strategy=MyStrategy())
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

## Error Handling

### Exception Hierarchy

Noesium provides a structured exception hierarchy for proper error handling:

```
NoesiumError (base)
├── EventError
│   ├── EventValidationError
│   └── EventStoreError
├── KernelError
│   ├── NodeExecutionError
│   └── CheckpointError
├── ProjectionError
│   └── ProjectionVersionError
├── CapabilityError
│   └── CapabilityNotFoundError
├── MemoryError
│   ├── ProviderNotFoundError
│   ├── ProviderReadOnlyError
│   └── RecallError
├── ToolError
│   ├── ToolNotFoundError
│   ├── ToolExecutionError
│   ├── ToolTimeoutError
│   ├── ToolPermissionError
│   └── SkillNotFoundError
├── LLMError
│   └── ContentPolicyError
└── Noer
    ├── PlanningError
    ├── ModeError
    └── IterationLimitError
```

**Exported exceptions** (from `noesium`):
- `NoesiumError`, `EventError`, `EventValidationError`, `KernelError`, `NodeExecutionError`
- `MemoryError`, `ProviderNotFoundError`, `CapabilityError`
- `ToolError`, `ToolNotFoundError`, `ToolExecutionError`, `ToolTimeoutError`
- `PlanningError`, `ModeError`, `IterationLimitError`

**Additional exceptions** (from `noesium.core.exceptions`):
- `LLMError`, `ContentPolicyError`, `CheckpointError`, `ProjectionError`, `ProjectionVersionError`
- `EventStoreError`, `CapabilityNotFoundError`
- `ProviderReadOnlyError`, `RecallError`, `ToolPermissionError`, `SkillNotFoundError`

**Exception Categories:**

| Category | Exceptions | Use Case |
|----------|------------|----------|
| Event | `EventError`, `EventValidationError`, `EventStoreError` | Event processing failures |
| Kernel | `KernelError`, `NodeExecutionError`, `CheckpointError` | Agent execution failures |
| Memory | `MemoryError`, `ProviderNotFoundError`, `ProviderReadOnlyError`, `RecallError` | Memory operation failures |
| Tool | `ToolError`, `ToolNotFoundError`, `ToolExecutionError`, `ToolTimeoutError`, `ToolPermissionError`, `SkillNotFoundError` | Tool execution failures |
| LLM | `LLMError`, `ContentPolicyError` | LLM provider failures |
| Capability | `CapabilityError`, `CapabilityNotFoundError` | Capability resolution failures |
| Projection | `ProjectionError`, `ProjectionVersionError` | State projection failures |
| Noe | `PlanningError`, `ModeError`, `IterationLimitError` | NoeAgent-specific failures |

### Content Policy Errors

When an LLM provider rejects content due to policy violations, a `ContentPolicyError` is raised:

```python
from noesium.core.exceptions import ContentPolicyError
from noesium import get_llm_client

client = get_llm_client(provider="openai")

try:
    response = client.completion(messages=[{"role": "user", "content": "..."}])
except ContentPolicyError as e:
    print(f"Content blocked by {e.provider}")
    print(f"Original error: {e.original_error}")
    # Handle gracefully - provide user feedback or alternative approach
```

**Key attributes:**
- `provider`: The LLM provider that rejected the content (e.g., "Dashscope/Alibaba Cloud", "OpenAI")
- `original_error`: The original exception from the provider

**Built-in agents handle this gracefully:**
- TacitusAgent returns informative messages instead of crashing
- Research workflows continue with available data
- Users receive actionable suggestions for resolving the issue

---

## Best Practices

### Agent Design

- **Single responsibility**: Each agent should have one clear purpose
- **Event-driven**: Use events for all state changes and coordination
- **Immutable state**: Derive state from event projections, not direct mutation
- **Capability declaration**: Subscribe to topics that match your agent's abilities
- **Graceful error handling**: Catch and handle `ContentPolicyError` appropriately

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
- Check `~/.noesium/config.json` for persistent settings

**Content Policy Violations**
- Some LLM providers (e.g., Dashscope/Alibaba Cloud) have strict content policies
- Rephrase queries in neutral terms if blocked
- Consider switching to a different provider for sensitive topics
- Built-in agents handle these errors gracefully with informative messages

**Toolkit Activation**
- Check that required dependencies are installed (`noesium[tools]`)
- Use `ToolkitRegistry.list_toolkits()` to see available toolkits
- Verify toolkit configuration in `FrameworkConfig.tools.toolkit_configs`

**Agent Execution**
- Ensure LangGraph dependencies are installed (`noesium[agents]`)
- Check event bus connectivity for multi-agent scenarios
- Use `setup_logging(level="DEBUG")` for verbose output

**Import Errors**
- `BrowserUseAgent` requires `noesium[browser-use]` extra
- `ollama` and `llamacpp` providers require additional dependencies
- Use `pip install noesium[all]` for complete installation

### Debugging

Enable debug logging:

```python
import os
os.environ["LOG_LEVEL"] = "DEBUG"

from noesium import setup_logging, get_logger

# Configure logging
setup_logging(level="DEBUG", enable_colors=True)

# Get a logger for your module
logger = get_logger(__name__)
logger.info("Application started")
```

### Exported Classes

The `noesium` module exports the following classes and functions:

**Tier 1: Main Entry Points**
- `FrameworkConfig`, `load_config`, `save_config` - Configuration management
- `get_llm_client` - LLM client factory
- `BaseAgent`, `BaseGraphicAgent` - Agent base classes

**Tier 2: Core Systems**
- `MemoryManager`, `DurableMemory`, `EphemeralMemory`, `SemanticMemory` - Memory systems
- `AtomicTool`, `ToolExecutor`, `ToolkitRegistry`, `get_toolkit`, `get_toolkits_map` - Tools
- `EventEnvelope`, `EventStore`, `InMemoryEventStore`, `FileEventStore` - Events
- `ProgressEvent`, `ProgressEventType`, `ProgressCallback` - Progress tracking
- `get_vector_store`, `BaseVectorStore` - Vector stores
- `ModelRouter` - Model routing

**Tier 3: Subagents**
- `AskuraAgent`, `AskuraConfig`, `AskuraResponse`, `AskuraState`
- `TacitusAgent`, `ResearchState`
- `BrowserUseAgent` (lazy-loaded)

**Tier 4: Utilities & Exceptions**
- `setup_logging`, `get_logger`
- `NoesiumError`, `ToolError`, `ToolNotFoundError`, `ToolExecutionError`, `ToolTimeoutError`
- `MemoryError`, `ProviderNotFoundError`, `PlanningError`, `ModeError`, `IterationLimitError`
- `EventError`, `EventValidationError`, `KernelError`, `NodeExecutionError`, `CapabilityError`

**Additional exports from submodules:**

| Module | Exports |
|--------|---------|
| `noesium.core.llm` | `BaseLLMClient`, `OpenAIClient`, `OpenRouterClient`, `OllamaClient`, `LlamaCppClient`, `LitellmClient` |
| `noesium.core.memory` | `MemoryProvider`, `MemoryTier`, `ProviderMemoryManager`, `MemoryItem`, `MemoryFilter`, `MemoryStats`, `SearchResult`, `RecallQuery`, `RecallResult`, `RecallScope` |
| `noesium.core.event` | `AgentRef`, `TraceContext`, `SignatureBlock`, `DomainEvent`, `TaskRequested`, `TaskCompleted`, `AgentStarted`, `AgentStopped`, `canonicalize`, `serialize`, `deserialize` |
| `noesium.core.toolify` | `BaseToolkit`, `AsyncBaseToolkit`, `ToolkitConfig`, `ToolContext`, `ToolPermission`, `ToolSource`, `ToolRegistry`, `Skill`, `SkillRegistry` |
| `noesium.core.routing` | `BaseRoutingStrategy`, `ModelTier`, `ComplexityScore`, `RoutingResult`, `SelfAssessmentStrategy`, `DynamicComplexityStrategy` |
| `noesium.core.vector_store` | `WeaviateVectorStore`, `PGVectorStore`, `OutputData` |
| `noesium.core.agent` | `SubagentContext`, `SubagentDescriptor`, `SubagentProgressEvent`, `SubagentProtocol`, `BaseSubagentRuntime`, `SubagentManager`, `SubagentProvider` |
| `noesium.core.exceptions` | `LLMError`, `ContentPolicyError`, `CheckpointError`, `ProjectionError`, `EventStoreError`, `CapabilityNotFoundError`, `ProviderReadOnlyError`, `RecallError`, `ToolPermissionError`, `SkillNotFoundError` |
| `noesium.subagents` | `SUBAGENT_ASKURA`, `SUBAGENT_BROWSER_USE`, `SUBAGENT_CLAUDE`, `SUBAGENT_TACITUS` |
| `noesium.toolkits` | `TOOLKIT_BASH`, `TOOLKIT_WEB_SEARCH`, `TOOLKIT_PYTHON_EXECUTOR`, `TOOLKIT_ARXIV`, `TOOLKIT_AUDIO`, `TOOLKIT_DOCUMENT`, `TOOLKIT_FILE_EDIT`, `TOOLKIT_GITHUB`, `TOOLKIT_GMAIL`, `TOOLKIT_IMAGE`, `TOOLKIT_JINA_RESEARCH`, `TOOLKIT_MCP`, `TOOLKIT_MEMORY`, `TOOLKIT_SERPER`, `TOOLKIT_TABULAR_DATA`, `TOOLKIT_USER_INTERACTION`, `TOOLKIT_VIDEO`, `TOOLKIT_WIKIPEDIA` |

### Support

- **Documentation**: See [AGENTS.md](../../AGENTS.md) for detailed documentation
- **Specifications**: Review RFCs in the [`specs/`](../specs/) directory
- **Examples**: Run examples from the [`examples/`](../../examples/) directory
- **Issues**: Report problems at the [GitHub repository](https://github.com/mirasoth/noesium)

## Next Steps

- **[NoeAgent Guide](quick_guide_noeagent.md)**: Learn about NoeAgent
- **[Voyager Guide](quick_guide_voyager.md)**: 24/7 companion app
- **[Developer Guide](dev_guide.md)**: Detailed framework development
- **[Examples](../../examples/)**: Real-world usage examples
