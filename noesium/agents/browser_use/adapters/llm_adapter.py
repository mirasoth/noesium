"""
LLM Adapter for Noesium to browser-use

This module provides LLM compatibility types and adapters to bridge between
noesium's LLM infrastructure and the community browser-use repository.
"""

import asyncio
import logging
from typing import Any, Generic, Literal, TypeVar, Union

import dotenv
from pydantic import BaseModel

from noesium.core.llm import BaseLLMClient

logger = logging.getLogger(__name__)

dotenv.load_dotenv()

################################################################################
# Browser-use compatibility types
################################################################################

# Define the TypeVar for generic typing
T = TypeVar("T")


class ChatInvokeUsage(BaseModel):
    """
    Usage information for a chat model invocation.
    """

    prompt_tokens: int
    """The number of tokens in the prompt (this includes the cached tokens as well. When calculating the cost, subtract the cached tokens from the prompt tokens)"""

    prompt_cached_tokens: int | None
    """The number of cached tokens."""

    prompt_cache_creation_tokens: int | None
    """Anthropic only: The number of tokens used to create the cache."""

    prompt_image_tokens: int | None
    """Google only: The number of tokens in the image (prompt tokens is the text tokens + image tokens in that case)"""

    completion_tokens: int
    """The number of tokens in the completion."""

    total_tokens: int
    """The total number of tokens in the response."""


class ChatInvokeCompletion(BaseModel, Generic[T]):
    completion: T
    thinking: str | None = None
    redacted_thinking: str | None = None
    usage: ChatInvokeUsage | None = None
    stop_reason: str | None = None


class ModelError(Exception):
    pass


class ModelProviderError(ModelError):
    def __init__(self, message: str, status_code: int = 502, model: str | None = None):
        super().__init__(message, status_code)
        self.model = model


class ModelRateLimitError(ModelProviderError):
    def __init__(self, message: str, status_code: int = 429, model: str | None = None):
        super().__init__(message, status_code, model)


# Define message types for compatibility
class ContentPartTextParam(BaseModel):
    text: str
    type: Literal["text"] = "text"


class ContentPartRefusalParam(BaseModel):
    refusal: str
    type: Literal["refusal"] = "refusal"


class ContentPartImageParam(BaseModel):
    image_url: Any
    type: Literal["image_url"] = "image_url"


class ImageURL(BaseModel):
    url: str
    detail: Literal["auto", "low", "high"] = "auto"
    media_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"] = "image/png"


class _MessageBase(BaseModel):
    role: Literal["user", "system", "assistant"]
    cache: bool = False


class UserMessage(_MessageBase):
    role: Literal["user"] = "user"
    content: str | list[ContentPartTextParam | ContentPartImageParam]
    name: str | None = None

    @property
    def text(self) -> str:
        """Get text content from message."""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, list):
            text_parts = []
            for part in self.content:
                if isinstance(part, ContentPartTextParam):
                    text_parts.append(part.text)
                elif isinstance(part, ContentPartImageParam):
                    # For images, return the URL
                    if isinstance(part.image_url, str):
                        text_parts.append(part.image_url)
                    elif isinstance(part.image_url, ImageURL):
                        text_parts.append(part.image_url.url)
            return "\n".join(text_parts)
        return str(self.content)


class SystemMessage(_MessageBase):
    role: Literal["system"] = "system"
    content: str | list[ContentPartTextParam]
    name: str | None = None


class AssistantMessage(_MessageBase):
    role: Literal["assistant"] = "assistant"
    content: str | list[ContentPartTextParam | ContentPartRefusalParam] | None
    name: str | None = None
    refusal: str | None = None
    tool_calls: list = []


BaseMessage = Union[UserMessage, SystemMessage, AssistantMessage]
ContentText = ContentPartTextParam
ContentRefusal = ContentPartRefusalParam
ContentImage = ContentPartImageParam


