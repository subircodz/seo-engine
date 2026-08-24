"""Port: LLM provider abstraction.

Domain layer depends on this Protocol; concrete implementations live in
``sie.infrastructure.llm`` and are injected at the composition root.

The provider exposes a minimal ``generate`` interface compatible with
OpenAI-style chat completion APIs but does NOT couple the domain to any
specific SDK.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Thin async interface for text generation via an LLM."""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send a prompt pair and return the assistant's raw text response.

        Raises ``LLMProviderError`` on transport, auth, or response errors.
        """
        ...

    async def close(self) -> None:
        """Release underlying connections."""
        ...


class LLMProviderError(Exception):
    """Raised when the LLM provider cannot fulfil a request.

    Subclasses distinguish error categories without leaking transport details
    into the domain layer.
    """


class LLMTimeoutError(LLMProviderError):
    """The LLM request timed out."""


class LLMAuthenticationError(LLMProviderError):
    """The API key is missing, invalid, or expired."""


class LLMRateLimitError(LLMProviderError):
    """The provider returned a rate-limit (429) response."""
