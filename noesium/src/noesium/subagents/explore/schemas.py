"""Structured output schemas for ExploreAgent.

Pydantic models for structured exploration outputs.
These models enable LLM structured completion for reliable exploration results.
"""

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class Finding(BaseModel):
    """A single finding from exploration."""

    finding_id: str = Field(..., description="Unique finding identifier")
    title: str = Field(..., description="Brief title of the finding")
    description: str = Field(..., description="Detailed description")
    source: str = Field(..., description="Where this finding came from")
    relevance: Literal["high", "medium", "low"] = "medium"
    finding_type: Literal["fact", "pattern", "insight", "reference"] = "fact"
    details: Dict[str, Any] = Field(default_factory=dict)


class Source(BaseModel):
    """A source accessed during exploration."""

    source_id: str = Field(..., description="Unique source identifier")
    type: Literal["file", "document", "data", "media", "url"]
    name: str = Field(..., description="Source name or title")
    location: str = Field(..., description="Path or URL")
    summary: str = Field(..., description="Brief summary of content")
    accessed_at: str = Field(..., description="ISO timestamp")


class ReflectionResult(BaseModel):
    """Result of reflection on exploration progress."""

    is_sufficient: bool = Field(..., description="Whether gathered info is sufficient")
    knowledge_gaps: List[str] = Field(default_factory=list, description="What information is still missing")
    follow_up_queries: List[str] = Field(default_factory=list, description="Queries to fill knowledge gaps")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in findings (0-1)")
    reasoning: str = Field(..., description="Explanation of assessment")


class ExploreResult(BaseModel):
    """Complete exploration result."""

    target: str = Field(..., description="Original exploration target")
    summary: str = Field(..., description="Synthesized summary of findings")
    findings: List[Finding] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    exploration_depth: int = Field(0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchQuery(BaseModel):
    """A search query in the exploration strategy."""

    query_id: str = Field(..., description="Unique query identifier")
    query: str = Field(..., description="The search query")
    query_type: Literal["file_search", "content_search", "pattern_match", "analysis"] = "content_search"
    priority: Literal["high", "medium", "low"] = "medium"
    expected_findings: str = Field(default="", description="What we expect to find")


class TargetAnalysis(BaseModel):
    """Analysis of the exploration target."""

    target_type: Literal["code", "document", "data", "media", "general"]
    information_sought: str = Field(..., description="What information is being sought")
    recommended_tools: List[str] = Field(default_factory=list, description="Tools to use")
    priority_sources: List[str] = Field(default_factory=list, description="Sources to prioritize")
    exploration_depth: int = Field(default=2, ge=1, le=5, description="Recommended depth")
    reasoning: str = Field(..., description="Explanation of analysis")


class SearchStrategy(BaseModel):
    """Complete search strategy for exploration."""

    queries: List[SearchQuery] = Field(default_factory=list)
    parallel_paths: List[List[str]] = Field(default_factory=list, description="Query IDs that can run in parallel")
    estimated_sources: int = Field(default=0, description="Estimated number of sources")
