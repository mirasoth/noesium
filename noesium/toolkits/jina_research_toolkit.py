"""
Jina research toolkit for web content extraction and Q&A.

Provides tools for extracting readable content from web pages via Jina Reader API
and performing LLM-powered question answering on web content.
"""

import asyncio
from typing import Callable, Dict

import aiohttp

from noesium.core.toolify.base import AsyncBaseToolkit
from noesium.core.toolify.config import ToolkitConfig
from noesium.core.toolify.registry import register_toolkit
from noesium.core.utils.logging import get_logger

logger = get_logger(__name__)


@register_toolkit("jina_research")
class JinaResearchToolkit(AsyncBaseToolkit):
    """
    Toolkit for web content extraction and Q&A via Jina Reader API.

    Provides:
    - Web page content extraction (Jina Reader)
    - LLM-powered question answering on extracted content
    - Related link extraction from web pages

    Required configuration (via ToolkitConfig.config):
    - JINA_API_KEY: API key for Jina Reader service
    """

    def __init__(self, config: ToolkitConfig = None):
        super().__init__(config)

        self.jina_url_template = "https://r.jina.ai/{url}"

        jina_api_key = self.config.config.get("JINA_API_KEY")
        if not jina_api_key:
            self.logger.warning("JINA_API_KEY not found in config - web content extraction may fail")

        self.jina_headers = {"Authorization": f"Bearer {jina_api_key}"} if jina_api_key else {}
        self.summary_token_limit = self.config.config.get("summary_token_limit", 1000)

    async def get_web_content(self, url: str) -> str:
        """
        Extract readable content from a web page using Jina Reader API.

        Args:
            url: The URL to extract content from

        Returns:
            Extracted text content from the web page
        """
        self.logger.info(f"Extracting content from: {url}")

        if not self.jina_headers.get("Authorization"):
            raise ValueError("JINA_API_KEY not configured")

        try:
            jina_url = self.jina_url_template.format(url=url)
            async with aiohttp.ClientSession() as session:
                async with session.get(jina_url, headers=self.jina_headers) as response:
                    response.raise_for_status()
                    content = await response.text()

            self.logger.info(f"Extracted {len(content)} characters from {url}")
            return content

        except Exception as e:
            self.logger.error(f"Content extraction failed for {url}: {e}")
            return f"Error extracting content from {url}: {str(e)}"

    async def web_qa(self, url: str, question: str) -> str:
        """
        Ask a question about a specific web page.

        Extracts content from the given URL via Jina Reader and uses the LLM to answer
        the provided question based on that content. Also attempts to find related links.

        Use cases:
        - Gather specific information from a webpage
        - Ask detailed questions about web content
        - Get summaries of web articles

        Args:
            url: The URL of the webpage to analyze
            question: The question to ask about the webpage content

        Returns:
            Answer to the question with related links
        """
        self.logger.info(f"Performing web Q&A for {url} with question: {question}")

        try:
            content = await self.get_web_content(url)

            if not content.strip():
                return f"Could not extract readable content from {url}"

            if not question.strip():
                question = "Summarize the main content and key points of this webpage."

            qa_task = self._answer_question(content, question)
            links_task = self._extract_related_links(url, content, question)

            answer, related_links = await asyncio.gather(qa_task, links_task)

            result = f"Answer: {answer}"
            if related_links.strip():
                result += f"\n\nRelated Links: {related_links}"

            return result

        except Exception as e:
            self.logger.error(f"Web Q&A failed for {url}: {e}")
            return f"Error processing {url}: {str(e)}"

    async def _answer_question(self, content: str, question: str) -> str:
        if len(content) > self.summary_token_limit * 4:
            content = content[: self.summary_token_limit * 4] + "..."

        prompt = f"""Based on the following web content, please answer the question.

Web Content:
{content}

Question: {question}

Please provide a clear, concise answer based on the content above. If the content doesn't contain enough information to answer the question, please state that clearly."""

        try:
            response = self.llm_client.completion(
                messages=[{"role": "user", "content": prompt}], temperature=0.1, max_tokens=500
            )
            return response.strip()
        except Exception as e:
            self.logger.error(f"LLM question answering failed: {e}")
            return f"Could not generate answer: {str(e)}"

    async def _extract_related_links(self, url: str, content: str, question: str) -> str:
        prompt = f"""From the following web content, extract any relevant links that might be related to this question: "{question}"

Original URL: {url}
Content: {content[:2000]}...

Please list any URLs, links, or references mentioned in the content that could provide additional information related to the question. Format as a simple list, one per line. If no relevant links are found, respond with "No related links found."
"""

        try:
            response = self.llm_client.completion(
                messages=[{"role": "user", "content": prompt}], temperature=0.1, max_tokens=200
            )
            return response.strip()
        except Exception as e:
            self.logger.error(f"Link extraction failed: {e}")
            return "Could not extract related links"

    async def get_tools_map(self) -> Dict[str, Callable]:
        return {
            "get_web_content": self.get_web_content,
            "web_qa": self.web_qa,
        }
