"""Unit tests for the core subagent framework (RFC-1006).

Tests cover all core subagent components without any NoeAgent dependencies:
- SubagentDescriptor: creation, matching, normalization
- SubagentContext: child spawning, depth limits
- SubagentRoutingPolicy: invocation rules, auto-routing validation
- SubagentProgressEvent: factory methods, serialization, terminal detection
- SubagentInvocationRequest / SubagentInvocationResult: creation, serialization
- SubagentManager: register, select, invoke, stream, cleanup
- SubagentProvider: from_instance, from_factory, from class
- SubagentLoader: config-based discovery
"""

from __future__ import annotations

from typing import Any, AsyncGenerator

import pytest

from noesium.core.agent.subagent.context import SubagentContext
from noesium.core.agent.subagent.descriptor import (
    BackendType,
    CostHint,
    LatencyHint,
    SubagentDescriptor,
    SubagentRoutingPolicy,
)
from noesium.core.agent.subagent.events import (
    SubagentErrorCode,
    SubagentEventType,
    SubagentProgressEvent,
)
from noesium.core.agent.subagent.manager import SubagentLoader, SubagentManager, SubagentQuery
from noesium.core.agent.subagent.protocol import BaseSubagentRuntime, SubagentProvider
from noesium.core.agent.subagent.request import SubagentInvocationRequest, SubagentInvocationResult

# ---------------------------------------------------------------------------
# Helpers: minimal concrete runtime for testing
# ---------------------------------------------------------------------------


class MinimalRuntime(BaseSubagentRuntime):
    """Minimal BaseSubagentRuntime for unit tests."""

    _static_descriptor = SubagentDescriptor(
        subagent_id="minimal",
        display_name="Minimal",
        description="Test runtime",
        backend_type=BackendType.INPROC,
        task_types=["test", "unit"],
        keywords=["minimal", "test"],
    )

    @classmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        return cls._static_descriptor

    async def health(self) -> bool:
        return True

    async def execute(self, task: str, **kwargs: Any) -> AsyncGenerator[SubagentProgressEvent, None]:
        request_id = kwargs.get("request_id", "req-test")
        yield SubagentProgressEvent.start(request_id=request_id, subagent_id="minimal")
        yield SubagentProgressEvent.progress(
            request_id=request_id,
            subagent_id="minimal",
            summary=f"Working on: {task}",
        )
        yield SubagentProgressEvent.end(
            request_id=request_id,
            subagent_id="minimal",
            summary="Done",
            detail=f"result:{task}",
        )


class FailingRuntime(BaseSubagentRuntime):
    """Runtime that always raises an exception during execute."""

    _static_descriptor = SubagentDescriptor(
        subagent_id="failing",
        display_name="Failing",
        description="Always fails",
        backend_type=BackendType.INPROC,
    )

    @classmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        return cls._static_descriptor

    async def health(self) -> bool:
        return True

    async def execute(self, task: str, **kwargs: Any) -> AsyncGenerator[SubagentProgressEvent, None]:
        request_id = kwargs.get("request_id", "req-fail")
        yield SubagentProgressEvent.start(request_id=request_id, subagent_id="failing")
        raise RuntimeError("intentional failure")
        yield  # make it an async generator


class UnhealthyRuntime(BaseSubagentRuntime):
    """Runtime that reports unhealthy."""

    _static_descriptor = SubagentDescriptor(
        subagent_id="unhealthy",
        display_name="Unhealthy",
        description="Never healthy",
        backend_type=BackendType.INPROC,
    )

    @classmethod
    def get_descriptor(cls) -> SubagentDescriptor:
        return cls._static_descriptor

    async def health(self) -> bool:
        return False

    async def execute(self, task: str, **kwargs: Any) -> AsyncGenerator[SubagentProgressEvent, None]:
        yield SubagentProgressEvent.end(request_id="x", subagent_id="unhealthy", summary="done")


# ---------------------------------------------------------------------------
# SubagentDescriptor Tests
# ---------------------------------------------------------------------------


