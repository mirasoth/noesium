"""Tests for autonomous mode components (RFC-1005, RFC-1006, RFC-1007).

This module tests the 100% implementation of RFC-1005, RFC-1006, and RFC-1007.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from noeagent.autonomous import (
    AutonomousEvent,
    CognitiveLoop,
    CognitiveLoopMetrics,
    EventQueue,
    GoalEngine,
    GoalStatus,
    Trigger,
)

# ============================================================================
# RFC-1005: Cognitive Loop Tests
# ============================================================================


class TestCognitiveLoopPauseResume:
    """Test CognitiveLoop pause/resume functionality (RFC-1005)."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for CognitiveLoop."""
        goal_engine = MagicMock()
        goal_engine.next_goal = AsyncMock(return_value=None)
        goal_engine.check_timeouts = AsyncMock(return_value=[])

        memory = MagicMock()
        agent_kernel = MagicMock()
        registry = MagicMock()

        return goal_engine, memory, agent_kernel, registry

    def test_initial_state_not_paused(self, mock_components):
        """Verify loop starts in not-paused state."""
        goal_engine, memory, agent_kernel, registry = mock_components
        loop = CognitiveLoop(
            goal_engine=goal_engine,
            memory=memory,
            agent_kernel=agent_kernel,
            capability_registry=registry,
        )

        assert loop.is_paused is False
        assert loop.is_running is False

    def test_pause_sets_paused_state(self, mock_components):
        """Verify pause() sets paused state."""
        goal_engine, memory, agent_kernel, registry = mock_components
        loop = CognitiveLoop(
            goal_engine=goal_engine,
            memory=memory,
            agent_kernel=agent_kernel,
            capability_registry=registry,
        )

        loop.pause()
        assert loop.is_paused is True

    def test_resume_clears_paused_state(self, mock_components):
        """Verify resume() clears paused state."""
        goal_engine, memory, agent_kernel, registry = mock_components
        loop = CognitiveLoop(
            goal_engine=goal_engine,
            memory=memory,
            agent_kernel=agent_kernel,
            capability_registry=registry,
        )

        loop.pause()
        assert loop.is_paused is True

        loop.resume()
        assert loop.is_paused is False


class TestCognitiveLoopMetrics:
    """Test CognitiveLoop metrics collection (RFC-1005)."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for CognitiveLoop."""
        goal_engine = MagicMock()
        goal_engine.next_goal = AsyncMock(return_value=None)
        goal_engine.check_timeouts = AsyncMock(return_value=[])

        memory = MagicMock()
        agent_kernel = MagicMock()
        registry = MagicMock()

        return goal_engine, memory, agent_kernel, registry

    def test_metrics_initial_values(self, mock_components):
        """Verify metrics start at zero."""
        goal_engine, memory, agent_kernel, registry = mock_components
        loop = CognitiveLoop(
            goal_engine=goal_engine,
            memory=memory,
            agent_kernel=agent_kernel,
            capability_registry=registry,
        )

        metrics = loop.metrics
        assert metrics.total_ticks == 0
        assert metrics.successful_ticks == 0
        assert metrics.failed_ticks == 0
        assert metrics.idle_ticks == 0

    @pytest.mark.asyncio
    async def test_metrics_increment_on_idle_tick(self, mock_components):
        """Verify metrics increment on idle tick."""
        goal_engine, memory, agent_kernel, registry = mock_components
        loop = CognitiveLoop(
            goal_engine=goal_engine,
            memory=memory,
            agent_kernel=agent_kernel,
            capability_registry=registry,
        )

        await loop._tick()

        metrics = loop.metrics
        assert metrics.total_ticks == 1
        assert metrics.idle_ticks == 1
        assert metrics.successful_ticks == 1
        assert metrics.last_tick_duration_ms > 0

    def test_metrics_avg_duration_calculation(self):
        """Verify average duration calculation."""
        metrics = CognitiveLoopMetrics(
            total_ticks=10,
            total_tick_duration_ms=1000.0,
        )

        assert metrics.avg_tick_duration_ms == 100.0

    def test_metrics_avg_duration_zero_ticks(self):
        """Verify average duration with zero ticks."""
        metrics = CognitiveLoopMetrics()
        assert metrics.avg_tick_duration_ms == 0.0

    def test_metrics_reset(self):
        """Verify metrics reset."""
        metrics = CognitiveLoopMetrics(
            total_ticks=10,
            successful_ticks=8,
            failed_ticks=2,
            total_tick_duration_ms=1000.0,
        )

        metrics.reset()

        assert metrics.total_ticks == 0
        assert metrics.successful_ticks == 0
        assert metrics.failed_ticks == 0


