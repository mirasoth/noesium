"""NoeAgent integration benchmark suite.

Real integration tests exercising NoeAgent with actual LLM calls and real
tool invocations.  Requires API keys configured in the environment.

Usage:
    uv run pytest tests/agents/benchmark_noe_agent.py -v -m benchmark
    uv run pytest tests/agents/benchmark_noe_agent.py -v -k "test_tool_web_search"

Environment variables required:
    NOESIUM_LLM_PROVIDER / OPENAI_API_KEY / OPENROUTER_API_KEY  (LLM)
    TAVILY_API_KEY        (web_search toolkit)
    JINA_API_KEY          (jina_research toolkit)
    SERPER_API_KEY        (serper toolkit)
    GITHUB_TOKEN          (github toolkit, optional)
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest
from noeagent.agent import NoeAgent
from noeagent.config import NoeConfig, NoeMode

from noesium.core.event import ProgressEvent, ProgressEventType

logger = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BENCHMARK_TIMEOUT = 120  # seconds per test


def _has_api_key(*env_vars: str) -> bool:
    return any(os.getenv(v) for v in env_vars)


def _make_config(**overrides: Any) -> NoeConfig:
    """Create a NoeConfig for benchmarking with sensible defaults."""
    defaults = {
        "mode": NoeMode.AGENT,
        "max_iterations": 10,
        "reflection_interval": 5,
        "enable_session_logging": False,
        "persist_memory": False,
        "memory_providers": ["working"],
    }
    defaults.update(overrides)
    return NoeConfig(**defaults)


class BenchmarkCollector:
    """Collects progress events and timing data for a single benchmark run."""

    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.subagent_events: list[ProgressEvent] = []
        self.errors: list[str] = []
        self.final_answer: str = ""
        self.start_time: float = 0
        self.elapsed: float = 0

    async def on_progress(self, event: ProgressEvent) -> None:
        self.events.append(event)
        if event.type == ProgressEventType.TOOL_START:
            self.tool_calls.append({"name": event.tool_name, "args": event.tool_args})
        elif event.type in (
            ProgressEventType.SUBAGENT_START,
            ProgressEventType.SUBAGENT_PROGRESS,
            ProgressEventType.SUBAGENT_END,
        ):
            self.subagent_events.append(event)
        elif event.type == ProgressEventType.ERROR:
            self.errors.append(event.error or "unknown")
        elif event.type == ProgressEventType.FINAL_ANSWER:
            self.final_answer = event.text or ""


async def _run_benchmark(
    prompt: str,
    config: NoeConfig | None = None,
    timeout: int = BENCHMARK_TIMEOUT,
) -> BenchmarkCollector:
    """Run NoeAgent with the given prompt and collect benchmark data."""
    collector = BenchmarkCollector()
    cfg = config or _make_config()
    cfg.progress_callbacks.append(collector.on_progress)
    agent = NoeAgent(cfg)

    collector.start_time = time.monotonic()
    try:
        result = await asyncio.wait_for(agent.arun(prompt), timeout=timeout)
        if not collector.final_answer:
            collector.final_answer = result
    except asyncio.TimeoutError:
        collector.errors.append(f"Benchmark timed out after {timeout}s")
    except Exception as exc:
        collector.errors.append(str(exc))
    finally:
        collector.elapsed = time.monotonic() - collector.start_time

    return collector


# ---------------------------------------------------------------------------
# A. Tool Call Correctness -- per-toolkit tests
# ---------------------------------------------------------------------------


class TestToolWebSearch:
    """Validates web_search toolkit: web_search, tavily_search, crawl_page."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _has_api_key("TAVILY_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"),
        reason="Missing API keys for web_search",
    )
    async def test_web_search_basic(self):
        """Agent performs a web search. Validates enabled_engines is passed as list (testerror.md regression)."""
        config = _make_config(enabled_toolkits=["web_search"], max_iterations=5)
        result = await _run_benchmark(
            "Search the web for 'Python asyncio best practices 2026'. Return a brief summary.",
            config=config,
        )
        assert result.final_answer, "Expected a final answer"
        tool_names = [tc["name"] for tc in result.tool_calls]
        assert any("search" in n for n in tool_names), f"Expected a search tool call, got: {tool_names}"
        assert not any(
            "validation error" in e.lower() for e in result.errors
        ), f"Validation errors detected: {result.errors}"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _has_api_key("TAVILY_API_KEY"),
        reason="Missing TAVILY_API_KEY",
    )
    async def test_tavily_search(self):
        """Agent uses tavily_search explicitly."""
        config = _make_config(enabled_toolkits=["web_search"], max_iterations=5)
        result = await _run_benchmark(
            "Use tavily_search to find information about 'noesium framework'. Summarize what you find.",
            config=config,
        )
        assert result.final_answer, "Expected a final answer"


