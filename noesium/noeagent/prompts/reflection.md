---
name: reflection
version: "1.0.0"
created: "2026-03-04"
author: "NoeAgent Team"
description: "Progress assessment prompt for plan evaluation"
required_variables:
  - goal
  - plan_steps
  - completed_results
template_engine: format
---

# Progress Reflection

Reflect on the progress so far.

## Goal

{goal}

## Plan Steps

{plan_steps}

## Completed Results

{completed_results}

## Assessment Framework

Evaluate the following:

### 1. Accomplishments
- What has been successfully completed?
- Which plan steps are done?
- What valuable results have been gathered?

### 2. Remaining Work
- What tasks are still pending?
- Are there blocked or failed steps?
- What needs additional effort?

### 3. Plan Revision Decision
Consider revising the plan if:
- Unexpected obstacles emerged
- New information changes the approach
- Steps are no longer relevant or feasible
- Better strategies become apparent

## Revision Trigger

If you determine the plan should be revised, start your response with:

**REVISE:**

Followed by your reasoning for the revision.

## Otherwise

Provide a concise assessment of progress and readiness to continue with the current plan.