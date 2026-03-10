"""General-purpose prompts for PlanAgent.

Domain-agnostic prompts for planning across software, research, workflows, and projects.
"""

PLAN_SYSTEM_PROMPT = """You are an expert planning agent capable of creating detailed, actionable plans for any domain.

Your responsibilities:
1. Analyze objectives and requirements
2. Break down complex tasks into clear, ordered steps
3. Identify dependencies between steps
4. Define verification criteria for each step
5. Provide specific, actionable guidance

You work across domains including:
- Software implementation (code, systems, infrastructure)
- Research and analysis (literature review, data analysis, feasibility)
- Business workflows (processes, pipelines, operations)
- Projects (multi-phase initiatives, launches, migrations)
- General tasks (content creation, documentation, organization)

Guidelines:
- Assess provided context before planning
- Request clarification if requirements are ambiguous
- Break tasks into specific, verifiable steps
- Include rationale for each step
- Identify dependencies and prerequisites
- Estimate effort for each step
- Define clear success criteria

You have access to:
- File and document reading tools (read_file, list_files, search_in_files)
- User interaction tools (ask_question)

You do NOT have write access - you only create plans, not implementations.
"""

CONTEXT_EVALUATION_PROMPT = """Evaluate the provided context for the following objective.

Objective: {objective}

Provided Context:
{context}

Determine:
1. Is the context sufficient to create a detailed plan?
2. What information gaps exist?
3. What resources should be explored to fill gaps?
4. What is the likely plan type (implementation, research, workflow, project)?

Respond with a JSON object containing:
- is_sufficient: boolean
- information_gaps: list of strings
- resources_to_explore: list of strings
- detected_plan_type: one of "implementation", "research", "workflow", "project", "general"
- reasoning: string explaining your assessment
"""

TASK_ANALYSIS_PROMPT = """Analyze the following objective and identify requirements and constraints.

Objective: {objective}

Context: {context}

Identify:
1. Core requirements - what must be achieved
2. Constraints - limitations on time, resources, dependencies
3. Implicit assumptions that should be validated
4. Potential risks or blockers

For each requirement, specify:
- Description of what needs to be achieved
- Priority (critical, high, medium, low)
- Category (functional, technical, quality, etc.)

For each constraint, specify:
- Description of the limitation
- Type (time, resource, dependency, compatibility)
- Impact (blocking, significant, minor)
"""

PLAN_GENERATION_PROMPT = """Create a detailed, actionable plan for the following objective.

Objective: {objective}

Context: {context}

Plan Type: {plan_type}

Requirements:
1. Break down into clear, numbered steps
2. For each step provide:
   - step_id: unique identifier (e.g., "step-001")
   - description: what this step accomplishes
   - action_type: one of (create, modify, analyze, execute, research, review, deploy)
   - target: file, resource, or entity to act upon (if applicable)
   - details: list of specific actions with aspect, action, content, rationale
   - dependencies: list of step_ids this depends on
   - verification: type, criteria, method, expected_outcome
   - estimated_effort: low, medium, or high
   - resources_required: list of resources needed
3. Identify overall dependencies and prerequisites
4. Note potential risks or blockers

Format as a structured plan with clear, actionable steps.
"""

CLARIFICATION_PROMPT = """Based on your analysis, identify any ambiguities or questions that need clarification.

Objective: {objective}

Context gathered: {context}

Current understanding: {current_understanding}

List specific questions that would help you create a better plan.
For each question:
1. State the question clearly
2. Explain why this clarification is needed
3. Optionally suggest possible answers

Only ask questions that are critical for creating an accurate plan.
Limit to 3 most important questions.
"""

PLAN_REFINEMENT_PROMPT = """Refine the plan based on additional information or feedback.

Original Plan:
{original_plan}

New Information/Feedback:
{feedback}

Update the plan to:
1. Address any issues raised
2. Incorporate new information
3. Maintain clarity and completeness
4. Preserve the structured format
"""

DEPENDENCY_ANALYSIS_PROMPT = """Analyze the dependencies between plan steps.

Plan Steps:
{plan_steps}

For each dependency:
1. Identify which step depends on which
2. Explain why the dependency exists
3. Determine if the dependency is:
   - Hard (must complete before starting)
   - Soft (preferred but not required)

Also identify:
- Steps that can be parallelized
- Critical path (longest chain of dependencies)
- Potential bottlenecks
"""

VERIFICATION_DEFINITION_PROMPT = """Define verification criteria for each plan step.

Plan Steps:
{plan_steps}

For each step, define:
1. Verification type (test, review, validation, manual, automated, milestone)
2. Success criteria (specific, measurable conditions)
3. Verification method (how to check)
4. Expected outcome (what success looks like)

Consider:
- Automated checks where possible
- Clear pass/fail criteria
- Milestone checkpoints for complex plans
"""
