---
name: planning
version: "1.0.0"
created: "2026-03-04"
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
Use for atomic operations requiring single tool invocations:
- Search operations (wizsearch, serper, arxiv, wikipedia)
- File operations (read, write, edit)
- Data processing (python_executor, tabular_data)
- API calls (github, gmail, jina_research)

### subagent
Delegate to a child agent for multi-step reasoning:
- Complex analysis requiring multiple steps
- Tasks needing persistent context
- Workflows with conditional logic

### external_subagent
Delegate to an external CLI agent (e.g., Claude Code):
- Code review and refactoring
- Complex multi-file editing
- Tasks requiring full shell access
- Specialized reasoning tasks

{external_subagent_info}

### builtin_agent
Delegate to a built-in specialized agent:
- **browser_use**: Real-time web data, form filling, interactive websites
- **tacitus**: Multi-source research, information synthesis, complex questions

{builtin_subagent_info}

**Selection guidelines:**
- Match task keywords to agent capabilities (e.g., "stock price" → browser_use, "research" → tacitus)
- Use browser_use for: real-time data, DOM interaction, form submissions
- Use tacitus for: research synthesis, multi-source analysis, complex questions

### auto
Let the agent decide based on context. Use when:
- The best approach is unclear
- Multiple modes could work
- Flexibility is needed

## External Subagent Usage

- Use for tasks requiring external agent capabilities (code review, refactoring)
- CLI agents like Claude Code have full file system and shell access
- Ideal for code-heavy tasks, multi-file editing, and complex reasoning

## Goal

{goal}

## Context

{context}

## Planning Guidelines

1. Keep steps atomic and actionable
2. Order steps logically (dependencies before dependents)
3. Choose appropriate execution hints
4. Consider error handling and fallback strategies
5. Estimate complexity accurately for delegation decisions