class TestSubagentDescriptor:
    def test_creation_with_defaults(self):
        d = SubagentDescriptor(
            subagent_id="test_agent",
            display_name="Test Agent",
            description="A test subagent",
            backend_type=BackendType.BUILTIN,
        )
        assert d.subagent_id == "test_agent"
        assert d.display_name == "Test Agent"
        assert d.backend_type == BackendType.BUILTIN
        assert d.supports_streaming is True
        assert d.requires_explicit_command is False
        assert d.cost_hint == CostHint.MEDIUM
        assert d.latency_hint == LatencyHint.BATCH
        assert d.task_types == []
        assert d.keywords == []

    def test_creation_with_string_enums(self):
        """String literals are normalized to enums in __post_init__."""
        d = SubagentDescriptor(
            subagent_id="x",
            display_name="X",
            description="desc",
            backend_type="cli",
            cost_hint="high",
            latency_hint="slow",
        )
        assert d.backend_type == BackendType.CLI
        assert d.cost_hint == CostHint.HIGH
        assert d.latency_hint == LatencyHint.SLOW

    def test_matches_task_type_no_restrictions(self):
        d = SubagentDescriptor(subagent_id="x", display_name="X", description="d", backend_type=BackendType.INPROC)
        assert d.matches_task_type("anything") is True

    def test_matches_task_type_with_types(self):
        d = SubagentDescriptor(
            subagent_id="x",
            display_name="X",
            description="d",
            backend_type=BackendType.INPROC,
            task_types=["web_search", "scraping"],
        )
        assert d.matches_task_type("web_search") is True
        assert d.matches_task_type("scraping") is True
        assert d.matches_task_type("coding") is False

    def test_matches_keywords_empty_query(self):
        d = SubagentDescriptor(
            subagent_id="x",
            display_name="X",
            description="d",
            backend_type=BackendType.INPROC,
            keywords=["browser", "click"],
        )
        assert d.matches_keywords([]) is True

    def test_matches_keywords_overlap(self):
        d = SubagentDescriptor(
            subagent_id="x",
            display_name="X",
            description="d",
            backend_type=BackendType.INPROC,
            keywords=["browser", "click", "navigate"],
        )
        assert d.matches_keywords(["browser", "other"]) is True
        assert d.matches_keywords(["unknown_keyword"]) is False

    def test_all_enum_values(self):
        assert BackendType.INPROC.value == "inproc"
        assert BackendType.BUILTIN.value == "builtin"
        assert BackendType.CLI.value == "cli"
        assert BackendType.REMOTE.value == "remote"

        assert CostHint.LOW.value == "low"
        assert CostHint.MEDIUM.value == "medium"
        assert CostHint.HIGH.value == "high"
        assert CostHint.VARIABLE.value == "variable"

        assert LatencyHint.INTERACTIVE.value == "interactive"
        assert LatencyHint.BATCH.value == "batch"
        assert LatencyHint.SLOW.value == "slow"


# ---------------------------------------------------------------------------
# SubagentContext Tests
# ---------------------------------------------------------------------------


