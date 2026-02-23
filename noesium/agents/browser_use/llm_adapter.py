"""
Copyright (c) 2025 Xiaming Chen
"""

import asyncio
import logging
from typing import Any, Generic, Literal, Protocol, TypeVar, Union

import dotenv
from pydantic import BaseModel

from noesium.core.llm import BaseLLMClient

logger = logging.getLogger(__name__)

dotenv.load_dotenv()

################################################################################
# Browser-use compatibility
################################################################################

# Define the TypeVar for generic typing
T = TypeVar("T")


class ChatInvokeCompletion(BaseModel, Generic[T]):
    completion: T
    thinking: str | None = None
    redacted_thinking: str | None = None


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


class _MessageBase(BaseModel):
    role: Literal["user", "system", "assistant"]
    cache: bool = False


class UserMessage(_MessageBase):
    role: Literal["user"] = "user"
    content: str | list[ContentPartTextParam | ContentPartImageParam]
    name: str | None = None


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
class BaseChatModel(Protocol):
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