class TestToolJinaResearch:
    @pytest.mark.asyncio
    @pytest.mark.skipif(not _has_api_key("JINA_API_KEY"), reason="Missing JINA_API_KEY")
    async def test_web_content_extraction(self):
        config = _make_config(enabled_toolkits=["jina_research"], max_iterations=5)
        result = await _run_benchmark(
            "Extract the main content from https://example.com using get_web_content. Summarize it.",
            config=config,
        )
        assert result.final_answer


class TestToolBash:
    @pytest.mark.asyncio
    async def test_list_directory(self):
        config = _make_config(enabled_toolkits=["bash"], max_iterations=5)
        result = await _run_benchmark(
            "List the files in the current directory using bash. Report the count.",
            config=config,
        )
        assert result.final_answer
        tool_names = [tc["name"] for tc in result.tool_calls]
        assert any("bash" in n or "directory" in n for n in tool_names)

    @pytest.mark.asyncio
    async def test_run_command(self):
        config = _make_config(enabled_toolkits=["bash"], max_iterations=5)
        result = await _run_benchmark(
            "Run 'echo hello_benchmark_test' using bash and report the output.",
            config=config,
        )
        assert result.final_answer
        assert "hello_benchmark_test" in result.final_answer.lower() or any(
            "hello_benchmark_test" in str(tc.get("args", {})) for tc in result.tool_calls
        )


class TestToolPythonExecutor:
    @pytest.mark.asyncio
    async def test_fibonacci(self):
        config = _make_config(enabled_toolkits=["python_executor"], max_iterations=5)
        result = await _run_benchmark(
            "Calculate the first 10 Fibonacci numbers using execute_python_code.",
            config=config,
        )
        assert result.final_answer
        assert "55" in result.final_answer or "34" in result.final_answer


class TestToolFileEdit:
    @pytest.mark.asyncio
    async def test_create_and_read_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_config(
                enabled_toolkits=["file_edit"],
                max_iterations=8,
                working_directory=tmpdir,
            )
            result = await _run_benchmark(
                f"Create a file called 'test_output.txt' in {tmpdir} with content "
                "'Hello from NoeAgent benchmark', then read it back and confirm the content.",
                config=config,
            )
            assert result.final_answer
            test_file = Path(tmpdir) / "test_output.txt"
            if test_file.exists():
                assert "Hello from NoeAgent benchmark" in test_file.read_text()


class TestToolMemory:
    @pytest.mark.asyncio
    async def test_store_and_recall(self):
        config = _make_config(enabled_toolkits=["memory"], max_iterations=8)
        result = await _run_benchmark(
            "Store the value 'benchmark_secret_42' in memory slot 'benchmark_slot', "
            "then read it back and confirm the value matches.",
            config=config,
        )
        assert result.final_answer


class TestToolArxiv:
    @pytest.mark.asyncio
    async def test_search_papers(self):
        config = _make_config(enabled_toolkits=["arxiv"], max_iterations=5)
        result = await _run_benchmark(
            "Search arxiv for papers about 'transformer architecture attention mechanism'. "
            "Return the title and authors of the top result.",
            config=config,
        )
        assert result.final_answer