class TestSubagentContext:
    def test_creation_with_defaults(self):
        ctx = SubagentContext(session_id="s1", parent_id="p1")
        assert ctx.session_id == "s1"
        assert ctx.parent_id == "p1"
        assert ctx.depth == 0
        assert ctx.max_depth == 5
        assert ctx.shared_memory is None
        assert ctx.config == {}
        assert ctx.permission_context == {}

    def test_can_spawn_child_true(self):
        ctx = SubagentContext(session_id="s", parent_id="p", depth=2, max_depth=5)
        assert ctx.can_spawn_child() is True

    def test_can_spawn_child_at_limit(self):
        ctx = SubagentContext(session_id="s", parent_id="p", depth=5, max_depth=5)
        assert ctx.can_spawn_child() is False

    def test_child_context_increments_depth(self):
        parent_ctx = SubagentContext(
            session_id="parent",
            parent_id="root",
            depth=0,
            max_depth=3,
            config={"key": "value"},
        )
        child_ctx = parent_ctx.child_context("child-session")
        assert child_ctx.depth == 1
        assert child_ctx.session_id == "child-session"
        assert child_ctx.parent_id == "parent"
        assert child_ctx.max_depth == 3
        assert child_ctx.config["key"] == "value"

    def test_child_context_with_overrides(self):
        parent_ctx = SubagentContext(
            session_id="parent",
            parent_id="root",
            depth=0,
            config={"a": 1, "b": 2},
        )
        child_ctx = parent_ctx.child_context("child", config_overrides={"b": 99, "c": 3})
        assert child_ctx.config["a"] == 1
        assert child_ctx.config["b"] == 99
        assert child_ctx.config["c"] == 3

    def test_child_context_raises_at_max_depth(self):
        ctx = SubagentContext(session_id="s", parent_id="p", depth=5, max_depth=5)
        with pytest.raises(RuntimeError, match="max depth"):
            ctx.child_context("child")

    def test_shared_memory_propagates(self):
        memory = {"key": "shared"}
        parent_ctx = SubagentContext(session_id="s", parent_id="p", shared_memory=memory)
        child_ctx = parent_ctx.child_context("child")
        assert child_ctx.shared_memory is memory


# ---------------------------------------------------------------------------
# SubagentRoutingPolicy Tests
# ---------------------------------------------------------------------------


class TestSubagentRoutingPolicy:
    def test_defaults(self):
        policy = SubagentRoutingPolicy()
        assert policy.allow_auto_routing is True
        assert policy.requires_explicit_command is False
        assert policy.max_depth == 5
        assert policy.permission_profile == "default"

    def test_can_be_invoked_by_depth_ok(self):
        policy = SubagentRoutingPolicy(max_depth=3)
        assert policy.can_be_invoked_by("orchestrator", 2) is True

    def test_can_be_invoked_by_depth_exceeded(self):
        policy = SubagentRoutingPolicy(max_depth=3)
        assert policy.can_be_invoked_by("orchestrator", 3) is False

    def test_can_be_invoked_by_parent_restriction(self):
        policy = SubagentRoutingPolicy(allowed_parent_agent_types=["noe"])
        assert policy.can_be_invoked_by("noe", 0) is True
        assert policy.can_be_invoked_by("other", 0) is False

    def test_can_be_invoked_by_no_parent_restriction(self):
        policy = SubagentRoutingPolicy(allowed_parent_agent_types=[])
        assert policy.can_be_invoked_by("anything", 0) is True

    def test_validate_auto_routing_allowed(self):
        policy = SubagentRoutingPolicy(allow_auto_routing=True)
        allowed, reason = policy.validate_auto_routing()
        assert allowed is True
        assert reason is None

    def test_validate_auto_routing_disabled(self):
        policy = SubagentRoutingPolicy(allow_auto_routing=False)
        allowed, reason = policy.validate_auto_routing()
        assert allowed is False
        assert reason is not None

    def test_validate_auto_routing_explicit_required(self):
        policy = SubagentRoutingPolicy(allow_auto_routing=True, requires_explicit_command=True)
        allowed, reason = policy.validate_auto_routing()
        assert allowed is False
        assert "explicit" in reason.lower()


# ---------------------------------------------------------------------------
# SubagentProgressEvent Tests
# ---------------------------------------------------------------------------


