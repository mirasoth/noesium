# NoeAgent Prompts

Versioned prompt templates for NoeAgent autonomous research agent.

## Overview

This directory contains production-ready prompt templates used by NoeAgent in both ASK and AGENT modes. Each prompt is a markdown file with YAML frontmatter for metadata.

## Prompt Files

| File | Purpose | Required Variables |
|------|---------|-------------------|
| `ask_system.md` | Read-only Q&A mode prompt | `memory_context` |
| `agent_system.md` | Autonomous agent prompt | `plan`, `execution_hint`, `completed_results`, `tool_descriptions` |
| `planning.md` | Task decomposition | `goal`, `context` (optional) |
| `reflection.md` | Progress assessment | `goal`, `plan_steps`, `completed_results` |
| `revise_plan.md` | Plan revision | `goal`, `original_steps`, `feedback`, `completed_results` |
| `finalize.md` | Adaptive answer synthesis (simple / complex / full report) | `goal`, `results`; optional: `current_datetime` |

## Usage

```python
from noesium.noeagent.prompts import get_prompt_manager

pm = get_prompt_manager()

# Render a prompt with required variables
system = pm.render(
    "agent_system",
    plan="Search for recent AI research papers",
    execution_hint="Use appropriate tools for search and analysis",
    completed_results="None yet.",
    tool_descriptions="- web_search: Web search\n- arxiv: ArXiv paper search",
)
```

## Template Engine

All prompts use Python's `str.format()` template engine. Variables are substituted using `{variable_name}` syntax.

## Metadata Schema

Each prompt includes YAML frontmatter:

```yaml
---
name: prompt_name
version: "1.0.0"
created: "2026-03-04"
author: "NoeAgent Team"
description: "Brief description"
required_variables:
  - var1
  - var2
optional_variables:
  var3: "default_value"
template_engine: format
---
```

## Capabilities Documented

Prompts document **default built-in** capabilities only; additional toolkits or subagents may be configured at runtime.

- **Default built-in toolkits** (from `NoeConfig.enabled_toolkits`): bash, file_edit, document, image, python_executor, tabular_data, web_search, user_interaction. The actual tool list shown to the agent is built at runtime from the capability registry and injected as `{tool_descriptions}` in the agent system prompt.

- **Default built-in subagents** (from `DEFAULT_AGENT_SUBAGENTS`): **browser_use** (web automation, form filling, DOM interaction), **tacitus** (research, multi-source synthesis). Invocation uses subagent action `invoke_builtin` with `name` set to the built-in name and `message` for the task.

- **Execution modes** (planning/revise): tool, subagent, external_subagent, builtin_agent, auto.

## Safety and Optimization

Prompts align with safety and optimization practices similar to Claude Code: no time estimates, professional objectivity, safe tool use (no destructive actions without user request, prefer specialized tools over bash for file operations), and quality standards (accuracy, no fabrication, cite sources in finalize). Security-related guidance supports authorized testing and refuses malicious or destructive requests.

## Versioning

Prompts are versioned following semantic versioning:
- Major version: Breaking changes to structure or required variables
- Minor version: New optional features or content improvements
- Patch version: Bug fixes, clarifications, documentation updates

## Contributing

When updating prompts:
1. Update the `version` field in frontmatter
2. Update the `created` or add `modified` date
3. Document changes in the prompt's markdown comments
4. Test with all required and optional variables
5. Update this README if structure changes

## Architecture

Prompts are loaded from package resources using `importlib.resources`, enabling:
- Version control and history tracking
- Separation from source code
- Easy updates without code changes
- Package distribution with prompts included
- Caching for performance