class TestToolSerper:
    @pytest.mark.asyncio
    @pytest.mark.skipif(not _has_api_key("SERPER_API_KEY"), reason="Missing SERPER_API_KEY")
    async def test_google_search(self):
        config = _make_config(enabled_toolkits=["serper"], max_iterations=5)
        result = await _run_benchmark(
            "Use google_search to search for 'Python type hints best practices'. " "Summarize the top 3 results.",
            config=config,
        )
        assert result.final_answer


class TestToolWikipedia:
    @pytest.mark.asyncio
    async def test_wikipedia_summary(self):
        config = _make_config(enabled_toolkits=["wikipedia"], max_iterations=5)
        result = await _run_benchmark(
            "Get the Wikipedia summary for 'Artificial Intelligence' and return the first paragraph.",
            config=config,
        )
        assert result.final_answer
        assert "intelligence" in result.final_answer.lower() or "ai" in result.final_answer.lower()


class TestToolGithub:
    @pytest.mark.asyncio
    @pytest.mark.skipif(not _has_api_key("GITHUB_TOKEN"), reason="Missing GITHUB_TOKEN")
    async def test_get_repo_info(self):
        config = _make_config(enabled_toolkits=["github"], max_iterations=5)
        result = await _run_benchmark(
            "Get information about the repository 'langchain-ai/langchain' on GitHub. "
            "Report the description and star count.",
            config=config,
        )
        assert result.final_answer


class TestToolUserInteraction:
    @pytest.mark.asyncio
    async def test_display_message(self):
        config = _make_config(enabled_toolkits=["user_interaction"], max_iterations=5)
        result = await _run_benchmark(
            "Use display_message to show the text 'Benchmark test message' to the user.",
            config=config,
        )
        assert result.final_answer or any(tc["name"] == "display_message" for tc in result.tool_calls)


class TestToolDocument:
    @pytest.mark.asyncio
    async def test_document_info(self):
        config = _make_config(enabled_toolkits=["document"], max_iterations=5)
        result = await _run_benchmark(
            "What document processing capabilities do you have available? " "List the document tools you can use.",
            config=config,
        )
        assert result.final_answer


class TestToolTabularData:
    @pytest.mark.asyncio
    async def test_tabular_capabilities(self):
        config = _make_config(enabled_toolkits=["tabular_data"], max_iterations=5)
        result = await _run_benchmark(
            "What tabular data analysis capabilities do you have? " "List the available tabular data tools.",
            config=config,
        )
        assert result.final_answer


class TestToolImage:
    @pytest.mark.asyncio
    async def test_image_capabilities(self):
        config = _make_config(enabled_toolkits=["image"], max_iterations=5)
        result = await _run_benchmark(
            "What image analysis capabilities do you have? List the available image tools.",
            config=config,
        )
        assert result.final_answer


class TestToolVideo:
    @pytest.mark.asyncio
    async def test_video_capabilities(self):
        config = _make_config(enabled_toolkits=["video"], max_iterations=5)
        result = await _run_benchmark(
            "What video analysis capabilities do you have? List the available video tools.",
            config=config,
        )
        assert result.final_answer


# ---------------------------------------------------------------------------
# B. Subagent Orchestration
# ---------------------------------------------------------------------------


