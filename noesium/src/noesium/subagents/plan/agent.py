"""PlanAgent implementation for creating domain-agnostic plans.

A general-purpose planning agent that generates detailed, actionable plans
with structured steps, resource requirements, dependencies, and verification criteria.
Applicable to diverse domains including software, research, workflows, and projects.
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Type

try:
    from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import END, START, StateGraph

    LANGCHAIN_AVAILABLE = True
except ImportError:
    AIMessage = None
    AnyMessage = None
    HumanMessage = None
    RunnableConfig = None
    StateGraph = None
    END = None
    START = None
    LANGCHAIN_AVAILABLE = False

from uuid_extensions import uuid7str

from noesium.core.agent import BaseGraphicAgent
from noesium.core.utils.logging import get_logger
from noesium.core.utils.typing import override
from noesium.toolkits import TOOLKIT_FILE_EDIT, TOOLKIT_USER_INTERACTION
from noesium.utils.tool_utils import ToolHelper, create_tool_helper

from .prompts import (
    CONTEXT_EVALUATION_PROMPT,
    PLAN_GENERATION_PROMPT,
    PLAN_SYSTEM_PROMPT,
    TASK_ANALYSIS_PROMPT,
)
from .schemas import ContextEvaluation, DetailedPlan
from .state import PlanState

logger = get_logger(__name__)


class PlanAgent(BaseGraphicAgent):
    """General-purpose planning agent for creating domain-agnostic plans.

    This agent:
    1. Evaluates context sufficiency (smart context detection)
    2. Explores resources if context is insufficient
    3. Analyzes requirements and constraints
    4. Generates detailed, structured plans
    5. Defines verification criteria for each step

    Supports plan types: implementation, research, workflow, project, general
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        max_planning_loops: int = 3,
        planning_temperature: float = 0.7,
        planning_max_tokens: int = 4000,
        agent_id: str | None = None,
        working_directory: str | None = None,
    ):
        """Initialize PlanAgent.

        Args:
            llm_provider: LLM provider to use
            max_planning_loops: Maximum planning refinement loops
            planning_temperature: Temperature for planning
            planning_max_tokens: Max tokens for planning
            agent_id: Optional agent ID (auto-generated if None)
            working_directory: Working directory for file operations
        """
        super().__init__(llm_provider=llm_provider)

        self.max_planning_loops = max_planning_loops
        self.planning_temperature = planning_temperature
        self.planning_max_tokens = planning_max_tokens

        # Generate agent ID
        self.agent_id = agent_id or f"plan-{uuid7str()[:8]}"

        # Tool configuration - read-only for planning
        self.enabled_toolkits = [TOOLKIT_FILE_EDIT, TOOLKIT_USER_INTERACTION]
        self.permissions = ["fs:read", "env:read"]  # Read-only!

        # ToolHelper will be initialized lazily
        self._tool_helper: ToolHelper | None = None
        self._working_directory = working_directory

        # Build the planning graph
        self.graph = self._build_graph()

    @override
    def get_state_class(self) -> Type:
        """Get the state class for this agent."""
        return PlanState

    async def _ensure_tool_helper(self) -> ToolHelper:
        """Lazily initialize tool helper."""
        if self._tool_helper is None:
            self._tool_helper = await create_tool_helper(
                agent_id=self.agent_id,
                enabled_toolkits=self.enabled_toolkits,
                permissions=self.permissions,
                working_directory=self._working_directory,
            )
        return self._tool_helper

    @override
    def _build_graph(self) -> StateGraph:
        """Build the planning workflow graph with unified context handling."""
        workflow = StateGraph(PlanState)

        # Add nodes
        workflow.add_node("evaluate_context", self._evaluate_context_node)
        workflow.add_node("explore_resources", self._explore_resources_node)
        workflow.add_node("analyze_requirements", self._analyze_requirements_node)
        workflow.add_node("generate_plan", self._generate_plan_node)
        workflow.add_node("define_verification", self._define_verification_node)
        workflow.add_node("finalize_plan", self._finalize_plan_node)

        # Set entry point
        workflow.add_edge(START, "evaluate_context")

        # Conditional edge: explore if context insufficient
        workflow.add_conditional_edges(
            "evaluate_context",
            self._should_explore,
            ["explore_resources", "analyze_requirements"],
        )

        # Continue after exploration
        workflow.add_edge("explore_resources", "analyze_requirements")
        workflow.add_edge("analyze_requirements", "generate_plan")
        workflow.add_edge("generate_plan", "define_verification")
        workflow.add_edge("define_verification", "finalize_plan")
        workflow.add_edge("finalize_plan", END)

        return workflow.compile()

    def _should_explore(self, state: PlanState) -> str:
        """Determine if context exploration is needed."""
        if state.get("context_sufficient", False):
            return "analyze_requirements"
        return "explore_resources"

    async def _evaluate_context_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Evaluate context sufficiency for planning."""
        objective = self._get_objective_from_messages(state["messages"])
        context = state.get("context", {})

        prompt = CONTEXT_EVALUATION_PROMPT.format(
            objective=objective,
            context=json.dumps(context, indent=2) if context else "No context provided",
        )

        try:
            # Use structured output for context evaluation
            result: ContextEvaluation = self.llm.structured_completion(
                messages=[
                    {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_model=ContextEvaluation,
                temperature=0.3,
                max_tokens=1000,
            )

            logger.info(f"Context evaluation: sufficient={result.is_sufficient}, type={result.detected_plan_type}")

            return {
                "context_sufficient": result.is_sufficient,
                "plan_type": result.detected_plan_type,
                "messages": [AIMessage(content=f"Context evaluation: {result.reasoning}")],
            }

        except Exception as e:
            logger.warning(f"Structured context evaluation failed, using fallback: {e}")
            # Fallback: assume context is insufficient if empty
            is_sufficient = bool(context)
            return {
                "context_sufficient": is_sufficient,
                "plan_type": "general",
                "messages": [AIMessage(content=f"Context evaluation fallback: sufficient={is_sufficient}")],
            }

    async def _explore_resources_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Explore resources to gather context."""
        objective = self._get_objective_from_messages(state["messages"])

        # Ensure tool helper is ready
        tool_helper = await self._ensure_tool_helper()

        # Get tool descriptions for LLM
        tool_desc = tool_helper.get_tool_descriptions()

        # Use LLM to identify which resources to explore
        exploration_prompt = f"""
You are planning: {objective}

Available tools:
{tool_desc}

Identify resources to explore for creating a comprehensive plan.
Return a JSON object with:
- files: list of file paths to read
- searches: list of search queries to run

Return ONLY the JSON object, no other text.
"""

        explored_resources = []
        file_contents = {}
        tool_results = []
        context = state.get("context", {})

        try:
            response = self.llm.completion(
                messages=[{"role": "user", "content": exploration_prompt}],
                temperature=0.3,
                max_tokens=500,
            )

            # Parse exploration plan
            try:
                exploration_plan = json.loads(response.strip())
            except json.JSONDecodeError:
                exploration_plan = {"files": [], "searches": []}

            # Read files
            for file_path in exploration_plan.get("files", [])[:5]:
                try:
                    # Sanitize file path: strip leading / to make it relative
                    if isinstance(file_path, str):
                        file_path = file_path.lstrip("/")
                    else:
                        logger.warning(f"Skipping non-string file path: {file_path}")
                        continue

                    if not file_path:
                        continue

                    result = await tool_helper.execute_tool(
                        "file_edit:read_file",
                        file_path=file_path,
                    )
                    explored_resources.append(file_path)
                    file_contents[file_path] = result
                    tool_results.append(
                        {
                            "tool": "read_file",
                            "file_path": file_path,
                            "success": True,
                            "size": len(result),
                        }
                    )
                    logger.info(f"Read file: {file_path} ({len(result)} bytes)")
                except Exception as e:
                    logger.warning(f"Failed to read file {file_path}: {e}")
                    tool_results.append(
                        {
                            "tool": "read_file",
                            "file_path": file_path,
                            "success": False,
                            "error": str(e),
                        }
                    )

            # Run searches
            for search_item in exploration_plan.get("searches", [])[:3]:
                try:
                    # Handle search pattern - could be string or dict
                    if isinstance(search_item, dict):
                        search_pattern = (
                            search_item.get("pattern")
                            or search_item.get("query")
                            or search_item.get("search")
                            or str(search_item)
                        )
                    elif isinstance(search_item, str):
                        search_pattern = search_item
                    else:
                        logger.warning(f"Skipping invalid search item: {search_item}")
                        continue

                    if not search_pattern or not isinstance(search_pattern, str):
                        continue

                    result = await tool_helper.execute_tool(
                        "file_edit:search_in_files",
                        pattern=search_pattern,
                        directory=".",
                    )
                    tool_results.append(
                        {
                            "tool": "search_in_files",
                            "query": search_pattern,
                            "success": True,
                            "matches": len(result.get("matches", [])) if isinstance(result, dict) else 0,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Search failed for '{search_item}': {e}")

        except Exception as e:
            logger.error(f"Error in explore_resources_node: {e}")

        # Update context with explored content
        context["explored_files"] = file_contents
        context["exploration_results"] = tool_results

        return {
            "explored_resources": explored_resources,
            "file_contents": file_contents,
            "tool_results": tool_results,
            "context": context,
            "context_sufficient": True,  # After exploration, proceed
        }

    async def _analyze_requirements_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Analyze requirements and constraints from the objective."""
        objective = self._get_objective_from_messages(state["messages"])
        context = state.get("context", {})

        prompt = TASK_ANALYSIS_PROMPT.format(
            objective=objective,
            context=json.dumps(context, indent=2) if context else "No additional context",
        )

        response = self.llm.completion(
            messages=[
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.planning_temperature,
            max_tokens=self.planning_max_tokens,
        )

        return {
            "messages": [AIMessage(content=response)],
        }

    async def _generate_plan_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Generate the detailed plan using structured output."""
        objective = self._get_objective_from_messages(state["messages"])
        context = state.get("context", {})
        plan_type = state.get("plan_type", "general")

        # Include explored content in context
        file_contents = state.get("file_contents", {})
        if file_contents:
            context["file_contents_summary"] = {
                k: v[:500] + "..." if len(v) > 500 else v for k, v in file_contents.items()
            }

        prompt = PLAN_GENERATION_PROMPT.format(
            objective=objective,
            context=json.dumps(context, indent=2) if context else "No additional context",
            plan_type=plan_type,
        )

        try:
            # Use structured output for plan generation
            result: DetailedPlan = self.llm.structured_completion(
                messages=[
                    {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_model=DetailedPlan,
                temperature=self.planning_temperature,
                max_tokens=self.planning_max_tokens,
            )

            # Convert to dict for state
            plan_steps = [step.model_dump() for step in result.plan_steps]
            dependencies = [dep.model_dump() for dep in result.dependencies]

            logger.info(f"Generated plan with {len(plan_steps)} steps")

            return {
                "plan_steps": plan_steps,
                "dependencies": dependencies,
                "messages": [AIMessage(content=f"Generated {result.plan_type} plan: {result.title}")],
            }

        except Exception as e:
            logger.warning(f"Structured plan generation failed, using fallback: {e}")
            # Fallback to text-based planning
            response = self.llm.completion(
                messages=[
                    {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.planning_temperature,
                max_tokens=self.planning_max_tokens,
            )

            plan_steps = self._parse_plan_steps(response)

            return {
                "plan_steps": plan_steps,
                "dependencies": [],
                "messages": [AIMessage(content=response)],
            }

    async def _define_verification_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Define verification criteria for plan steps."""
        plan_steps = state.get("plan_steps", [])

        # Extract verification steps from plan_steps (already included in structured output)
        verification_steps = []
        for step in plan_steps:
            if step.get("verification"):
                verification_steps.append(
                    {
                        "step_id": step.get("step_id"),
                        "verification": step.get("verification"),
                    }
                )

        return {
            "verification_steps": verification_steps,
        }

    async def _finalize_plan_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Finalize and format the plan."""
        plan_steps = state.get("plan_steps", [])
        plan_type = state.get("plan_type", "general")
        dependencies = state.get("dependencies", [])

        # Format plan as readable text
        plan_text = self._format_plan_text(plan_type, plan_steps, dependencies)

        return {
            "final_plan": plan_text,
            "messages": [AIMessage(content=plan_text)],
        }

    def _get_objective_from_messages(self, messages: List[AnyMessage]) -> str:
        """Extract objective from messages."""
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message.content
        return ""

    def _parse_plan_steps(self, plan_text: str) -> List[Dict[str, Any]]:
        """Parse plan text into structured steps (fallback)."""
        steps = []
        lines = plan_text.split("\n")

        current_step = None
        step_num = 0

        for line in lines:
            line = line.strip()
            if line and (line.startswith(f"{step_num + 1}.") or line.startswith(f"Step {step_num + 1}")):
                if current_step:
                    steps.append(current_step)
                step_num += 1
                current_step = {
                    "step_id": f"step-{step_num:03d}",
                    "description": line,
                    "action_type": "execute",
                    "target": None,
                    "details": [],
                    "dependencies": [],
                    "verification": None,
                    "estimated_effort": "medium",
                    "resources_required": [],
                }
            elif current_step and line:
                # Add to details
                if not current_step.get("details"):
                    current_step["details"] = []
                current_step["details"].append(
                    {
                        "aspect": "detail",
                        "action": line,
                        "content": None,
                        "rationale": "",
                    }
                )

        if current_step:
            steps.append(current_step)

        return steps

    def _format_plan_text(
        self,
        plan_type: str,
        plan_steps: List[Dict[str, Any]],
        dependencies: List[Dict[str, Any]],
    ) -> str:
        """Format plan as readable text."""
        lines = [
            f"# {plan_type.title()} Plan",
            "",
            f"## Steps ({len(plan_steps)} total)",
            "",
        ]

        for step in plan_steps:
            step_id = step.get("step_id", "")
            desc = step.get("description", "")
            action = step.get("action_type", "execute")
            target = step.get("target", "")
            effort = step.get("estimated_effort", "medium")

            lines.append(f"### {step_id}: {desc}")
            lines.append(f"- **Action**: {action}")
            if target:
                lines.append(f"- **Target**: {target}")
            lines.append(f"- **Effort**: {effort}")

            # Details
            details = step.get("details", [])
            if details:
                lines.append("- **Details**:")
                for detail in details:
                    lines.append(f"  - {detail.get('action', '')}")
                    if detail.get("rationale"):
                        lines.append(f"    *Rationale: {detail.get('rationale')}*")

            # Verification
            verification = step.get("verification")
            if verification:
                lines.append(f"- **Verification**: {verification.get('type', 'manual')}")
                if verification.get("method"):
                    lines.append(f"  - Method: {verification.get('method')}")
                if verification.get("expected_outcome"):
                    lines.append(f"  - Expected: {verification.get('expected_outcome')}")

            lines.append("")

        # Dependencies
        if dependencies:
            lines.append("## Dependencies")
            lines.append("")
            for dep in dependencies:
                lines.append(f"- {dep.get('from_step')} depends on {dep.get('to_step')}: {dep.get('reason', '')}")

        return "\n".join(lines)

    @override
    async def run(
        self,
        user_message: str,
        context: Dict[str, Any] = None,
        config: Optional[RunnableConfig] = None,
    ) -> str:
        """Run the planning agent and return the plan.

        Args:
            user_message: The objective to plan for
            context: Additional context (unified handling)
            config: Runtime configuration

        Returns:
            The plan as formatted text
        """
        initial_state: PlanState = {
            "messages": [HumanMessage(content=user_message)],
            "context": context or {},
            "context_sufficient": False,
            "explored_resources": [],
            "requirements": [],
            "constraints": [],
            "plan_type": "general",
            "plan_steps": [],
            "dependencies": [],
            "verification_steps": [],
            "tool_results": [],
            "file_contents": {},
            "clarification_questions": [],
            "final_plan": None,
        }

        result = await self.graph.ainvoke(initial_state, config=config)

        return result.get("final_plan", "Planning failed")

    async def astream_progress(
        self,
        user_message: str,
        context: Dict[str, Any] = None,
        config: Optional[RunnableConfig] = None,
    ) -> AsyncGenerator[Any, None]:
        """Stream progress events during planning.

        Args:
            user_message: The objective to plan for
            context: Additional context
            config: Runtime configuration

        Yields:
            ProgressEvent: Events describing planning progress
        """
        from noesium.core.event import ProgressEvent, ProgressEventType

        session_id = uuid7str()

        # Yield SESSION_START
        yield ProgressEvent(
            type=ProgressEventType.SESSION_START,
            session_id=session_id,
            summary=f"Planning: {user_message[:60]}",
        )

        # Initialize state
        initial_state: PlanState = {
            "messages": [HumanMessage(content=user_message)],
            "context": context or {},
            "context_sufficient": False,
            "explored_resources": [],
            "requirements": [],
            "constraints": [],
            "plan_type": "general",
            "plan_steps": [],
            "dependencies": [],
            "verification_steps": [],
            "tool_results": [],
            "file_contents": {},
            "clarification_questions": [],
            "final_plan": None,
        }

        try:
            yield ProgressEvent(
                type=ProgressEventType.THINKING,
                session_id=session_id,
                summary="Evaluating context...",
            )

            async for event in self.graph.astream(initial_state):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    if node_name == "evaluate_context":
                        plan_type = node_output.get("plan_type", "general")
                        sufficient = node_output.get("context_sufficient", False)
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary=f"Context evaluation: {plan_type} plan, sufficient={sufficient}",
                        )

                    elif node_name == "explore_resources":
                        tool_results = node_output.get("tool_results", [])
                        for tool_result in tool_results:
                            tool_name = tool_result.get("tool", "unknown")
                            success = tool_result.get("success", False)

                            # Build specific target name for progress message
                            if tool_name == "read_file":
                                target = tool_result.get("file_path", "unknown file")
                            elif tool_name == "search_in_files":
                                target = f"pattern '{tool_result.get('query', 'unknown')}'"
                            else:
                                target = tool_result.get("file_path", tool_result.get("query", "unknown target"))

                            yield ProgressEvent(
                                type=ProgressEventType.TOOL_START,
                                session_id=session_id,
                                tool_name=tool_name,
                                summary=f"Exploring: {target}",
                            )

                            if success:
                                # Build detailed success message
                                if tool_name == "read_file":
                                    size = tool_result.get("size", 0)
                                    detail = f"{size} bytes" if size else "content loaded"
                                elif tool_name == "search_in_files":
                                    matches = tool_result.get("matches", 0)
                                    detail = f"{matches} matches" if matches else "search complete"
                                else:
                                    detail = "Success"

                                yield ProgressEvent(
                                    type=ProgressEventType.TOOL_END,
                                    session_id=session_id,
                                    tool_name=tool_name,
                                    tool_result=detail,
                                    summary=f"Explored {target}: {detail}",
                                )
                            else:
                                error_msg = tool_result.get("error", "unknown error")
                                yield ProgressEvent(
                                    type=ProgressEventType.TOOL_END,
                                    session_id=session_id,
                                    tool_name=tool_name,
                                    tool_result=f"Failed: {error_msg}",
                                    summary=f"Failed to explore {target}: {error_msg[:50]}",
                                )

                    elif node_name == "analyze_requirements":
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary="Analyzing requirements...",
                        )

                    elif node_name == "generate_plan":
                        plan_steps = node_output.get("plan_steps", [])
                        yield ProgressEvent(
                            type=ProgressEventType.PLAN_CREATED,
                            session_id=session_id,
                            summary=f"Generated plan with {len(plan_steps)} steps",
                            plan_snapshot={
                                "steps": [
                                    {"description": step.get("description", ""), "status": "pending"}
                                    for step in plan_steps
                                ],
                                "goal": user_message,
                            },
                        )

                    elif node_name == "finalize_plan":
                        final_plan = node_output.get("final_plan", "")
                        yield ProgressEvent(
                            type=ProgressEventType.FINAL_ANSWER,
                            session_id=session_id,
                            text=final_plan,
                            summary="Planning complete",
                        )

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            yield ProgressEvent(
                type=ProgressEventType.ERROR,
                session_id=session_id,
                error=str(e),
                summary=f"Planning failed: {str(e)[:60]}",
            )
            raise

        finally:
            yield ProgressEvent(
                type=ProgressEventType.SESSION_END,
                session_id=session_id,
            )
