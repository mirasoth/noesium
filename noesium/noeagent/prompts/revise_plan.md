---
name: revise_plan
version: "1.1.0"
created: "2026-03-04"
modified: "2026-03-04"
author: "NoeAgent Team"
description: "Plan revision prompt based on feedback and results"
required_variables:
  - goal
  - original_steps
  - feedback
  - completed_results
template_engine: format
---

# Plan Revision

Revise the plan based on the following feedback and completed results.

## Original Goal

{goal}

## Original Plan Steps

{original_steps}

## Feedback

{feedback}

## Completed Results

{completed_results}

## Revision Guidelines

Consider:
- What worked well in the original plan?
- What obstacles or failures occurred?
- What new information emerged?
- What changes will improve success probability?

## Output Format

Return a revised JSON object with a "steps" array where each element has:
- **description**: string describing the step
- **execution_hint**: one of "tool", "subagent", "external_subagent", "builtin_agent", or "auto"

## Execution Modes (Default Built-in Only)

- **tool**: Atomic operations using default toolkits (bash, file_edit, document, image, python_executor, tabular_data, wizsearch, user_interaction).
- **subagent**: Multi-step reasoning with in-process child agent.
- **external_subagent**: External CLI agent (e.g., Claude Code), when configured.
- **builtin_agent**: Default built-in subagents only — **browser_use** (web automation, forms, real-time data) or **tacitus** (research, synthesis, multi-source).
- **auto**: Let the agent decide.

## Revision Principles

1. Preserve successful completed steps.
2. Remove redundant or unnecessary steps.
3. Add steps to address new requirements.
4. Adjust execution hints based on learnings; use only default built-in tools and subagents.
5. Maintain logical ordering and dependencies.
6. Keep the goal achievable with available resources.