# ============================================================================
# RFC-1006: Goal Engine Tests
# ============================================================================


class TestGoalDependencies:
    """Test goal dependencies (blocked_by) functionality (RFC-1006)."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock memory provider."""
        storage = MagicMock()
        storage.write = AsyncMock()
        storage.read = AsyncMock(return_value=None)
        storage.list_keys = AsyncMock(return_value=[])
        return storage

    @pytest.mark.asyncio
    async def test_create_goal_with_dependencies(self, mock_storage):
        """Test creating goal with blocked_by dependencies."""
        engine = GoalEngine(memory_provider=mock_storage)

        goal = await engine.create_goal(
            description="Test goal",
            blocked_by=["goal-1", "goal-2"],
        )

        assert goal.blocked_by == ["goal-1", "goal-2"]

    @pytest.mark.asyncio
    async def test_next_goal_skips_blocked_goals(self, mock_storage):
        """Test that next_goal skips goals with incomplete dependencies."""
        engine = GoalEngine(memory_provider=mock_storage)

        # Create dependency goal
        dep_goal = await engine.create_goal("Dependency goal")

        # Create dependent goal (assigned to _ to indicate intentionally unused)
        await engine.create_goal(
            "Blocked goal",
            blocked_by=[dep_goal.id],
        )

        # next_goal should not return the blocked goal
        next_goal = await engine.next_goal()
        assert next_goal is not None
        assert next_goal.id == dep_goal.id

    @pytest.mark.asyncio
    async def test_next_goal_returns_unblocked_goal(self, mock_storage):
        """Test that next_goal returns goal when dependencies complete."""
        engine = GoalEngine(memory_provider=mock_storage)

        # Create and complete dependency goal
        dep_goal = await engine.create_goal("Dependency goal")
        await engine.complete_goal(dep_goal.id)

        # Create dependent goal
        dependent_goal = await engine.create_goal(
            "Dependent goal",
            blocked_by=[dep_goal.id],
        )

        # next_goal should now return the dependent goal
        next_goal = await engine.next_goal()
        assert next_goal is not None
        assert next_goal.id == dependent_goal.id

    @pytest.mark.asyncio
    async def test_add_dependency(self, mock_storage):
        """Test adding dependency to existing goal."""
        engine = GoalEngine(memory_provider=mock_storage)

        goal = await engine.create_goal("Test goal")
        assert goal.blocked_by == []

        updated_goal = await engine.add_dependency(goal.id, "dep-goal-1")
        assert "dep-goal-1" in updated_goal.blocked_by

    @pytest.mark.asyncio
    async def test_remove_dependency(self, mock_storage):
        """Test removing dependency from goal."""
        engine = GoalEngine(memory_provider=mock_storage)

        goal = await engine.create_goal(
            "Test goal",
            blocked_by=["dep-1", "dep-2"],
        )

        updated_goal = await engine.remove_dependency(goal.id, "dep-1")
        assert "dep-1" not in updated_goal.blocked_by
        assert "dep-2" in updated_goal.blocked_by


class TestGoalTimeout:
    """Test goal timeout/deadline functionality (RFC-1006)."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock memory provider."""
        storage = MagicMock()
        storage.write = AsyncMock()
        storage.read = AsyncMock(return_value=None)
        storage.list_keys = AsyncMock(return_value=[])
        return storage

    @pytest.mark.asyncio
    async def test_create_goal_with_deadline(self, mock_storage):
        """Test creating goal with deadline."""
        engine = GoalEngine(memory_provider=mock_storage)

        deadline = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        goal = await engine.create_goal(
            description="Test goal",
            deadline=deadline,
        )

        assert goal.deadline == deadline

    @pytest.mark.asyncio
    async def test_check_timeouts_fails_expired_goals(self, mock_storage):
        """Test that check_timeouts fails goals past deadline."""
        engine = GoalEngine(memory_provider=mock_storage)

        # Create goal with past deadline
        past_deadline = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
        goal = await engine.create_goal(
            description="Expired goal",
            deadline=past_deadline,
            max_retries=0,  # No retries for timeout
        )

        # Check timeouts
        failed_goals = await engine.check_timeouts()

        assert len(failed_goals) == 1
        assert failed_goals[0].id == goal.id

    @pytest.mark.asyncio
    async def test_check_timeouts_ignores_valid_goals(self, mock_storage):
        """Test that check_timeouts ignores goals within deadline."""
        engine = GoalEngine(memory_provider=mock_storage)

        # Create goal with future deadline (assigned to _ to indicate intentionally unused)
        future_deadline = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        await engine.create_goal(
            description="Valid goal",
            deadline=future_deadline,
        )

        # Check timeouts
        failed_goals = await engine.check_timeouts()

        assert len(failed_goals) == 0


