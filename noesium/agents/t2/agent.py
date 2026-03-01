from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel
from wizsearch import SearchResult, WizSearch, WizSearchConfig

from noesium.agents.browser_use import BrowserSession
from noesium.agents.browser_use.agent.service import Agent as BrowserUseServiceAgent
from noesium.agents.browser_use.agent.views import AgentHistoryList, AgentSettings
from noesium.agents.browser_use.browser.events import NavigateToUrlEvent
from noesium.agents.browser_use.browser.profile import BrowserProfile, ProxySettings
from noesium.agents.browser_use.llm_adapter import BaseChatModel
from noesium.core.agent import ResearchOutput
from noesium.core.llm import BaseLLMClient, get_llm_client
from noesium.core.utils.logging import get_logger

logger = get_logger(__name__)

_T2_SEARCH_ENGINES = ["tavily", "duckduckgo"]


class T2Agent:
    def __init__(self, llm: BaseLLMClient | None = None, **kwargs):
        if not llm:
            llm = get_llm_client(structured_output=True)
        self.llm = llm
        self.browser_session: BrowserSession | None = None

    async def search(
        self,
        query: str,
        search_engines: List[str] = _T2_SEARCH_ENGINES,
        max_results_per_engine: int = 5,
        search_timeout: int = 20,
        crawl_conent: bool = True,
        conent_format: str = "markdown",
        adaptive_crawl: bool = False,
        crawl_depth: int = 1,
        crawl_external_links: bool = False,
        reranker_enabled: bool = False,
        reranker_llm: BaseLLMClient | None = None,
        **kwargs,
    ) -> SearchResult:
        """
        Search the query using the WizSearch.

        Args:
            query: The query to search for.
            max_results: The maximum number of results to return.
            crawl_conent: Whether to crawl the page content of SERP links.
            conent_format: The format of the content to return.
            adaptive_crawl: Whether to use adaptive crawling of Crawl4AI (with embedding similarity).
            crawl_depth: The depth of the crawl (leave 1 to disable deep crawling).
            **kwargs: Additional arguments.

        Returns:
            SearchResult: The search result.
        """
        if reranker_enabled:
            self.reranker_llm = reranker_llm if reranker_llm else self.llm

        try:
            config = WizSearchConfig(
                enabled_engines=search_engines, max_results_per_engine=max_results_per_engine, timeout=search_timeout
            )
            wiz_search = WizSearch(config=config)
            result = await wiz_search.search(query)

            if not crawl_conent:
                return result

            return result
        except Exception as e:
            logger.error(f"Failed to search: {e}")
            raise

    async def research(
        self,
        instruction: str,
        search_engines: List[str] = _T2_SEARCH_ENGINES,
        max_results_per_engine: int = 5,
        search_timeout: int = 30,
        **kwargs,
    ) -> ResearchOutput:
        """
        Research the query using Deep Research.

        Args:
            instruction: The query to research.
            search_engines: The search engines to use. Alternatives: tavily, duckduckgo, googleai, searxng, brave, baidu, wechat.
            max_results_per_engine: The maximum number of results per engine.
            search_timeout: The timeout for the search.
            **kwargs: Additional arguments.

        Returns:
            ResearchOutput: The research output.
        """
        try:
            from noesium.agents.tacitus import TacitusAgent

            researcher = TacitusAgent(
                search_engines=search_engines,
                max_results_per_engine=max_results_per_engine,
                search_timeout=search_timeout,
                **kwargs,
            )
            return await researcher.research(user_message=instruction)
        except Exception as e:
            logger.error(f"Failed to research: {e}")
            raise

    async def navigate_and_extract(
        self,
        url: str,
        instruction: str,
        schema: Union[Dict, BaseModel],
        selector: Optional[str] = None,
        headless: bool = True,
        use_vision: bool = False,
        max_failures: int = 3,
        max_actions_per_step: int = 3,
        **kwargs,
    ) -> Union[Dict, BaseModel]:
        """
        Extracts structured data from the page based on a Pydantic-like schema.
        """
        session = None
        try:
            if not self.llm:
                raise ValueError("LLM client is required for data extraction")

            # Launch browser session if not already available
            if not self.browser_session:
                session = await self._launch_browser_session(headless=headless, **kwargs)
            else:
                session = self.browser_session

            # Navigate to the URL first
            event = session.event_bus.dispatch(NavigateToUrlEvent(url=url, timeout_ms=30000))
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)

            # Prepare task instruction
            task_instruction = f"Extract data from the current page: {instruction}"
            if selector:
                task_instruction += f" Focus on elements matching selector: {selector}"

            # Determine output model
            output_model = None
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                output_model = schema
            elif isinstance(schema, dict):
                # Convert dict schema to Pydantic model if needed
                # For now, we'll extract as text and structure it
                pass

            # Create agent for extraction
            agent = BrowserUseServiceAgent(
                task=task_instruction,
                llm=BaseChatModel(self.llm),
                browser=session,
                output_model_schema=output_model,
                settings=AgentSettings(
                    use_vision=use_vision,
                    max_failures=max_failures,
                    max_actions_per_step=max_actions_per_step,
                    use_thinking=False,  # Disable thinking to reduce JSON complexity
                ),
            )

            # Execute extraction
            history: AgentHistoryList = await agent.run()
            result = history.final_result() if history else None

            if output_model and result:
                try:
                    # Try to parse as structured output
                    if isinstance(result, str):
                        return output_model.model_validate_json(result)
                    elif isinstance(result, dict):
                        return output_model.model_validate(result)
                    else:
                        return result
                except Exception as parse_error:
                    logger.warning(f"Failed to parse structured output: {parse_error}")
                    # Fall back to text extraction
                    return {"page_text": str(result)}

            # Return as dict or original schema format
            if isinstance(schema, dict):
                return {"page_text": str(result)} if result else {}
            elif isinstance(result, str):
                return {"page_text": result}
            else:
                return result or {}

        except Exception as e:
            logger.error(f"Failed to extract data with instruction '{instruction}': {e}")
            raise
        finally:
            # Only close if we created the session
            if session and not self.browser_session:
                await self._close_browser_session(session)

    async def navigate_and_act(
        self,
        url: str,
        instruction: str,
        headless: bool = True,
        use_vision: bool = False,
        max_failures: int = 3,
        max_actions_per_step: int = 3,
        **kwargs,
    ) -> Any:
        """
        Navigate to a URL and perform an action using natural language.

        Args:
            url: The URL to navigate to
            instruction: Natural language instruction for the action
            headless: Whether to run browser in headless mode
            use_vision: Whether to use vision capabilities
            max_failures: Maximum number of failures allowed
            max_actions_per_step: Maximum actions per step
            **kwargs: Additional arguments

        Returns:
            The result of the action
        """
        session = None
        try:
            if not self.llm:
                raise ValueError("LLM client is required for navigation and action")

            session = await self._launch_browser_session(headless, **kwargs)

            # Navigate to the URL first
            event = session.event_bus.dispatch(NavigateToUrlEvent(url=url, timeout_ms=8000))
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)

            # Create browser-use agent for the action
            browser_use_agent = BrowserUseServiceAgent(
                task=instruction,
                llm=BaseChatModel(self.llm),
                browser=session,
                settings=AgentSettings(
                    use_vision=use_vision,
                    max_failures=max_failures,
                    max_actions_per_step=max_actions_per_step,
                    use_thinking=False,  # Disable thinking to reduce JSON complexity
                ),
            )
            logger.info(f"Navigating to {url} and executing: {instruction}")
            result: AgentHistoryList = await browser_use_agent.run()
            logger.info(f"✅ Navigation and action completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to navigate to {url} and execute '{instruction}': {e}")
            raise
        finally:
            # Only close if we created the session
            if session and not self.browser_session:
                await self._close_browser_session(session)

    async def use_browser(
        self,
        instruction: str,
        headless: bool = True,
        use_vision: bool = False,
        max_failures: int = 3,
        max_actions_per_step: int = 3,
        **kwargs,
    ) -> Any:
        result = None
        try:
            if not self.llm:
                raise ValueError("LLM client is required for autonomous agent")

            session = await self._launch_browser_session(headless, **kwargs)

            # Create browser-use agent
            browser_use_agent = BrowserUseServiceAgent(
                task=instruction,
                llm=BaseChatModel(self.llm),
                browser=session,
                settings=AgentSettings(
                    use_vision=use_vision,
                    max_failures=max_failures,
                    max_actions_per_step=max_actions_per_step,
                    use_thinking=False,  # Disable thinking to reduce JSON complexity
                ),
            )
            logger.info(f"Autonomous browser-use agent created for task: {instruction}")
            result = await browser_use_agent.run()
            logger.info(f"✅ Autonomous agent completed: {result}")
        except Exception as e:
            logger.error(f"Failed to create agent for instruction '{instruction}': {e}")
            raise
        finally:
            await self._close_browser_session(session)
            return result

    async def _launch_browser_session(
        self,
        headless: bool = True,
        proxy_server: str = None,
        proxy_bypass: str = None,
        proxy_username: str = None,
        proxy_password: str = None,
        enable_default_extensions: bool = False,
        minimum_wait_page_load_time: float = 0.75,
        **kwargs,
    ) -> BrowserSession:
        """
        Launches a new browser instance.
        """
        try:
            # Create proxy settings only if proxy_server is provided
            proxy_settings = None
            if proxy_server:
                proxy_settings = ProxySettings(
                    server=proxy_server,
                    bypass=proxy_bypass,
                    username=proxy_username,
                    password=proxy_password,
                )

            browser_config = BrowserProfile(
                headless=headless,
                proxy=proxy_settings,
                enable_default_extensions=enable_default_extensions,
                minimum_wait_page_load_time=minimum_wait_page_load_time,
                wait_for_network_idle_page_load_time=5.0,  # Wait for network to be idle
                wait_between_actions=1.0,  # Delay between actions
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",  # Realistic user agent
                **kwargs,
            )
            session = BrowserSession(browser_profile=browser_config)
            await session.start()
            return session
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise

    async def _close_browser_session(self, session: BrowserSession):
        """Closes the browser instance."""
        try:
            if session:
                await session.stop()
                logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Failed to close browser: {e}")
            raise