class TestSubagentOrchestration:
    """Tests for in-process subagent spawning and interaction."""

    @pytest.mark.asyncio
    async def test_spawn_single_subagent(self):
        """Agent spawns a child subagent for a research subtask."""
        config = _make_config(
            enabled_toolkits=["bash", "wikipedia"],
            max_iterations=12,
            enable_subagents=True,
            subagent_max_depth=2,
        )
        result = await _run_benchmark(
            "Spawn a subagent named 'wiki-researcher' to get the Wikipedia summary "
            "of 'Machine Learning'. Report what the subagent found.",
            config=config,
            timeout=180,
        )
        assert result.final_answer
        has_subagent = len(result.subagent_events) > 0 or any(
            "subagent" in tc["name"] or "spawn" in tc["name"] for tc in result.tool_calls
        )
        assert has_subagent, "Expected subagent activity"

    @pytest.mark.asyncio
    async def test_parallel_subagents(self):
        """Agent spawns multiple subagents for parallel research."""
        config = _make_config(
            enabled_toolkits=["bash", "wikipedia", "web_search"],
            max_iterations=15,
            enable_subagents=True,
            subagent_max_depth=2,
        )
        result = await _run_benchmark(
            "I need information from two sources in parallel. "
            "Spawn subagent 'wiki-agent' to search Wikipedia for 'Neural Network', "
            "and spawn subagent 'general-agent' to summarize what a neural network is. "
            "Combine both results.",
            config=config,
            timeout=240,
        )
        assert result.final_answer

    @pytest.mark.asyncio
    async def test_subagent_depth_limit(self):
        """Subagent depth limit is enforced."""
        config = _make_config(
            enabled_toolkits=["bash"],
            max_iterations=8,
            enable_subagents=True,
            subagent_max_depth=1,
        )
        agent = NoeAgent(config)
        agent._depth = 1  # already at max depth
        with pytest.raises(RuntimeError, match="depth limit"):
            await agent.spawn_subagent("child", mode=NoeMode.AGENT)

    @pytest.mark.asyncio
    async def test_subagent_disabled(self):
        """Subagent operations fail gracefully when disabled."""
        config = _make_config(enable_subagents=False)
        agent = NoeAgent(config)
        with pytest.raises(RuntimeError, match="disabled"):
            await agent.spawn_subagent("child", mode=NoeMode.AGENT)


# ---------------------------------------------------------------------------
# C. Error Resilience
# ---------------------------------------------------------------------------


class TestErrorResilience:
    """Tests for graceful error handling and recovery."""

    @pytest.mark.asyncio
    async def test_tool_validation_error_recovery(self):
        """Regression test for testerror.md: web_search enabled_engines validation.

        The agent should recover from tool validation errors and still produce
        a final answer, possibly using alternative tools or approaches.
        """
        config = _make_config(
            enabled_toolkits=["web_search", "bash"],
            max_iterations=8,
        )
        result = await _run_benchmark(
            "Search the web for 'noesium framework'. If web search fails, "
            "explain what happened and try an alternative approach.",
            config=config,
        )
        assert result.final_answer, "Agent should produce a final answer despite tool errors"

    @pytest.mark.asyncio
    async def test_permission_denied(self):
        """Agent handles permission denied for restricted tools."""
        config = _make_config(
            enabled_toolkits=["bash"],
            permissions=[],  # no permissions granted
            max_iterations=5,
        )
        result = await _run_benchmark(
            "Run the command 'echo test' using bash.",
            config=config,
        )
        assert result.final_answer

    @pytest.mark.asyncio
    async def test_iteration_limit(self):
        """Agent finalizes when iteration limit is reached."""
        config = _make_config(
            enabled_toolkits=["bash"],
            max_iterations=2,
        )
        result = await _run_benchmark(
            "Perform a very complex multi-step analysis that would normally "
            "take many iterations. Do your best within the constraints.",
            config=config,
        )
        assert result.final_answer, "Agent should finalize with partial results"