class TestGoalRetryPolicy:
    """Test goal retry policy functionality (RFC-1006)."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock memory provider."""
        storage = MagicMock()
        storage.write = AsyncMock()
        storage.read = AsyncMock(return_value=None)
        storage.list_keys = AsyncMock(return_value=[])
        return storage

    @pytest.mark.asyncio
    async def test_fail_goal_with_retries_remaining(self, mock_storage):
        """Test that fail_goal retries when retries remain."""
        engine = GoalEngine(memory_provider=mock_storage)

        goal = await engine.create_goal(
            description="Test goal",
            max_retries=3,
        )
        # Activate goal first
        await engine.update_goal(goal.id, GoalStatus.ACTIVE)

        # Fail goal (should retry)
        failed_goal = await engine.fail_goal(goal.id, error="Test error")

        assert failed_goal.status == GoalStatus.PENDING
        assert failed_goal.retry_count == 1

    @pytest.mark.asyncio
    async def test_fail_goal_exhausted_retries(self, mock_storage):
        """Test that fail_goal fails permanently when retries exhausted."""
        engine = GoalEngine(memory_provider=mock_storage)

        goal = await engine.create_goal(
            description="Test goal",
            max_retries=1,
        )
        await engine.update_goal(goal.id, GoalStatus.ACTIVE)

        # First failure - should retry
        goal = await engine.fail_goal(goal.id, error="Error 1")
        assert goal.status == GoalStatus.PENDING
        assert goal.retry_count == 1

        await engine.update_goal(goal.id, GoalStatus.ACTIVE)

        # Second failure - should fail permanently
        goal = await engine.fail_goal(goal.id, error="Error 2")
        assert goal.status == GoalStatus.FAILED

    @pytest.mark.asyncio
    async def test_fail_goal_allow_retry_false(self, mock_storage):
        """Test that fail_goal respects allow_retry=False."""
        engine = GoalEngine(memory_provider=mock_storage)

        goal = await engine.create_goal(
            description="Test goal",
            max_retries=3,
        )
        await engine.update_goal(goal.id, GoalStatus.ACTIVE)

        # Fail with allow_retry=False (e.g., timeout)
        failed_goal = await engine.fail_goal(goal.id, error="Timeout", allow_retry=False)

        assert failed_goal.status == GoalStatus.FAILED
        assert failed_goal.retry_count == 0


# ============================================================================
# RFC-1007: Event System Tests
# ============================================================================