class TestSubagentProgressEvent:
    def test_start_factory(self):
        evt = SubagentProgressEvent.start(request_id="req1", subagent_id="agent1")
        assert evt.event_type == SubagentEventType.SUBAGENT_START
        assert evt.request_id == "req1"
        assert evt.subagent_id == "agent1"

    def test_progress_factory(self):
        evt = SubagentProgressEvent.progress(
            request_id="req1",
            subagent_id="agent1",
            summary="Working...",
            detail="details here",
        )
        assert evt.event_type == SubagentEventType.SUBAGENT_PROGRESS
        assert evt.summary == "Working..."
        assert evt.detail == "details here"

    def test_thought_factory(self):
        evt = SubagentProgressEvent.thought(request_id="req1", subagent_id="agent1", thought="I'm thinking")
        assert evt.event_type == SubagentEventType.SUBAGENT_THOUGHT
        assert evt.detail == "I'm thinking"

    def test_tool_call_factory(self):
        evt = SubagentProgressEvent.tool_call(
            request_id="req1",
            subagent_id="agent1",
            tool_name="web_search",
            tool_args={"query": "test"},
        )
        assert evt.event_type == SubagentEventType.SUBAGENT_TOOL_CALL
        assert evt.tool_name == "web_search"
        assert evt.tool_args == {"query": "test"}

    def test_tool_result_factory(self):
        evt = SubagentProgressEvent.tool_result(
            request_id="req1",
            subagent_id="agent1",
            tool_name="web_search",
            result={"results": []},
        )
        assert evt.event_type == SubagentEventType.SUBAGENT_TOOL_RESULT
        assert evt.tool_name == "web_search"
        assert evt.tool_result == {"results": []}

    def test_hitl_request_factory(self):
        evt = SubagentProgressEvent.hitl_request(
            request_id="req1",
            subagent_id="agent1",
            prompt="Please enter CAPTCHA",
            options=["A", "B"],
            timeout_s=60.0,
        )
        assert evt.event_type == SubagentEventType.SUBAGENT_HITL_REQUEST
        assert evt.hitl_prompt == "Please enter CAPTCHA"
        assert evt.hitl_options == ["A", "B"]
        assert evt.hitl_timeout_s == 60.0
        assert evt.is_hitl_request() is True

    def test_error_factory(self):
        evt = SubagentProgressEvent.error(
            request_id="req1",
            subagent_id="agent1",
            error_code=SubagentErrorCode.SUBAGENT_TIMEOUT.value,
            error_message="timed out",
        )
        assert evt.event_type == SubagentEventType.SUBAGENT_ERROR
        assert evt.error_code == "SUBAGENT_TIMEOUT"
        assert evt.error_message == "timed out"

    def test_end_factory(self):
        evt = SubagentProgressEvent.end(
            request_id="req1",
            subagent_id="agent1",
            summary="Done",
            detail="final answer",
        )
        assert evt.event_type == SubagentEventType.SUBAGENT_END
        assert evt.detail == "final answer"

    def test_is_terminal(self):
        end_evt = SubagentProgressEvent.end(request_id="r", subagent_id="a")
        err_evt = SubagentProgressEvent.error(request_id="r", subagent_id="a", error_code="X", error_message="m")
        start_evt = SubagentProgressEvent.start(request_id="r", subagent_id="a")

        assert end_evt.is_terminal() is True
        assert err_evt.is_terminal() is True
        assert start_evt.is_terminal() is False

    def test_to_dict_minimal(self):
        evt = SubagentProgressEvent.start(request_id="req1", subagent_id="agent1")
        d = evt.to_dict()
        assert d["event_type"] == "subagent.start"
        assert d["request_id"] == "req1"
        assert d["subagent_id"] == "agent1"
        assert "event_id" in d
        assert "timestamp" in d

    def test_to_dict_with_error_fields(self):
        evt = SubagentProgressEvent.error(
            request_id="req1",
            subagent_id="agent1",
            error_code="ERR",
            error_message="message",
        )
        d = evt.to_dict()
        assert d["error_code"] == "ERR"
        assert d["error_message"] == "message"

    def test_to_dict_with_hitl_fields(self):
        evt = SubagentProgressEvent.hitl_request(request_id="r", subagent_id="a", prompt="prompt?", timeout_s=30.0)
        d = evt.to_dict()
        assert d["hitl_prompt"] == "prompt?"
        assert d["hitl_timeout_s"] == 30.0

    def test_event_id_is_unique(self):
        evt1 = SubagentProgressEvent.start(request_id="r", subagent_id="a")
        evt2 = SubagentProgressEvent.start(request_id="r", subagent_id="a")
        assert evt1.event_id != evt2.event_id


