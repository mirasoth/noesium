"""
Tests for WizSearchToolkit functionality.
"""

from unittest.mock import AsyncMock, patch

import pytest

from noesium.core.toolify import ToolkitConfig, get_toolkit


@pytest.fixture
def wizsearch_config():
    """Create a test configuration for WizSearchToolkit."""
    return ToolkitConfig(
        name="wizsearch",
        config={
            "enabled_engines": ["tavily", "duckduckgo"],
            "max_results_per_engine": 5,
            "search_timeout": 20,
            "content_format": "markdown",
        },
    )


@pytest.fixture
def wizsearch_toolkit(wizsearch_config):
    """Create WizSearchToolkit instance for testing."""
    try:
        return get_toolkit("wizsearch", wizsearch_config)
    except KeyError as e:
        if "wizsearch" in str(e):
            pytest.skip("WizSearchToolkit not available for testing")
        raise


class TestWizSearchToolkit:
    """Test cases for WizSearchToolkit."""

    @pytest.mark.asyncio
    async def test_toolkit_initialization(self, wizsearch_toolkit):
        """Test that WizSearchToolkit initializes correctly."""
        assert wizsearch_toolkit is not None
        assert hasattr(wizsearch_toolkit, "web_search")
        assert hasattr(wizsearch_toolkit, "tavily_search")
        assert hasattr(wizsearch_toolkit, "google_ai_search")
        assert hasattr(wizsearch_toolkit, "crawl_page")

    @pytest.mark.asyncio
    async def test_toolkit_config_defaults(self, wizsearch_toolkit):
        """Test that configuration values are read correctly."""
        assert wizsearch_toolkit.enabled_engines == ["tavily", "duckduckgo"]
        assert wizsearch_toolkit.max_results_per_engine == 5
        assert wizsearch_toolkit.search_timeout == 20
        assert wizsearch_toolkit.content_format == "markdown"

    @pytest.mark.asyncio
    async def test_get_tools_map(self, wizsearch_toolkit):
        """Test that tools map is correctly defined."""
        tools_map = await wizsearch_toolkit.get_tools_map()

        expected_tools = ["web_search", "tavily_search", "google_ai_search", "crawl_page"]
        for tool_name in expected_tools:
            assert tool_name in tools_map
            assert callable(tools_map[tool_name])

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.WizSearch")
    @patch("noesium.toolkits.wizsearch_toolkit.WizSearchConfig")
    async def test_web_search_success(self, mock_config_cls, mock_wiz_cls, wizsearch_toolkit):
        """Test successful multi-engine web search."""
        from unittest.mock import MagicMock

        from wizsearch import SearchResult, SourceItem

        mock_sources = [
            SourceItem(title="Result 1", url="https://example1.com", content="Content 1"),
            SourceItem(title="Result 2", url="https://example2.com", content="Content 2"),
        ]
        mock_result = SearchResult(query="test query", sources=mock_sources, answer="Combined answer")

        mock_instance = MagicMock()
        mock_instance.search = AsyncMock(return_value=mock_result)
        mock_instance.get_enabled_engines.return_value = ["tavily", "duckduckgo"]
        mock_wiz_cls.return_value = mock_instance

        result = await wizsearch_toolkit.web_search("test query")

        assert isinstance(result, SearchResult)
        assert result.query == "test query"
        assert len(result.sources) == 2
        mock_instance.search.assert_called_once_with(query="test query")

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.WizSearch")
    @patch("noesium.toolkits.wizsearch_toolkit.WizSearchConfig")
    async def test_web_search_with_custom_engines(self, mock_config_cls, mock_wiz_cls, wizsearch_toolkit):
        """Test web search with overridden engine list."""
        from unittest.mock import MagicMock

        from wizsearch import SearchResult

        mock_instance = MagicMock()
        mock_instance.search = AsyncMock(return_value=SearchResult(query="test", sources=[]))
        mock_instance.get_enabled_engines.return_value = ["brave"]
        mock_wiz_cls.return_value = mock_instance

        await wizsearch_toolkit.web_search("test", engines=["brave"])

        mock_config_cls.assert_called_once_with(
            enabled_engines=["brave"],
            max_results_per_engine=5,
            timeout=20,
            fail_silently=True,
        )

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.TavilySearch")
    @patch("noesium.toolkits.wizsearch_toolkit.TavilySearchConfig")
    async def test_tavily_search_success(self, mock_config_cls, mock_tavily_cls, wizsearch_toolkit):
        """Test successful Tavily search."""
        from wizsearch import SearchResult, SourceItem

        mock_sources = [
            SourceItem(title="Tavily Result 1", url="https://example1.com", content="Content 1"),
            SourceItem(title="Tavily Result 2", url="https://example2.com", content="Content 2"),
        ]
        mock_result = SearchResult(query="test query", sources=mock_sources, answer="AI answer")

        mock_instance = AsyncMock()
        mock_instance.search = AsyncMock(return_value=mock_result)
        mock_tavily_cls.return_value = mock_instance

        result = await wizsearch_toolkit.tavily_search(
            "test query", max_results=5, search_depth="advanced", include_answer=True
        )

        assert isinstance(result, SearchResult)
        assert result.query == "test query"
        assert len(result.sources) == 2
        assert result.answer == "AI answer"

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.TavilySearch")
    @patch("noesium.toolkits.wizsearch_toolkit.TavilySearchConfig")
    async def test_tavily_search_generates_summary_without_answer(
        self, mock_config_cls, mock_tavily_cls, wizsearch_toolkit
    ):
        """Test Tavily search generates a summary when no AI answer is provided."""
        from wizsearch import SearchResult, SourceItem

        mock_sources = [
            SourceItem(title="Result A", url="https://a.com", content="A"),
        ]
        mock_result = SearchResult(query="test", sources=mock_sources, answer=None)

        mock_instance = AsyncMock()
        mock_instance.search = AsyncMock(return_value=mock_result)
        mock_tavily_cls.return_value = mock_instance

        result = await wizsearch_toolkit.tavily_search("test", include_answer=False)

        assert result.answer is not None
        assert "Found 1 results" in result.answer

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.TavilySearch")
    @patch("noesium.toolkits.wizsearch_toolkit.TavilySearchConfig")
    async def test_tavily_search_error(self, mock_config_cls, mock_tavily_cls, wizsearch_toolkit):
        """Test Tavily search error propagation."""
        mock_tavily_cls.side_effect = Exception("Tavily API error")

        with pytest.raises(Exception, match="Tavily API error"):
            await wizsearch_toolkit.tavily_search("test query")

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.GoogleAISearch")
    async def test_google_ai_search_success(self, mock_google_cls, wizsearch_toolkit):
        """Test successful Google AI search."""
        from wizsearch import SearchResult, SourceItem

        mock_sources = [SourceItem(title="AI Paper", url="https://arxiv.org/paper1", content="Research content")]
        mock_result = SearchResult(
            query="AI research",
            sources=mock_sources,
            answer="AI research is advancing rapidly.",
        )

        mock_instance = AsyncMock()
        mock_instance.search = AsyncMock(return_value=mock_result)
        mock_google_cls.return_value = mock_instance

        result = await wizsearch_toolkit.google_ai_search("AI research", model="gemini-2.5-flash", temperature=0.0)

        assert isinstance(result, SearchResult)
        assert result.query == "AI research"
        assert len(result.sources) == 1
        mock_instance.search.assert_called_once_with(query="AI research", model="gemini-2.5-flash", temperature=0.0)

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.GoogleAISearch")
    async def test_google_ai_search_error(self, mock_google_cls, wizsearch_toolkit):
        """Test Google AI search error propagation."""
        mock_google_cls.side_effect = Exception("Google AI API error")

        with pytest.raises(Exception, match="Google AI API error"):
            await wizsearch_toolkit.google_ai_search("test query")

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.PageCrawler")
    async def test_crawl_page_success(self, mock_crawler_cls, wizsearch_toolkit):
        """Test successful page crawling."""
        mock_instance = AsyncMock()
        mock_instance.crawl = AsyncMock(return_value="# Page Title\n\nPage content here.")
        mock_crawler_cls.return_value = mock_instance

        result = await wizsearch_toolkit.crawl_page("https://example.com")

        assert isinstance(result, str)
        assert "Page Title" in result
        mock_crawler_cls.assert_called_once_with(url="https://example.com", content_format="markdown", only_text=False)

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.PageCrawler")
    async def test_crawl_page_custom_format(self, mock_crawler_cls, wizsearch_toolkit):
        """Test page crawling with custom content format."""
        mock_instance = AsyncMock()
        mock_instance.crawl = AsyncMock(return_value="<p>HTML content</p>")
        mock_crawler_cls.return_value = mock_instance

        result = await wizsearch_toolkit.crawl_page("https://example.com", content_format="html", only_text=True)

        assert isinstance(result, str)
        mock_crawler_cls.assert_called_once_with(url="https://example.com", content_format="html", only_text=True)

    @pytest.mark.asyncio
    @patch("noesium.toolkits.wizsearch_toolkit.PageCrawler")
    async def test_crawl_page_empty_result(self, mock_crawler_cls, wizsearch_toolkit):
        """Test page crawling that returns empty content."""
        mock_instance = AsyncMock()
        mock_instance.crawl = AsyncMock(return_value="")
        mock_crawler_cls.return_value = mock_instance

        result = await wizsearch_toolkit.crawl_page("https://example.com")

        assert result == ""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("search_depth", ["basic", "advanced"])
    @patch("noesium.toolkits.wizsearch_toolkit.TavilySearch")
    @patch("noesium.toolkits.wizsearch_toolkit.TavilySearchConfig")
    async def test_tavily_search_depth_options(self, mock_config_cls, mock_tavily_cls, search_depth, wizsearch_toolkit):
        """Test Tavily search with different depth options."""
        from wizsearch import SearchResult

        mock_instance = AsyncMock()
        mock_instance.search = AsyncMock(return_value=SearchResult(query="test", sources=[]))
        mock_tavily_cls.return_value = mock_instance

        await wizsearch_toolkit.tavily_search("test", search_depth=search_depth)

        mock_config_cls.assert_called_once()
        call_kwargs = mock_config_cls.call_args[1]
        assert call_kwargs["search_depth"] == search_depth

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", ["gemini-2.5-flash", "gemini-2.0-flash-exp"])
    @patch("noesium.toolkits.wizsearch_toolkit.GoogleAISearch")
    async def test_google_ai_search_model_options(self, mock_google_cls, model, wizsearch_toolkit):
        """Test Google AI search with different model options."""
        from wizsearch import SearchResult

        mock_instance = AsyncMock()
        mock_instance.search = AsyncMock(return_value=SearchResult(query="test", sources=[]))
        mock_google_cls.return_value = mock_instance

        await wizsearch_toolkit.google_ai_search("test", model=model)

        mock_instance.search.assert_called_once_with(query="test", model=model, temperature=0.0)


class TestWizSearchToolkitIntegration:
    """Integration tests for WizSearchToolkit (require running search engines)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_web_search(self):
        """Test with real multi-engine search."""
        config = ToolkitConfig(
            name="wizsearch",
            config={"enabled_engines": ["duckduckgo"], "max_results_per_engine": 3},
        )
        toolkit = get_toolkit("wizsearch", config)

        result = await toolkit.web_search("Python programming language")

        assert result is not None
        assert result.query == "Python programming language"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_crawl_page(self):
        """Test with real page crawling."""
        config = ToolkitConfig(name="wizsearch", config={})
        toolkit = get_toolkit("wizsearch", config)

        result = await toolkit.crawl_page("https://docs.python.org/3/")

        assert isinstance(result, str)