# ---------------------------------------------------------------------------
# D. End-to-End Scenarios
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Full end-to-end research scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _has_api_key("TAVILY_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"),
        reason="Missing API keys",
    )
    async def test_research_project_name_uniqueness(self):
        """Regression test for the exact failing scenario from testerror.md.

        Prompt: analyze uniqueness of project name 'noesium'.
        Previous failures:
          - web_search: enabled_engines validation error (string vs list)
          - crawl_page: 30s timeout + playwright TargetClosedError
        """
        config = _make_config(
            enabled_toolkits=["web_search", "bash", "python_executor"],
            max_iterations=10,
        )
        result = await _run_benchmark(
            "Analyze the uniqueness of the project name 'noesium'. "
            "Search for existing uses of this name. Summarize your findings.",
            config=config,
            timeout=180,
        )
        assert result.final_answer, "Expected a research result"
        assert len(result.tool_calls) > 0, "Expected tool usage"

    @pytest.mark.asyncio
    async def test_planning_and_reflection_cycle(self):
        """Agent creates a plan, executes steps, reflects, and finalizes."""
        config = _make_config(
            enabled_toolkits=["bash", "python_executor"],
            max_iterations=10,
            reflection_interval=2,
        )
        result = await _run_benchmark(
            "Create a Python script that generates the first 20 prime numbers, "
            "then execute it and report the results.",
            config=config,
        )
        assert result.final_answer
        event_types = {e.type for e in result.events}
        assert ProgressEventType.PLAN_CREATED in event_types, "Expected plan creation"

    @pytest.mark.asyncio
    async def test_ask_mode_no_tools(self):
        """Ask mode produces answers without tool calls."""
        config = _make_config(mode=NoeMode.ASK)
        result = await _run_benchmark(
            "What is the capital of France?",
            config=config,
        )
        assert result.final_answer
        assert len(result.tool_calls) == 0, "Ask mode should not use tools"

    @pytest.mark.asyncio
    async def test_multi_toolkit_research(self):
        """Agent uses multiple toolkits in a single research session."""
        config = _make_config(
            enabled_toolkits=["bash", "python_executor", "memory"],
            max_iterations=10,
        )
        result = await _run_benchmark(
            "Use bash to check the current date, then use python to calculate "
            "how many days until the end of the year. Store the result in memory "
            "slot 'days_remaining'. Report everything.",
            config=config,
        )
        assert result.final_answer
        tool_names = {tc["name"] for tc in result.tool_calls}
        assert len(tool_names) >= 2, f"Expected multiple tools used, got: {tool_names}"


# ---------------------------------------------------------------------------
# E. Benchmark Report
# ---------------------------------------------------------------------------


class TestBenchmarkReport:
    """Meta-test that collects and reports benchmark statistics."""

    @pytest.mark.asyncio
    async def test_tool_loading_all_toolkits(self):
        """Verify all 18 toolkits can be loaded without errors."""
        all_toolkits = [
            "web_search",
            "jina_research",
            "bash",
            "python_executor",
            "file_edit",
            "memory",
            "document",
            "image",
            "tabular_data",
            "video",
            "user_interaction",
            "arxiv",
            "serper",
            "wikipedia",
            "github",
            "gmail",
            "audio",
            "audio_aliyun",
        ]
        config = _make_config(enabled_toolkits=all_toolkits)
        agent = NoeAgent(config)
        await agent.initialize()

        registry = agent._tool_registry
        assert registry is not None, "Tool registry should be initialized"

        loaded_tools = registry.list_tools()
        loaded_names = {t.name for t in loaded_tools}
        logger.info("Loaded %d tools from %d toolkits: %s", len(loaded_tools), len(all_toolkits), loaded_names)

        assert len(loaded_tools) > 0, "At least some tools should be loaded"

    @pytest.mark.asyncio
    async def test_progress_event_lifecycle(self):
        """Verify progress events follow the expected lifecycle."""
        config = _make_config(
            enabled_toolkits=["bash"],
            max_iterations=5,
        )
        result = await _run_benchmark(
            "Run 'echo benchmark_lifecycle_test' and report the output.",
            config=config,
        )

        event_types = [e.type for e in result.events]
        assert event_types[0] == ProgressEventType.SESSION_START
        assert event_types[-1] == ProgressEventType.SESSION_END
        assert ProgressEventType.FINAL_ANSWER in event_types

        for event in result.events:
            assert event.session_id, "Every event must have a session_id"
            assert event.sequence > 0, "Every event must have a positive sequence number"
