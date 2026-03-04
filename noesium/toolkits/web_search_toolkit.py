"""
Web Search toolkit for multi-engine web search and page crawling.

Wraps the wizsearch library to provide unified search across multiple engines
(Tavily, DuckDuckGo, Google AI, Brave, Bing, etc.) and web page content extraction.

Engine-specific API keys (e.g. Tavily) are read from toolkit config or environment.
Set TAVILY_API_KEY in config or env for Tavily to work; otherwise Tavily may fail
silently and only other engines (e.g. DuckDuckGo) return results.
"""

import os
from typing import Any, Callable, Dict, List, Optional

try:
    from wizsearch import (
        GoogleAISearch,
        PageCrawler,
        SearchResult,
        TavilySearch,
        TavilySearchConfig,
        WizSearch,
        WizSearchConfig,
    )

    WIZSEARCH_AVAILABLE = True
except ImportError:
    GoogleAISearch = None
    PageCrawler = None
    SearchResult = None
    TavilySearch = None
    TavilySearchConfig = None
    WizSearch = None
    WizSearchConfig = None
    WIZSEARCH_AVAILABLE = False

from noesium.core.library_consts import TOOLKIT_WEB_SEARCH
from noesium.core.toolify.base import AsyncBaseToolkit
from noesium.core.toolify.config import ToolkitConfig
from noesium.core.toolify.registry import register_toolkit
from noesium.core.utils.logging import get_logger

logger = get_logger(__name__)


def _require_wizsearch():
    if not WIZSEARCH_AVAILABLE:
        raise ImportError("wizsearch package is not installed. Install it with: pip install 'noesium[tools]'")


def _normalize_engine_list(value: Optional[List[str]], default: List[str]) -> List[str]:
    """Ensure enabled_engines is a list of strings. Accepts list or comma-separated string (e.g. from config or LLM)."""
    if value is None:
        return default
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return default


def _apply_tavily_api_key_from_config(config: dict) -> None:
    """Set TAVILY_API_KEY in environment from toolkit config if not already set.

    The wizsearch library uses LangchainTavilySearch, which only reads TAVILY_API_KEY
    from the environment. Without it, Tavily fails and (with fail_silently=True)
    only other engines return results.
    """
    if os.environ.get("TAVILY_API_KEY"):
        return
    key = config.get("TAVILY_API_KEY") or config.get("tavily_api_key")
    if isinstance(key, str) and key.strip():
        os.environ["TAVILY_API_KEY"] = key.strip()


