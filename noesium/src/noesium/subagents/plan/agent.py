"""PlanAgent implementation for creating implementation plans."""

import json
import re
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
    CLARIFICATION_PROMPT,
    PLAN_GENERATION_PROMPT,
    PLAN_SYSTEM_PROMPT,
    TASK_ANALYSIS_PROMPT,
)
from .state import PlanState

logger = get_logger(__name__)


class PlanAgent(BaseGraphicAgent):
    """Planning agent for creating implementation plans.

    This agent:
    1. Analyzes tasks and requirements
    2. Reads relevant files to understand codebase
    3. Breaks down complex tasks into actionable steps
    4. Asks clarifying questions when needed
    5. Creates comprehensive implementation plans
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
        """Build the planning workflow graph."""
        workflow = StateGraph(PlanState)

        # Add nodes
        workflow.add_node("analyze_task", self._analyze_task_node)
        workflow.add_node("read_context", self._read_context_node)
        workflow.add_node("generate_plan", self._generate_plan_node)
        workflow.add_node("validate_plan", self._validate_plan_node)
        workflow.add_node("finalize_plan", self._finalize_plan_node)

        # Set entry point
        workflow.add_edge(START, "analyze_task")

        # Add edges
        workflow.add_edge("analyze_task", "read_context")
        workflow.add_edge("read_context", "generate_plan")
        workflow.add_edge("generate_plan", "validate_plan")
        workflow.add_conditional_edges(
            "validate_plan",
            self._should_finalize,
            ["finalize_plan", "read_context"],
        )
        workflow.add_edge("finalize_plan", END)

        return workflow.compile()

    async def _analyze_task_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Analyze the task and identify what needs to be understood."""
        task = self._get_task_from_messages(state["messages"])

        prompt = TASK_ANALYSIS_PROMPT.format(
            task=task,
            context=state.get("context", {}),
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

    async def _read_context_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Read relevant files using actual tools."""
        task = self._get_task_from_messages(state["messages"])

        # Ensure tool helper is ready
        tool_helper = await self._ensure_tool_helper()

        # Get tool descriptions for LLM
        tool_desc = tool_helper.get_tool_descriptions()

        # Use LLM to identify which files to read
        file_identification_prompt = f"""
You are planning: {task}

Available tools:
{tool_desc}

Identify which files should be read to create a comprehensive plan.
Return a JSON list of file paths to read, e.g.: ["file1.py", "src/module.py"]

Return ONLY the JSON list, no other text.
"""

        files_read = []
        file_contents = {}
        tool_results = []

        try:
            # Get file list from LLM
            response = self.llm.completion(
                messages=[{"role": "user", "content": file_identification_prompt}],
                temperature=0.3,
                max_tokens=500,
            )

            # Parse file paths
            try:
                file_paths = json.loads(response.strip())
            except json.JSONDecodeError:
                # Fallback: try to extract paths from text
                file_paths = re.findall(r'["\']([^"\']+\.py)["\']', response)

            # Read each file using actual tools
            for file_path in file_paths[:5]:  # Limit to 5 files
                try:
                    result = await tool_helper.execute_tool(
                        "file_edit:read_file",
                        file_path=file_path,
                    )

                    files_read.append(file_path)
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

        except Exception as e:
            logger.error(f"Error in read_context_node: {e}")

        return {
            "files_read": files_read,
            "file_contents": file_contents,
            "tool_results": tool_results,
        }

    async def _generate_plan_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Generate the implementation plan."""
        task = self._get_task_from_messages(state["messages"])
        files_analyzed = state.get("files_read", [])

        # Extract key findings from messages
        key_findings = self._extract_key_findings(state["messages"])

        prompt = PLAN_GENERATION_PROMPT.format(
            task=task,
            files_analyzed=files_analyzed,
            key_findings=key_findings,
        )

        response = self.llm.completion(
            messages=[
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.planning_temperature,
            max_tokens=self.planning_max_tokens,
        )

        # Parse the plan into structured steps
        plan_steps = self._parse_plan_steps(response)

        return {
            "messages": [AIMessage(content=response)],
            "plan_steps": plan_steps,
        }

    async def _validate_plan_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Validate the plan and check if clarification is needed."""
        task = self._get_task_from_messages(state["messages"])
        files_read = state.get("files_read", [])

        # Extract current understanding from messages
        current_understanding = self._extract_current_understanding(state["messages"])

        prompt = CLARIFICATION_PROMPT.format(
            task=task,
            files_read=files_read,
            current_understanding=current_understanding,
        )

        response = self.llm.completion(
            messages=[
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.planning_temperature,
            max_tokens=self.planning_max_tokens,
        )

        # Parse clarification questions
        clarification_questions = self._parse_clarification_questions(response)

        return {
            "messages": [AIMessage(content=response)],
            "clarification_questions": clarification_questions,
        }

    async def _finalize_plan_node(self, state: PlanState, config: RunnableConfig) -> Dict[str, Any]:
        """Finalize the plan."""
        # Extract the final plan from messages
        final_plan = self._extract_final_plan(state["messages"])

        return {
            "final_plan": final_plan,
            "messages": [AIMessage(content=final_plan)],
        }

    def _should_finalize(self, state: PlanState) -> str:
        """Determine if planning should finalize or continue."""
        clarification_questions = state.get("clarification_questions", [])
        current_step = state.get("current_step_index", 0)

        # If no clarification needed or max loops reached, finalize
        if not clarification_questions or current_step >= self.max_planning_loops:
            return "finalize_plan"

        # Otherwise, continue gathering context
        return "read_context"

    def _get_task_from_messages(self, messages: List[AnyMessage]) -> str:
        """Extract task from messages."""
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message.content
        return ""

    def _extract_key_findings(self, messages: List[AnyMessage]) -> str:
        """Extract key findings from messages."""
        findings = []
        for message in messages:
            if isinstance(message, AIMessage):
                findings.append(message.content)
        return "\n\n".join(findings[-2:]) if findings else "No findings yet"

    def _extract_current_understanding(self, messages: List[AnyMessage]) -> str:
        """Extract current understanding from messages."""
        understandings = []
        for message in messages[-3:]:
            if isinstance(message, AIMessage):
                understandings.append(message.content)
        return "\n\n".join(understandings) if understandings else "Initial analysis"

    def _parse_plan_steps(self, plan_text: str) -> List[Dict[str, Any]]:
        """Parse plan text into structured steps."""
        # Simple parsing - in production, would use structured output
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
                    "step_number": step_num,
                    "description": line,
                    "rationale": "",
                    "files_to_read": [],
                    "estimated_complexity": "medium",
                    "dependencies": [],
                }
            elif current_step and line:
                # Add to rationale
                current_step["rationale"] += " " + line

        if current_step:
            steps.append(current_step)

        return steps

    def _parse_clarification_questions(self, text: str) -> List[str]:
        """Parse clarification questions from text."""
        questions = []
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if line and ("?" in line or line.startswith("Q:") or line.startswith("Question:")):
                questions.append(line)

        return questions[:3]  # Limit to 3 questions

    def _extract_final_plan(self, messages: List[AnyMessage]) -> str:
        """Extract final plan from messages."""
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return message.content
        return "Plan creation failed"

    @override
    async def run(
        self,
        user_message: str,
        context: Dict[str, Any] = None,
        config: Optional[RunnableConfig] = None,
    ) -> str:
        """Run the planning agent and return the plan.

        Args:
            user_message: The task to plan
            context: Additional context
            config: Runtime configuration

        Returns:
            The implementation plan as text
        """
        initial_state: PlanState = {
            "messages": [HumanMessage(content=user_message)],
            "context": context or {},
            "files_read": [],
            "file_contents": {},
            "tool_results": [],
            "plan_steps": [],
            "current_step_index": 0,
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
            user_message: The task to plan
            context: Additional context
            config: Runtime configuration

        Yields:
            ProgressEvent: Events describing planning progress
        """
        from uuid_extensions import uuid7str

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
            "files_read": [],
            "file_contents": {},
            "tool_results": [],
            "plan_steps": [],
            "current_step_index": 0,
            "clarification_questions": [],
            "final_plan": None,
        }

        try:
            # Yield thinking event
            yield ProgressEvent(
                type=ProgressEventType.THINKING,
                session_id=session_id,
                summary="Analyzing task requirements...",
            )

            # Stream graph execution
            async for event in self.graph.astream(initial_state):
                for node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue

                    # Handle different nodes
                    if node_name == "analyze_task":
                        yield ProgressEvent(
                            type=ProgressEventType.THINKING,
                            session_id=session_id,
                            summary="Analyzing task structure...",
                        )

                    elif node_name == "read_context":
                        tool_results = node_output.get("tool_results", [])
                        node_output.get("files_read", [])

                        # Emit tool events based on actual tool execution
                        for tool_result in tool_results:
                            tool_name = tool_result.get("tool", "unknown")
                            file_path = tool_result.get("file_path", "")
                            success = tool_result.get("success", False)

                            # Emit TOOL_START
                            yield ProgressEvent(
                                type=ProgressEventType.TOOL_START,
                                session_id=session_id,
                                tool_name=tool_name,
                                summary=f"Reading {file_path}...",
                            )

                            # Emit TOOL_END
                            if success:
                                size = tool_result.get("size", 0)
                                yield ProgressEvent(
                                    type=ProgressEventType.TOOL_END,
                                    session_id=session_id,
                                    tool_name=tool_name,
                                    tool_result=f"Successfully read {file_path} ({size} bytes)",
                                    summary=f"Read {file_path}",
                                )
                            else:
                                error = tool_result.get("error", "Unknown error")
                                yield ProgressEvent(
                                    type=ProgressEventType.TOOL_END,
                                    session_id=session_id,
                                    tool_name=tool_name,
                                    tool_result=f"Failed to read {file_path}: {error}",
                                    summary=f"Failed to read {file_path}",
                                )

                    elif node_name == "generate_plan":
                        plan_steps = node_output.get("plan_steps", [])
                        yield ProgressEvent(
                            type=ProgressEventType.PLAN_CREATED,
                            session_id=session_id,
                            summary=f"Generated plan with {len(plan_steps)} steps",
                            plan_snapshot={
                                "steps": [
                                    {
                                        "description": step.get("description", ""),
                                        "status": "pending",
                                    }
                                    for step in plan_steps
                                ],
                                "goal": user_message,
                            },
                        )

                    elif node_name == "validate_plan":
                        questions = node_output.get("clarification_questions", [])
                        if questions:
                            yield ProgressEvent(
                                type=ProgressEventType.THINKING,
                                session_id=session_id,
                                summary=f"Identified {len(questions)} clarification questions",
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
            # Yield SESSION_END
            yield ProgressEvent(
                type=ProgressEventType.SESSION_END,
                session_id=session_id,
            )