# ---------------------------------------------------------------------------
# SubagentInvocationRequest Tests
# ---------------------------------------------------------------------------


class TestSubagentInvocationRequest:
    def test_creation_with_defaults(self):
        req = SubagentInvocationRequest(subagent_id="agent", message="do thing")
        assert req.subagent_id == "agent"
        assert req.message == "do thing"
        assert req.execution_mode == "oneshot"
        assert req.timeout_s is None
        assert req.cancellation_token is None
        assert req.context == {}
        assert req.policy_overrides == {}
        assert req.metadata == {}

    def test_request_id_is_unique(self):
        req1 = SubagentInvocationRequest(subagent_id="a", message="m")
        req2 = SubagentInvocationRequest(subagent_id="a", message="m")
        assert req1.request_id != req2.request_id

    def test_with_timeout(self):
        req = SubagentInvocationRequest(subagent_id="a", message="m")
        req2 = req.with_timeout(30.0)
        assert req2.timeout_s == 30.0
        assert req2.request_id == req.request_id  # same ID

    def test_with_context(self):
        req = SubagentInvocationRequest(subagent_id="a", message="m", context={"x": 1})
        req2 = req.with_context(y=2)
        assert req2.context == {"x": 1, "y": 2}
        assert req.context == {"x": 1}  # original unchanged

    def test_to_dict(self):
        req = SubagentInvocationRequest(subagent_id="agent", message="task", timeout_s=60.0)
        d = req.to_dict()
        assert d["subagent_id"] == "agent"
        assert d["message"] == "task"
        assert d["timeout_s"] == 60.0
        assert "request_id" in d


# ---------------------------------------------------------------------------
# SubagentInvocationResult Tests
# ---------------------------------------------------------------------------


class TestSubagentInvocationResult:
    def test_success_result(self):
        r = SubagentInvocationResult.success_result(
            request_id="req1",
            subagent_id="agent",
            final_text="Done!",
        )
        assert r.success is True
        assert r.final_text == "Done!"
        assert r.error_code is None
        assert r.error_message is None

    def test_failure_result(self):
        r = SubagentInvocationResult.failure_result(
            request_id="req1",
            subagent_id="agent",
            error_code="SUBAGENT_TIMEOUT",
            error_message="Timed out",
            partial_text="partial",
        )
        assert r.success is False
        assert r.error_code == "SUBAGENT_TIMEOUT"
        assert r.error_message == "Timed out"
        assert r.final_text == "partial"

    def test_to_dict(self):
        r = SubagentInvocationResult.success_result(request_id="r", subagent_id="a", final_text="ok")
        d = r.to_dict()
        assert d["success"] is True
        assert d["final_text"] == "ok"
        assert "timestamp" in d

    def test_to_dict_with_error(self):
        r = SubagentInvocationResult.failure_result(
            request_id="r", subagent_id="a", error_code="ERR", error_message="msg"
        )
        d = r.to_dict()
        assert d["success"] is False
        assert d["error_code"] == "ERR"
        assert d["error_message"] == "msg"


# ---------------------------------------------------------------------------
# SubagentProvider Tests
# ---------------------------------------------------------------------------


