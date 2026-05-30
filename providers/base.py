"""
Abstract LLM provider interface.

Every concrete provider (OpenAI-compatible, Anthropic, etc.) implements this
single method. The rest of the agent only ever talks to this interface, so
swapping providers never touches agent or tool code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    """A normalized tool call, regardless of which provider produced it."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """A normalized response shape that all providers return."""
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None

    @property
    def wants_tools(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Interface every provider must implement."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """
        Send a list of chat messages (and optionally tool schemas).
        Return a normalized LLMResponse.
        """
        raise NotImplementedError
