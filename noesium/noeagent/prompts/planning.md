---
name: planning
version: "1.1.0"
created: "2026-03-04"
modified: "2026-03-04"
author: "NoeAgent Team"
description: "Task planning prompt with execution hints"
required_variables:
  - goal
optional_variables:
  context: ""
  external_subagent_info: ""
  builtin_subagent_info: ""
template_engine: format
---

# Task Planning

Break the following goal into a concise ordered list of actionable steps.

Each step should be one concrete action (search, analyze, compute, write, etc.).

## Output Format

Return a JSON object with a "steps" array where each element has:
- **description**: string describing the step
- **execution_hint**: one of the execution modes below

## Execution Modes

### tool
Use for atomic operations with a single toolkit:
- Search: web_search (default built-in web search)
- File: file_edit (read, write, edit)
- Shell: bash (when no specialized tool fits)
- Data: python_executor, tabular_data, document, image
- User input: user_interaction

### subagent
Delegate to an in-process child agent for multi-step reasoning (complex analysis, persistent context, conditional workflows). Execution hint only; the agent will choose spawn/interact as needed.

### external_subagent
Delegate to an external CLI agent (e.g., Claude Code). Use when:
- Code review, refactoring, complex multi-file editing
- Tasks requiring full shell access or specialized CLI tools

{external_subagent_info}

### builtin_agent
Delegate to a **default built-in** subagent. Available options:

| Built-in | Name | Use for |
|----------|------|--------|
| browser_use | `browser_use` | Real-time web data, form filling, DOM interaction, interactive websites, screenshots |

**Note:** Some specialized agents (like `tacitus` for research) require explicit `/command` invocation and cannot be auto-routed.

**Selection:** Match task keywords to capabilities (e.g., "stock price", "form", "click" → browser_use). The executor uses subagent with action `invoke_builtin` and this name.

{builtin_subagent_info}

### auto
Let the agent decide based on context when the best approach is unclear or multiple modes could work.

## Goal

{goal}

## Context

{context}

## Planning Guidelines

1. Keep steps atomic and actionable.
2. Order steps logically (dependencies before dependents).
3. Choose execution hints that match default built-in tools and subagents only.
4. Consider fallbacks; do not over-specify or estimate time.