class TestSubagentProvider:
    @pytest.mark.asyncio
    async def test_from_class(self):
        provider = SubagentProvider(MinimalRuntime)
        assert provider.subagent_id == "minimal"
        runtime = await provider.get_runtime()
        assert isinstance(runtime, MinimalRuntime)

    @pytest.mark.asyncio
    async def test_from_class_lazy_instantiation(self):
        provider = SubagentProvider(MinimalRuntime)
        assert provider._instance is None
        await provider.get_runtime()
        assert provider._instance is not None
        # Second call returns the same instance
        runtime2 = await provider.get_runtime()
        assert runtime2 is provider._instance

    @pytest.mark.asyncio
    async def test_from_instance(self):
        runtime = MinimalRuntime()
        provider = SubagentProvider.from_instance(runtime)
        assert provider.subagent_id == "minimal"
        assert provider._instance is runtime
        # get_runtime returns the pre-built instance
        got = await provider.get_runtime()
        assert got is runtime

    @pytest.mark.asyncio
    async def test_from_factory(self):
        factory_calls = []

        def factory() -> MinimalRuntime:
            factory_calls.append(1)
            return MinimalRuntime()

        descriptor = MinimalRuntime.get_descriptor()
        provider = SubagentProvider.from_factory(factory, descriptor)
        assert provider.subagent_id == "minimal"
        await provider.get_runtime()
        assert len(factory_calls) == 1
        # Second call does NOT call factory again
        await provider.get_runtime()
        assert len(factory_calls) == 1

    @pytest.mark.asyncio
    async def test_health_lazy(self):
        provider = SubagentProvider(MinimalRuntime)
        # Not instantiated yet -> always healthy
        assert await provider.health() is True

    @pytest.mark.asyncio
    async def test_health_after_instantiation(self):
        provider = SubagentProvider(MinimalRuntime)
        await provider.get_runtime()
        assert await provider.health() is True

    @pytest.mark.asyncio
    async def test_invoke_returns_result(self):
        provider = SubagentProvider(MinimalRuntime)
        request = SubagentInvocationRequest(subagent_id="minimal", message="hello")
        result = await provider.invoke(request)
        assert result.success is True
        assert "hello" in result.final_text

    @pytest.mark.asyncio
    async def test_invoke_stream_yields_events(self):
        provider = SubagentProvider(MinimalRuntime)
        request = SubagentInvocationRequest(subagent_id="minimal", message="test")
        events = []
        async for evt in provider.invoke_stream(request):
            events.append(evt)

        event_types = [e.event_type for e in events]
        assert SubagentEventType.SUBAGENT_START in event_types
        assert SubagentEventType.SUBAGENT_END in event_types

    @pytest.mark.asyncio
    async def test_cleanup(self):
        provider = SubagentProvider(MinimalRuntime)
        await provider.get_runtime()
        assert provider._instance is not None
        await provider.cleanup()
        assert provider._instance is None


# ---------------------------------------------------------------------------
# SubagentManager Tests
# ---------------------------------------------------------------------------


