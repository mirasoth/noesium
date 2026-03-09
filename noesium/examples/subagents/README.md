# Subagent Examples

This directory contains example scripts demonstrating how to use the built-in subagents.

## Available Examples

### 1. PlanAgent Demo (`plan_demo.py`)

Demonstrates how to use PlanAgent to create implementation plans.

```bash
python examples/subagents/plan_demo.py
```

**What it shows:**
- Creating a PlanAgent instance
- Streaming progress events
- Receiving a structured implementation plan
- Handling plan steps and clarification questions

### 2. ExploreAgent Demo (`explore_demo.py`)

Demonstrates how to use ExploreAgent to gather information.

```bash
python examples/subagents/explore_demo.py
```

**What it shows:**
- Creating an ExploreAgent instance
- Streaming exploration progress
- Gathering findings and sources
- Receiving synthesized exploration results

### 3. PlanAgent + ExploreAgent Integration (`plan_calls_explore_demo.py`)

Demonstrates how both agents work together under NoeAgent orchestration.

```bash
python examples/subagents/plan_calls_explore_demo.py
```

**What it shows:**
- NoeAgent initialization
- Task routing to appropriate subagents
- PlanAgent calling ExploreAgent when needed
- End-to-end task execution

**Requirements:**
- Requires NoeAgent to be fully configured
- LLM provider must be set up (e.g., OpenAI API key)
- Necessary dependencies installed

## Running the Examples

### Prerequisites

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Set up your LLM provider:
   ```bash
   export NOESIUM_LLM_PROVIDER=openai
   export OPENAI_API_KEY=your-api-key
   ```

### Direct Usage (Standalone)

For standalone subagent usage:

```python
import asyncio
from noesium.subagents import PlanAgent

async def main():
    agent = PlanAgent()
    plan = await agent.run("Plan how to implement a REST API")
    print(plan)

asyncio.run(main())
```

### With NoeAgent Orchestration

For integrated usage with NoeAgent:

```python
import asyncio
from noeagent.agent import NoeAgent
from noeagent.config import NoeConfig, NoeMode

async def main():
    config = NoeConfig(mode=NoeMode.AGENT)
    agent = NoeAgent(config)
    result = await agent.run("Your task here")
    print(result)

asyncio.run(main())
```

## Progress Events

All subagents emit progress events during execution:

- `SESSION_START` - Agent session started
- `THINKING` - Agent is processing/thinking
- `TOOL_START` - Tool invocation started
- `TOOL_END` - Tool invocation completed
- `PLAN_CREATED` - Plan generated (PlanAgent)
- `PLAN_REVISED` - Plan updated (PlanAgent)
- `STEP_START` - Step started
- `STEP_COMPLETE` - Step completed
- `PARTIAL_RESULT` - Incremental result available
- `FINAL_ANSWER` - Final result ready
- `SESSION_END` - Agent session ended

## Customizing Subagent Behavior

You can customize subagent behavior through configuration:

```python
from noesium.subagents import PlanAgent, ExploreAgent

# PlanAgent with more planning loops
planner = PlanAgent(
    llm_provider="openai",
    max_planning_loops=5,
    planning_temperature=0.7,
)

# ExploreAgent with deeper exploration
explorer = ExploreAgent(
    llm_provider="openai",
    max_exploration_depth=5,
    exploration_temperature=0.5,
)
```

## Integration with NoeAgent

When using subagents through NoeAgent, they are automatically:

1. **Registered**: All enabled subagents are registered with the subagent manager
2. **Routed**: Tasks are intelligently routed to appropriate subagents
3. **Monitored**: Progress events are tracked and logged
4. **Coordinated**: Subagents can call each other when needed

Example NoeAgent configuration:

```python
from noeagent.config import NoeConfig

config = NoeConfig(
    mode=NoeMode.AGENT,
    enable_subagents=True,
    subagent_max_depth=2,  # Allow subagent-to-subagent calls
)

# Subagents are configured in config.builtin
# You can customize them through the config file
```

## Further Reading

- [PlanAgent Documentation](../../noesium/src/noesium/subagents/plan/)
- [ExploreAgent Documentation](../../noesium/src/noesium/subagents/explore/)
- [NoeAgent Configuration Guide](../../docs/user_guides/toolkit_configuration_guide.md)