"""Schema definitions for ExploreAgent."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExplorationFinding(BaseModel):
    """A single finding from exploration.

    Attributes:
        title: Title of the finding
        description: Description of what was found
        source: Where this was found (file, command output, etc.)
        relevance: How relevant this is to the target
        details: Additional details
    """

    title: str = Field(..., description="Title of the finding")
    description: str = Field(..., description="Description of what was found")
    source: str = Field(..., description="Where this was found")
    relevance: str = Field(default="high", description="Relevance: high, medium, low")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")


class ExplorationSource(BaseModel):
    """A source found during exploration.

    Attributes:
        type: Type of source (file, code, documentation, data)
        name: Name or path of the source
        location: Location or path
        summary: Brief summary of what's in this source
    """

    type: str = Field(..., description="Type: file, code, documentation, data")
    name: str = Field(..., description="Name or path")
    location: str = Field(..., description="Location or path")
    summary: str = Field(default="", description="Brief summary")


class ExplorationResult(BaseModel):
    """Result from exploration agent.

    Attributes:
        target: What was explored
        findings: List of findings
        sources: List of sources found
        summary: Summary of exploration
        timestamp: When exploration was performed
    """

    target: str = Field(..., description="What was explored")
    findings: list[ExplorationFinding] = Field(default_factory=list, description="Findings")
    sources: list[ExplorationSource] = Field(default_factory=list, description="Sources found")
    summary: str = Field(..., description="Summary of exploration")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp")