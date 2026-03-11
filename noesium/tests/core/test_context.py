"""Unit tests for CognitiveContext (RFC-1009)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from noesium.core.context import CognitiveContext


@pytest.fixture
def mock_memory_manager():
    """Create a mock memory manager for testing."""
    manager = MagicMock()
    manager.store = AsyncMock()
    manager.read = AsyncMock(return_value=None)
    manager.recall = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def test_session_id():
    """Provide a test session ID."""
    return "test-session-123"


class TestCognitiveContextBasics:
    """Test basic CognitiveContext operations."""

    def test_initial_state(self, mock_memory_manager, test_session_id) -> None:
        """Test initial context state is empty."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        assert ctx.goal == ""
        assert ctx.findings == []
        assert ctx.scratchpad == {}
        assert ctx.max_findings == 8

    def test_set_goal(self, mock_memory_manager, test_session_id) -> None:
        """Test setting a goal."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Find the user's preferences")
        assert ctx.goal == "Find the user's preferences"

    def test_add_finding(self, mock_memory_manager, test_session_id) -> None:
        """Test adding findings."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.add_finding("User prefers dark mode")
        ctx.add_finding("User is in timezone UTC+8")
        assert len(ctx.findings) == 2
        assert "User prefers dark mode" in ctx.findings
        assert "User is in timezone UTC+8" in ctx.findings

    def test_add_finding_auto_trim(self, mock_memory_manager, test_session_id) -> None:
        """Test findings are auto-trimmed to max_findings (FIFO)."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id, max_findings=3)
        ctx.add_finding("finding1")
        ctx.add_finding("finding2")
        ctx.add_finding("finding3")
        ctx.add_finding("finding4")
        ctx.add_finding("finding5")

        assert len(ctx.findings) == 3
        # Oldest findings should be removed
        assert "finding1" not in ctx.findings
        assert "finding2" not in ctx.findings
        # Newest findings should remain
        assert ctx.findings == ["finding3", "finding4", "finding5"]


class TestScratchpad:
    """Test scratchpad operations."""

    def test_set_and_get_scratchpad(self, mock_memory_manager, test_session_id) -> None:
        """Test setting and getting scratchpad values."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_scratchpad("current_plan", {"step": 1, "action": "search"})
        ctx.set_scratchpad("retry_count", 3)

        assert ctx.get_scratchpad("current_plan") == {"step": 1, "action": "search"}
        assert ctx.get_scratchpad("retry_count") == 3

    def test_get_scratchpad_default(self, mock_memory_manager, test_session_id) -> None:
        """Test getting scratchpad with default value."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        assert ctx.get_scratchpad("nonexistent") is None
        assert ctx.get_scratchpad("nonexistent", "default_value") == "default_value"

    def test_scratchpad_overwrite(self, mock_memory_manager, test_session_id) -> None:
        """Test overwriting scratchpad values."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_scratchpad("key", "value1")
        ctx.set_scratchpad("key", "value2")
        assert ctx.get_scratchpad("key") == "value2"


class TestExport:
    """Test export functionality."""

    def test_export_empty(self, mock_memory_manager, test_session_id) -> None:
        """Test exporting empty context."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        assert ctx.export() == ""

    def test_export_goal_only(self, mock_memory_manager, test_session_id) -> None:
        """Test exporting with goal only."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Analyze the code")
        result = ctx.export()
        assert "**Goal**: Analyze the code" in result

    def test_export_with_findings(self, mock_memory_manager, test_session_id) -> None:
        """Test exporting with findings."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Research topic")
        ctx.add_finding("Found article A")
        ctx.add_finding("Found article B")
        result = ctx.export()

        assert "**Goal**: Research topic" in result
        assert "**Findings**:" in result
        assert "- Found article A" in result
        assert "- Found article B" in result

    def test_export_without_scratchpad(self, mock_memory_manager, test_session_id) -> None:
        """Test export excludes scratchpad by default."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Test")
        ctx.set_scratchpad("secret", "hidden")
        result = ctx.export(include_scratchpad=False)
        assert "secret" not in result
        assert "hidden" not in result

    def test_export_with_scratchpad(self, mock_memory_manager, test_session_id) -> None:
        """Test export includes scratchpad when requested."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Test")
        ctx.set_scratchpad("note", "important info")
        result = ctx.export(include_scratchpad=True)

        assert "**Notes**:" in result
        assert "note: important info" in result


class TestForSubagent:
    """Test subagent context scoping."""

    def test_for_subagent_basic(self, mock_memory_manager, test_session_id) -> None:
        """Test creating subagent context."""
        parent = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        parent.set_goal("Main research task")
        parent.add_finding("Found source 1")
        parent.add_finding("Found source 2")
        parent.set_scratchpad("parent_note", "value")

        child = parent.for_subagent("Search for details about source 1")

        # Child should have new goal
        assert child.goal == "Search for details about source 1"
        # Child should inherit findings
        assert child.findings == ["Found source 1", "Found source 2"]
        # Child should have fresh scratchpad
        assert child.scratchpad == {}
        # Child should inherit max_findings
        assert child.max_findings == parent.max_findings

    def test_for_subagent_isolation(self, mock_memory_manager, test_session_id) -> None:
        """Test subagent context is isolated from parent."""
        parent = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        parent.add_finding("parent finding")

        child = parent.for_subagent("child task")
        child.add_finding("child finding")

        # Child modification should not affect parent
        assert "child finding" not in parent.findings
        # Parent should only have original finding
        assert parent.findings == ["parent finding"]


class TestClear:
    """Test clear functionality."""

    def test_clear(self, mock_memory_manager, test_session_id) -> None:
        """Test clearing all context state."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Some goal")
        ctx.add_finding("Some finding")
        ctx.set_scratchpad("key", "value")

        ctx.clear()

        assert ctx.goal == ""
        assert ctx.findings == []
        assert ctx.scratchpad == {}


class TestMemoryIntegration:
    """Test optional memory integration methods."""

    @pytest.mark.asyncio
    async def test_save(self, mock_memory_manager, test_session_id) -> None:
        """Test saving context to memory."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Test goal")
        ctx.add_finding("Test finding")
        ctx.set_scratchpad("key", "value")

        await ctx.save(key="test_context")

        mock_memory_manager.store.assert_called_once()
        call_args = mock_memory_manager.store.call_args
        assert call_args.kwargs["key"] == "test_context"
        assert call_args.kwargs["content_type"] == "cognitive_context"
        assert call_args.kwargs["value"]["goal"] == "Test goal"
        assert call_args.kwargs["value"]["findings"] == ["Test finding"]

    @pytest.mark.asyncio
    async def test_load_success(self, mock_memory_manager, test_session_id) -> None:
        """Test loading context from memory."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)

        mock_result = MagicMock()
        mock_result.value = {
            "goal": "Restored goal",
            "findings": ["Restored finding"],
            "scratchpad": {"restored_key": "restored_value"},
            "max_findings": 5,
        }
        mock_memory_manager.read.return_value = mock_result

        success = await ctx.load(key="test_context")

        assert success is True
        assert ctx.goal == "Restored goal"
        assert ctx.findings == ["Restored finding"]
        assert ctx.scratchpad == {"restored_key": "restored_value"}
        assert ctx.max_findings == 5

    @pytest.mark.asyncio
    async def test_load_not_found(self, mock_memory_manager, test_session_id) -> None:
        """Test loading when context not in memory."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Original goal")

        mock_memory_manager.read.return_value = None

        success = await ctx.load()

        assert success is False
        # Original state should be preserved
        assert ctx.goal == "Original goal"

    @pytest.mark.asyncio
    async def test_enrich(self, mock_memory_manager, test_session_id) -> None:
        """Test enriching context from memory."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Research Python async")

        mock_result1 = MagicMock()
        mock_result1.entry.value = "Python async/await introduced in 3.5"
        mock_result2 = MagicMock()
        mock_result2.entry.value = "asyncio is the standard library"
        mock_memory_manager.recall.return_value = [mock_result1, mock_result2]

        recalled = await ctx.enrich(limit=2)

        assert len(recalled) == 2
        assert "[memory]" in recalled[0]
        # Findings should include recalled memories
        assert len(ctx.findings) == 2

    @pytest.mark.asyncio
    async def test_enrich_empty_goal(self, mock_memory_manager, test_session_id) -> None:
        """Test enrich with no goal returns empty."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)

        recalled = await ctx.enrich()

        assert recalled == []
        mock_memory_manager.recall.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrich_with_custom_query(self, mock_memory_manager, test_session_id) -> None:
        """Test enrich with custom query."""
        ctx = CognitiveContext()
        ctx.set_goal("Main goal")

        mock_memory = AsyncMock()
        mock_memory.recall.return_value = []

        await ctx.enrich(mock_memory, query="custom search")

        mock_memory.recall.assert_called_once_with("custom search", limit=3)


class TestPydanticIntegration:
    """Test Pydantic model features."""

    def test_model_dump(self, mock_memory_manager, test_session_id) -> None:
        """Test model serialization."""
        ctx = CognitiveContext(memory_manager=mock_memory_manager, session_id=test_session_id)
        ctx.set_goal("Test")
        ctx.add_finding("Finding")
        ctx.set_scratchpad("key", "value")

        data = ctx.model_dump()

        assert data["goal"] == "Test"
        assert data["findings"] == ["Finding"]
        assert data["scratchpad"] == {"key": "value"}
        assert data["max_findings"] == 8

    def test_model_construct(self, mock_memory_manager, test_session_id) -> None:
        """Test model construction from dict."""
        ctx = CognitiveContext(
            memory_manager=mock_memory_manager,
            session_id=test_session_id,
            goal="Constructed goal",
            findings=["f1", "f2"],
            scratchpad={"k": "v"},
            max_findings=5,
        )

        assert ctx.goal == "Constructed goal"
        assert ctx.findings == ["f1", "f2"]
        assert ctx.scratchpad == {"k": "v"}
        assert ctx.max_findings == 5