@register_toolkit(TOOLKIT_WEB_SEARCH)
class WebSearchToolkit(AsyncBaseToolkit):
    """
    Toolkit for multi-engine web search and page crawling via the wizsearch library.

    Provides:
    - Multi-engine concurrent search (WizSearch)
    - Tavily search with AI summaries
    - Google AI grounded search with citations
    - Web page content crawling via Crawl4AI

    Configuration keys (via ToolkitConfig.config):
    - enabled_engines: list of engine names (default: ["tavily"])
    - max_results_per_engine: int (default: 10)
    - search_timeout: int seconds (default: 30)
    - content_format: "markdown" | "html" | "text" (default: "markdown")
    - TAVILY_API_KEY or tavily_api_key: Tavily API key (optional; can also set env TAVILY_API_KEY)
    """

    def __init__(self, config: ToolkitConfig = None):
        super().__init__(config)

        self.enabled_engines: List[str] = _normalize_engine_list(self.config.config.get("enabled_engines"), ["tavily"])
        self.max_results_per_engine: int = self.config.config.get("max_results_per_engine", 10)
        self.search_timeout: int = self.config.config.get("search_timeout", 30)
        self.content_format: str = self.config.config.get("content_format", "markdown")

    async def web_search(
        self,
        query: str,
        engines: Optional[List[str]] = None,
        max_results: Optional[int] = None,
    ) -> SearchResult:
        """
        Search the web across multiple search engines concurrently and return merged results.

        Uses WizSearch to run queries in parallel across configured engines (e.g. Tavily,
        DuckDuckGo, Brave, Google AI) with automatic result deduplication and round-robin
        merging for diverse results.

        Args:
            query: The search query to execute. Be specific and descriptive for better results.
            engines: Override the default engine list for this search.
                     Available engines: tavily, duckduckgo, brave, bing, google, googleai,
                     searxng, baidu, wechat. If None, uses the toolkit's configured engines.
            max_results: Maximum results per engine (default: toolkit config value).

        Returns:
            SearchResult with merged sources from all engines, optional AI answer, and metadata.
        """
        _require_wizsearch()
        _apply_tavily_api_key_from_config(self.config.config)
        self.logger.info(f"Multi-engine web search for: {query}")

        engine_list = _normalize_engine_list(engines, self.enabled_engines)
        wiz_config = WizSearchConfig(
            enabled_engines=engine_list,
            max_results_per_engine=max_results or self.max_results_per_engine,
            timeout=self.search_timeout,
            fail_silently=True,
        )
        wiz = WizSearch(config=wiz_config)
        result = await wiz.search(query=query)

        self.logger.info(
            f"Web search complete: {len(result.sources)} results from " f"{', '.join(wiz.get_enabled_engines())}"
        )
        return result

    async def _web_search_for_agent(
        self,
        query: str,
        max_results: Optional[int] = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Agent-facing web search: uses toolkit-configured engines only (no engines argument).

        This entry point is exposed to the agent so that engine selection is controlled
        solely by config (e.g. enabled_engines in toolkit_configs). With empty config,
        the default is tavily. Any engines passed in kwargs are ignored. The full
        web_search(..., engines=...) remains available for programmatic use.
        """
        return await self.web_search(query=query, engines=None, max_results=max_results)

    async def tavily_search(
        self,
        query: str,
        max_results: Optional[int] = 10,
        search_depth: Optional[str] = "advanced",
        include_answer: Optional[bool] = False,
        include_raw_content: Optional[bool] = False,
    ) -> SearchResult:
        """
        Search the web using Tavily Search API to find relevant information and sources.

        Performs comprehensive web searches with optional AI-powered summaries.
        Ideal for research tasks, fact-checking, and gathering current information.

        Args:
            query: The search query to execute. Be specific and descriptive for better results.
                   Examples: "latest news on AI developments", "best restaurants in Paris 2024"
            max_results: Maximum number of search results to return (1-50).
                        Higher numbers provide more comprehensive coverage but may be slower.
            search_depth: Search depth level - "basic" for quick results or "advanced" for
                         more thorough, comprehensive search with better source quality.
            include_answer: When True, generates an AI-powered summary of the search results.
            include_raw_content: When True, includes the full content of web pages in results.

        Returns:
            SearchResult with sources, optional AI answer, and query metadata.
        """
        _require_wizsearch()
        _apply_tavily_api_key_from_config(self.config.config)
        self.logger.info(f"Tavily search for: {query}")

        tavily_config = TavilySearchConfig(
            max_results=max_results,
            search_depth=search_depth,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
        )
        searcher = TavilySearch(config=tavily_config)
        result = await searcher.search(query=query)

        summary = None
        if include_answer and result.answer:
            summary = result.answer
        elif result.sources:
            top = result.sources[:3]
            summary = (
                f"Found {len(result.sources)} results for '{query}'. "
                f"Top results: {', '.join(repr(s.title) for s in top)}"
            )

        return SearchResult(query=query, sources=result.sources, answer=summary)

    async def google_ai_search(
        self,
        query: str,
        model: Optional[str] = "gemini-2.5-flash",
        temperature: Optional[float] = 0.0,
    ) -> SearchResult:
        """
        Search the web using Google AI Search powered by Gemini models.

        Leverages Google's advanced AI search capabilities to find information,
        generate comprehensive research summaries, and provide detailed citations.
        Particularly effective for academic research, detailed analysis, and
        well-sourced information with proper attribution.

        Args:
            query: The search query. Be specific and detailed for best results.
                   Examples: "climate change impact on agriculture 2024",
                             "machine learning trends in healthcare"
            model: The Gemini model to use.
                   - "gemini-2.5-flash": Fast, efficient (recommended)
                   - "gemini-2.0-flash-exp": Experimental with latest features
            temperature: Controls creativity vs accuracy (0.0-1.0).
                        0.0 is most factual (recommended for research).

        Returns:
            SearchResult with cited sources, comprehensive AI answer, and query metadata.
        """
        _require_wizsearch()
        self.logger.info(f"Google AI search for: {query}")

        google = GoogleAISearch()
        return await google.search(query=query, model=model, temperature=temperature)

    async def crawl_page(
        self,
        url: str,
        content_format: Optional[str] = None,
        only_text: bool = False,
    ) -> str:
        """
        Extract readable content from a web page using Crawl4AI.

        Crawls the specified URL and returns the page content in the requested format.
        Useful for reading full articles, documentation, or any web content that
        a search snippet doesn't fully capture.

        Args:
            url: The URL of the web page to crawl.
            content_format: Output format: "markdown" (default), "html", or "text".
                           If None, uses the toolkit's configured default.
            only_text: When True, extracts only the text content without any markup.

        Returns:
            Extracted page content as a string. Returns empty string if crawling fails.
        """
        _require_wizsearch()
        self.logger.info(f"Crawling page: {url}")

        fmt = content_format or self.content_format
        crawler = PageCrawler(url=url, content_format=fmt, only_text=only_text)
        content = await crawler.crawl()

        self.logger.info(f"Crawled {url}: {len(content)} chars")
        return content

    async def get_tools_map(self) -> Dict[str, Callable]:
        return {
            "web_search": self._web_search_for_agent,
            "tavily_search": self.tavily_search,
            "google_ai_search": self.google_ai_search,
            "crawl_page": self.crawl_page,
        }
