"""OpenAI-compatible LLM provider backed by httpx.

Implements the ``LLMProvider`` port for any API that exposes a
``/v1/chat/completions`` endpoint (OpenAI, local proxies, vLLM, etc.).
"""

from __future__ import annotations

import json

import httpx

from sie.domain.ports.llm import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from sie.logging import get_logger

logger = get_logger(__name__)


class OpenAICompatibleProvider:
    """HTTP client for OpenAI-compatible chat completion APIs.

    Parameters
    ----------
    base_url:
        Root URL of the API (e.g. ``https://api.openai.com``).
        May optionally include a path suffix (e.g. ``http://localhost:20128/v1``).
    api_key:
        Bearer token for authentication.  Empty string = no auth header sent
        (for local providers that don't require authentication).
    model:
        Model identifier sent in the request body.
    timeout_seconds:
        Per-request timeout (legacy, used if granular timeouts not provided).
    connect_timeout_seconds:
        TCP connection timeout.
    read_timeout_seconds:
        Response body read timeout.
    write_timeout_seconds:
        Request body write timeout.
    pool_timeout_seconds:
        Connection pool acquisition timeout.
    client:
        Optional pre-configured ``httpx.AsyncClient`` (for testing).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 60.0,
        connect_timeout_seconds: float = 10.0,
        read_timeout_seconds: float = 60.0,
        write_timeout_seconds: float = 30.0,
        pool_timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

        # Build default headers — only include Authorization when a key is present
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Use granular timeouts for better control
        timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )

        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
        )
        self._owns_client = client is None

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        # If base_url already ends with /v1, don't append it again
        if self._base_url.endswith("/v1"):
            url = f"{self._base_url}/chat/completions"
        else:
            url = f"{self._base_url}/v1/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        logger.debug("LLM request to %s model=%s", url, self._model)

        try:
            response = await self._client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("LLM request timed out: %s", exc)
            raise LLMTimeoutError(f"LLM request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.warning("LLM request transport error: %s", exc)
            raise LLMProviderError(f"LLM transport error: {exc}") from exc

        if response.status_code == 401:
            raise LLMAuthenticationError("LLM API key is invalid or missing")
        if response.status_code == 429:
            raise LLMRateLimitError("LLM rate limit exceeded")
        if response.status_code >= 400:
            body = response.text[:500]
            raise LLMProviderError(f"LLM API returned HTTP {response.status_code}: {body}")

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMProviderError(f"LLM returned invalid JSON: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"LLM response missing expected structure: {exc}") from exc

        return self._strip_code_fences(content)

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences wrapping LLM output."""
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.split("\n")
            # Drop opening fence line (may be ```json or just ```)
            start = 1
            # Drop closing fence line
            end = len(lines)
            if lines[-1].strip() == "```":
                end = len(lines) - 1
            return "\n".join(lines[start:end]).strip()
        return text

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