class TestSubagentManager:
    def make_manager(self) -> SubagentManager:
        return SubagentManager(default_timeout_s=10.0, max_concurrent=3)

    def test_register_and_list(self):
        mgr = self.make_manager()
        provider = SubagentProvider(MinimalRuntime)
        mgr.register(provider)
        assert len(mgr.list_providers()) == 1
        assert mgr.list_descriptors()[0].subagent_id == "minimal"

    def test_get_provider_found(self):
        mgr = self.make_manager()
        provider = SubagentProvider(MinimalRuntime)
        mgr.register(provider)
        found = mgr.get_provider("minimal")
        assert found is provider

    def test_get_provider_not_found(self):
        mgr = self.make_manager()
        assert mgr.get_provider("nonexistent") is None

    def test_unregister(self):
        mgr = self.make_manager()
        mgr.register(SubagentProvider(MinimalRuntime))
        result = mgr.unregister("minimal")
        assert result is True
        assert mgr.get_provider("minimal") is None

    def test_unregister_not_found(self):
        mgr = self.make_manager()
        assert mgr.unregister("nonexistent") is False

    def test_register_runtime_class(self):
        mgr = self.make_manager()
        mgr.register_runtime_class(MinimalRuntime)
        assert mgr.get_provider("minimal") is not None

    def test_select_no_filters(self):
        mgr = self.make_manager()
        mgr.register(SubagentProvider(MinimalRuntime))
        results = mgr.select(SubagentQuery())
        assert len(results) == 1

    def test_select_by_task_type(self):
        mgr = self.make_manager()
        mgr.register(SubagentProvider(MinimalRuntime))
        results = mgr.select(SubagentQuery(task_type="test"))
        assert len(results) == 1
        results_miss = mgr.select(SubagentQuery(task_type="unknown_type"))
        assert len(results_miss) == 0

    def test_select_by_keywords(self):
        mgr = self.make_manager()
        mgr.register(SubagentProvider(MinimalRuntime))
        results = mgr.select(SubagentQuery(keywords=["minimal"]))
        assert len(results) == 1
        results_miss = mgr.select(SubagentQuery(keywords=["no_match"]))
        assert len(results_miss) == 0

    def test_select_excludes_explicit_only(self):
        from noesium.core.agent.subagent.descriptor import SubagentRoutingPolicy

        mgr = self.make_manager()
        provider = SubagentProvider(MinimalRuntime)
        policy = SubagentRoutingPolicy(requires_explicit_command=True)
        mgr.register(provider, policy)

        results_excl = mgr.select(SubagentQuery(exclude_explicit_only=True))
        assert len(results_excl) == 0

        results_incl = mgr.select(SubagentQuery(exclude_explicit_only=False))
        assert len(results_incl) == 1

    def test_select_depth_limit(self):
        mgr = self.make_manager()
        mgr.register(SubagentProvider(MinimalRuntime))
        # Context at max depth can't spawn child
        ctx = SubagentContext(session_id="s", parent_id="p", depth=5, max_depth=5)
        results = mgr.select(SubagentQuery(), context=ctx)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_invoke_success(self):
        mgr = self.make_manager()
        mgr.register(SubagentProvider(MinimalRuntime))
        request = SubagentInvocationRequest(subagent_id="minimal", message="hello")
        result = await mgr.invoke("minimal", request)
        assert result.success is True
        assert "hello" in result.final_text

    @pytest.mark.asyncio
    async def test_invoke_not_found(self):
        mgr = self.make_manager()
        request = SubagentInvocationRequest(subagent_id="ghost", message="hello")
        result = await mgr.invoke("ghost", request)
        assert result.success is False
        assert result.error_code == SubagentErrorCode.SUBAGENT_NOT_FOUND.value

    @pytest.mark.asyncio
    async def test_invoke_unhealthy(self):
        mgr = self.make_manager()
        runtime = UnhealthyRuntime()
        mgr.register(SubagentProvider.from_instance(runtime))
        request = SubagentInvocationRequest(subagent_id="unhealthy", message="x")
        result = await mgr.invoke("unhealthy", request)
        assert result.success is False
        assert result.error_code == SubagentErrorCode.SUBAGENT_UNHEALTHY.value

    @pytest.mark.asyncio
    async def test_invoke_policy_denied(self):
        from noesium.core.agent.subagent.descriptor import SubagentRoutingPolicy

        mgr = self.make_manager()
        mgr.register(
            SubagentProvider(MinimalRuntime),
            SubagentRoutingPolicy(max_depth=2),
        )
        # Context at depth >= max_depth should be denied
        ctx = SubagentContext(session_id="s", parent_id="p", depth=2, max_depth=5)
        request = SubagentInvocationRequest(subagent_id="minimal", message="x")
        result = await mgr.invoke("minimal", request, context=ctx)
        assert result.success is False
        assert result.error_code == SubagentErrorCode.SUBAGENT_POLICY_DENIED.value

    @pytest.mark.asyncio
    async def test_invoke_stream_success(self):
        mgr = self.make_manager()
        mgr.register(SubagentProvider(MinimalRuntime))
        request = SubagentInvocationRequest(subagent_id="minimal", message="stream")
        events = []
        async for evt in mgr.invoke_stream("minimal", request):
            events.append(evt)
        types = [e.event_type for e in events]
        assert SubagentEventType.SUBAGENT_START in types
        assert SubagentEventType.SUBAGENT_END in types

    @pytest.mark.asyncio
    async def test_invoke_stream_not_found(self):
        mgr = self.make_manager()
        request = SubagentInvocationRequest(subagent_id="ghost", message="x")
        events = []
        async for evt in mgr.invoke_stream("ghost", request):
            events.append(evt)
        assert events[0].event_type == SubagentEventType.SUBAGENT_ERROR
        assert events[0].error_code == SubagentErrorCode.SUBAGENT_NOT_FOUND.value

    @pytest.mark.asyncio
    async def test_cleanup(self):
        mgr = self.make_manager()
        mgr.register(SubagentProvider(MinimalRuntime))
        # Instantiate the runtime
        provider = mgr.get_provider("minimal")
        await provider.get_runtime()
        # Cleanup should shutdown
        await mgr.cleanup()
        # Provider's instance should be None after cleanup
        assert provider._instance is None

    @pytest.mark.asyncio
    async def test_cancel_returns_false_by_default(self):
        mgr = self.make_manager()
        mgr.register(SubagentProvider(MinimalRuntime))
        result = await mgr.cancel("req-1", "minimal")
        assert result is False  # MinimalRuntime doesn't support cancel


