"""Schema definitions for PlanAgent."""

from datetime import datetime

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """A single step in the implementation plan.

    Attributes:
        step_number: Step sequence number
        description: What this step does
        rationale: Why this step is needed
        files_to_read: Files that should be read for this step
        estimated_complexity: Complexity estimate (low, medium, high)
        dependencies: Step numbers this depends on
    """

    step_number: int = Field(..., description="Step sequence number")
    description: str = Field(..., description="What this step does")
    rationale: str = Field(..., description="Why this step is needed")
    files_to_read: list[str] = Field(default_factory=list, description="Files to read for this step")
    estimated_complexity: str = Field(default="medium", description="Complexity: low, medium, high")
    dependencies: list[int] = Field(default_factory=list, description="Step numbers this depends on")


class ClarificationQuestion(BaseModel):
    """A question for user clarification.

    Attributes:
        question: The question text
        reason: Why this clarification is needed
        suggested_answers: Optional suggested answers
    """

    question: str = Field(..., description="The question text")
    reason: str = Field(..., description="Why this clarification is needed")
    suggested_answers: list[str] = Field(default_factory=list, description="Optional suggested answers")


class PlanResult(BaseModel):
    """Result from the planning agent.

    Attributes:
        plan_steps: List of plan steps
        clarification_questions: Questions for user
        files_analyzed: Files that were analyzed
        final_plan: The complete plan text
        timestamp: When the plan was created
    """

    plan_steps: list[PlanStep] = Field(default_factory=list, description="Plan steps")
    clarification_questions: list[ClarificationQuestion] = Field(
        default_factory=list, description="Clarification questions"
    )
    files_analyzed: list[str] = Field(default_factory=list, description="Files that were analyzed")
    final_plan: str = Field(..., description="The complete plan text")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp")