# Define the BaseChatModel class for compatibility
# Using a regular class instead of Protocol for Pydantic compatibility
class BaseChatModel:
    """Base chat model that adapts noesium LLM clients for browser-use compatibility."""

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize Base Chat Model

        Args:
            llm_client: noesium LLM client to adapt
        """
        self.llm_client = llm_client
        self._verified_api_keys = True  # Assume the noesium client is properly configured

    @property
    def provider(self) -> str:
        """Return provider name if available"""
        return getattr(self.llm_client, "provider", "unknown")

    @property
    def name(self) -> str:
        """Return the model name."""
        return self.model

    @property
    def model(self) -> str:
        """Return model name"""
        return self.model_name

    @property
    def model_name(self) -> str:
        """Return the model name for legacy support."""
        return getattr(self.llm_client, "chat_model", getattr(self.llm_client, "model", "unknown"))

    async def ainvoke(
        self, messages: list[BaseMessage], output_format: type[T] | None = None
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """Invoke the LLM with messages."""
        try:
            # Convert browser-use messages to noesium format
            noesium_messages = []
            for msg in messages:
                if hasattr(msg, "role"):
                    # Extract text content properly from browser-use message objects
                    content_text = ""
                    if hasattr(msg, "text"):
                        # Use the convenient .text property that handles both string and list formats
                        content_text = msg.text
                    elif hasattr(msg, "content"):
                        # Fallback: handle content directly
                        if isinstance(msg.content, str):
                            content_text = msg.content
                        elif isinstance(msg.content, list):
                            # Extract text from content parts
                            text_parts = []
                            for part in msg.content:
                                if hasattr(part, "text") and hasattr(part, "type") and part.type == "text":
                                    text_parts.append(part.text)
                            content_text = "\n".join(text_parts)
                        else:
                            content_text = str(msg.content)
                    else:
                        content_text = str(msg)

                    noesium_messages.append({"role": msg.role, "content": content_text})
                elif isinstance(msg, dict):
                    # Already in the right format
                    noesium_messages.append(msg)
                else:
                    # Handle other message formats
                    noesium_messages.append({"role": "user", "content": str(msg)})

            # Choose completion method based on output_format
            if output_format is not None:
                # Use structured completion for structured output
                try:
                    if asyncio.iscoroutinefunction(self.llm_client.structured_completion):
                        structured_response = await self.llm_client.structured_completion(
                            noesium_messages, output_format
                        )
                    else:
                        structured_response = self.llm_client.structured_completion(noesium_messages, output_format)
                    return ChatInvokeCompletion(completion=structured_response)
                except Exception as e:
                    logger.error(f"Error in structured completion: {e}")
                    raise
            else:
                # Use regular completion for string output
                if asyncio.iscoroutinefunction(self.llm_client.completion):
                    response = await self.llm_client.completion(noesium_messages)
                else:
                    response = self.llm_client.completion(noesium_messages)

                return ChatInvokeCompletion(completion=str(response))

        except Exception as e:
            logger.error(f"Error in LLM adapter: {e}")
            raise


class NoesiumLLMAdapter(BaseChatModel):
    """
    Adapter that wraps noesium's LLM client for use with browser-use agents.

    This adapter bridges the gap between noesium's BaseLLMClient interface
    and browser-use's expected LLM interface.
    """

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize the adapter with a noesium LLM client.

        Args:
            llm_client: A noesium BaseLLMClient instance
        """
        super().__init__(llm_client)

    async def ainvoke(
        self, messages: list, output_format: type[T] | None = None
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """
        Invoke the LLM with messages.

        Args:
            messages: List of messages to send to the LLM
            output_format: Optional Pydantic model for structured output

        Returns:
            ChatInvokeCompletion with the LLM response
        """
        return await super().ainvoke(messages, output_format)

    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"NoesiumLLMAdapter(model={self.model_name}, provider={self.provider})"


def create_llm_adapter(llm_client: BaseLLMClient) -> NoesiumLLMAdapter:
    """
    Create a browser-use compatible LLM adapter from a noesium LLM client.

    Args:
        llm_client: A noesium BaseLLMClient instance

    Returns:
        NoesiumLLMAdapter instance
    """
    return NoesiumLLMAdapter(llm_client)


__all__ = [
    # Types
    "ChatInvokeUsage",
    "ChatInvokeCompletion",
    "BaseChatModel",
    "ModelProviderError",
    "ModelRateLimitError",
    "ImageURL",
    # Message types
    "BaseMessage",
    "UserMessage",
    "SystemMessage",
    "AssistantMessage",
    "ContentText",
    "ContentRefusal",
    "ContentImage",
    # Adapters
    "NoesiumLLMAdapter",
    "create_llm_adapter",
]