# ---------------------------------------------------------------------------
# SubagentLoader Tests
# ---------------------------------------------------------------------------


class TestSubagentLoader:
    def test_discover_from_config_empty(self):
        results = SubagentLoader.discover_from_config({})
        assert results == []

    def test_discover_from_config_module(self):
        # Use the test module itself as the config-discovered module
        config = {"subagent_modules": ["tests.core.test_subagent_core"]}
        results = SubagentLoader.discover_from_config(config)
        # MinimalRuntime, FailingRuntime, UnhealthyRuntime should be discovered
        class_names = {cls.__name__ for cls in results}
        assert "MinimalRuntime" in class_names
        assert "FailingRuntime" in class_names

    def test_discover_from_config_bad_module(self):
        config = {"subagent_modules": ["nonexistent.module.path"]}
        # Should not raise, just log warning
        results = SubagentLoader.discover_from_config(config)
        assert results == []

    def test_discover_via_entry_points_no_group(self):
        # With no registered entry points for noesium.subagents, should return empty list
        results = SubagentLoader.discover_subagents()
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# BaseSubagentRuntime Tests
# ---------------------------------------------------------------------------


class TestBaseSubagentRuntime:
    @pytest.mark.asyncio
    async def test_initialize_sets_context(self):
        runtime = MinimalRuntime()
        ctx = SubagentContext(session_id="s", parent_id="p")
        await runtime.initialize(ctx)
        assert runtime._context is ctx
        assert runtime._initialized is True

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self):
        runtime = MinimalRuntime()
        ctx = SubagentContext(session_id="s", parent_id="p")
        await runtime.initialize(ctx)
        await runtime.shutdown()
        assert runtime._initialized is False
        assert runtime._context is None

    @pytest.mark.asyncio
    async def test_invoke_uses_execute_stream(self):
        runtime = MinimalRuntime()
        request = SubagentInvocationRequest(subagent_id="minimal", message="hello")
        result = await runtime.invoke(request)
        assert result.success is True
        assert "hello" in result.final_text

    @pytest.mark.asyncio
    async def test_cancel_returns_false(self):
        runtime = MinimalRuntime()
        result = await runtime.cancel("req-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_raises_not_implemented(self):
        runtime = MinimalRuntime()
        with pytest.raises(NotImplementedError):
            async for _ in runtime.resume("req-1", "input"):
                pass

    @pytest.mark.asyncio
    async def test_invoke_handles_error_event(self):
        runtime = FailingRuntime()
        request = SubagentInvocationRequest(subagent_id="failing", message="fail")
        # invoke_stream wraps execute, which raises after yielding start
        # The manager normally handles this; at runtime level it propagates
        events = []
        try:
            async for evt in runtime.invoke_stream(request):
                events.append(evt)
        except RuntimeError:
            pass
        # At least START was yielded before the exception
        assert any(e.event_type == SubagentEventType.SUBAGENT_START for e in events)
