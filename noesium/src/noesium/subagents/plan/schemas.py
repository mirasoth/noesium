"""Structured output schemas for PlanAgent.

Pydantic models for structured plan generation outputs.
These models enable LLM structured completion for reliable plan generation.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ActionDetail(BaseModel):
    """Details about a specific action within a plan step."""

    aspect: str = Field(..., description="What aspect is being addressed")
    action: str = Field(..., description="Specific action to take")
    content: Optional[str] = Field(None, description="Suggested content or approach")
    rationale: str = Field(..., description="Why this action is needed")


class VerificationStep(BaseModel):
    """Verification criteria for a plan step."""

    type: Literal["test", "review", "validation", "manual", "automated", "milestone"]
    criteria: List[str] = Field(default_factory=list, description="Success criteria")
    method: Optional[str] = Field(None, description="How to verify")
    expected_outcome: str = Field(..., description="What success looks like")


class PlanStep(BaseModel):
    """A single step in a plan."""

    step_id: str = Field(..., description="Unique step identifier")
    description: str = Field(..., description="What this step accomplishes")
    action_type: Literal["create", "modify", "analyze", "execute", "research", "review", "deploy"]
    target: Optional[str] = Field(None, description="File, resource, or entity to act upon")
    details: Optional[List[ActionDetail]] = Field(None, description="Detailed actions")
    dependencies: List[str] = Field(default_factory=list, description="Step IDs this depends on")
    verification: Optional[VerificationStep] = Field(None, description="How to verify this step")
    estimated_effort: Literal["low", "medium", "high"] = "medium"
    resources_required: List[str] = Field(default_factory=list)


class Dependency(BaseModel):
    """Dependency relationship between steps."""

    from_step: str = Field(..., description="Dependent step ID")
    to_step: str = Field(..., description="Required step ID")
    reason: str = Field(..., description="Why this dependency exists")


class DetailedPlan(BaseModel):
    """Complete structured plan output."""

    plan_type: Literal["implementation", "research", "workflow", "project", "general"]
    title: str = Field(..., description="Plan title")
    summary: str = Field(..., description="Brief summary of the plan")
    plan_steps: List[PlanStep] = Field(default_factory=list)
    dependencies: List[Dependency] = Field(default_factory=list)
    estimated_total_effort: Literal["low", "medium", "high"] = "medium"
    prerequisites: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextEvaluation(BaseModel):
    """Result of context evaluation for planning."""

    is_sufficient: bool = Field(..., description="Whether context is sufficient for planning")
    information_gaps: List[str] = Field(default_factory=list, description="What information is missing")
    resources_to_explore: List[str] = Field(default_factory=list, description="Resources to explore to fill gaps")
    detected_plan_type: Literal["implementation", "research", "workflow", "project", "general"] = "general"
    reasoning: str = Field(..., description="Explanation of the assessment")


class Requirement(BaseModel):
    """A structured requirement extracted from the objective."""

    requirement_id: str = Field(..., description="Unique requirement identifier")
    description: str = Field(..., description="What needs to be achieved")
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    category: str = Field(default="general", description="Category of requirement")


class Constraint(BaseModel):
    """A constraint that limits the plan."""

    constraint_id: str = Field(..., description="Unique constraint identifier")
    description: str = Field(..., description="What the constraint is")
    type: Literal["time", "resource", "dependency", "compatibility", "other"] = "other"
    impact: Literal["blocking", "significant", "minor"] = "significant"