class TestEventDeduplication:
    """Test EventQueue deduplication functionality (RFC-1007)."""

    @pytest.mark.asyncio
    async def test_enqueue_returns_true_for_new_event(self):
        """Test that enqueue returns True for new events."""
        queue = EventQueue(dedup_window_seconds=5.0)

        event = AutonomousEvent(
            type="test.event",
            source="test",
            payload={"key": "value"},
        )

        result = await queue.enqueue(event)
        assert result is True
        assert queue.size == 1

    @pytest.mark.asyncio
    async def test_enqueue_returns_false_for_duplicate(self):
        """Test that enqueue returns False for duplicate events."""
        queue = EventQueue(dedup_window_seconds=5.0)

        event1 = AutonomousEvent(
            type="test.event",
            source="test",
            payload={"key": "value"},
        )
        event2 = AutonomousEvent(
            type="test.event",
            source="test",
            payload={"key": "value"},
        )

        result1 = await queue.enqueue(event1)
        result2 = await queue.enqueue(event2)

        assert result1 is True
        assert result2 is False
        assert queue.size == 1

    @pytest.mark.asyncio
    async def test_different_events_not_deduplicated(self):
        """Test that different events are not deduplicated."""
        queue = EventQueue(dedup_window_seconds=5.0)

        event1 = AutonomousEvent(
            type="test.event",
            source="test",
            payload={"key": "value1"},
        )
        event2 = AutonomousEvent(
            type="test.event",
            source="test",
            payload={"key": "value2"},  # Different payload
        )

        result1 = await queue.enqueue(event1)
        result2 = await queue.enqueue(event2)

        assert result1 is True
        assert result2 is True
        assert queue.size == 2

    @pytest.mark.asyncio
    async def test_dedup_cache_size(self):
        """Test dedup_cache_size property."""
        queue = EventQueue(dedup_window_seconds=5.0)

        for i in range(5):
            event = AutonomousEvent(
                type="test.event",
                source="test",
                payload={"index": i},
            )
            await queue.enqueue(event)

        assert queue.dedup_cache_size == 5

    @pytest.mark.asyncio
    async def test_clear_clears_dedup_cache(self):
        """Test that clear() also clears dedup cache."""
        queue = EventQueue(dedup_window_seconds=5.0)

        event = AutonomousEvent(
            type="test.event",
            source="test",
            payload={"key": "value"},
        )
        await queue.enqueue(event)

        assert queue.dedup_cache_size == 1

        queue.clear()

        assert queue.dedup_cache_size == 0


class TestTriggerEvaluation:
    """Test Trigger evaluation functionality (RFC-1007)."""

    def test_trigger_matches_event_type(self):
        """Test that trigger matches correct event type."""
        trigger = Trigger(
            id="test-trigger",
            event_type="test.event",
            goal_template="Handle test event",
        )

        event = AutonomousEvent(
            type="test.event",
            source="test",
            payload={},
        )

        assert trigger.evaluate(event) is True

    def test_trigger_does_not_match_wrong_type(self):
        """Test that trigger doesn't match wrong event type."""
        trigger = Trigger(
            id="test-trigger",
            event_type="test.event",
            goal_template="Handle test event",
        )

        event = AutonomousEvent(
            type="other.event",
            source="test",
            payload={},
        )

        assert trigger.evaluate(event) is False

    def test_trigger_with_condition(self):
        """Test trigger with custom condition function."""
        trigger = Trigger(
            id="test-trigger",
            event_type="test.event",
            goal_template="Handle priority event",
            condition=lambda e: e.payload.get("priority", 0) > 5,
        )

        low_priority = AutonomousEvent(
            type="test.event",
            source="test",
            payload={"priority": 3},
        )
        high_priority = AutonomousEvent(
            type="test.event",
            source="test",
            payload={"priority": 10},
        )

        assert trigger.evaluate(low_priority) is False
        assert trigger.evaluate(high_priority) is True

    def test_trigger_goal_template_substitution(self):
        """Test goal template placeholder substitution."""
        trigger = Trigger(
            id="test-trigger",
            event_type="filesystem.change",
            goal_template="Process file: {path} ({action})",
        )

        event = AutonomousEvent(
            type="filesystem.change",
            source="watchdog",
            payload={"path": "/tmp/test.txt", "action": "create"},
        )

        description = trigger.create_goal_description(event)
        assert description == "Process file: /tmp/test.txt (create)"


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.integration
class TestAutonomousModeIntegration:
    """Integration tests for autonomous mode components."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock memory provider."""
        storage = MagicMock()
        storage.write = AsyncMock()
        storage.read = AsyncMock(return_value=None)
        storage.list_keys = AsyncMock(return_value=[])
        return storage

    @pytest.mark.asyncio
    async def test_goal_lifecycle_with_dependencies(self, mock_storage):
        """Test full goal lifecycle with dependencies."""
        engine = GoalEngine(memory_provider=mock_storage)

        # Create parent goal
        parent = await engine.create_goal("Parent task", priority=70)

        # Create dependent goal
        child = await engine.create_goal(
            "Child task",
            priority=80,
            blocked_by=[parent.id],
        )

        # Child has higher priority but is blocked
        next_goal = await engine.next_goal()
        assert next_goal.id == parent.id

        # Complete parent
        await engine.complete_goal(parent.id)

        # Now child should be available
        next_goal = await engine.next_goal()
        assert next_goal.id == child.id
