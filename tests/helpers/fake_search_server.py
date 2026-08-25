"""Controlled local HTTP test server for Phase 6M integration tests.

Implements the generic ``POST /search`` contract that ``HttpSearchProvider``
expects — entirely in-process, no real network, no external APIs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

__all__ = [
    "FakeSearchServer",
    "ServerConfig",
    "ServerMode",
]


class ServerMode:
    """Behavior modes the fake server can operate in."""

    OK = "ok"
    NOT_FOUND = "not_found"
    AUTH_ERROR = "auth_error"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    MALFORMED_JSON = "malformed_json"
    TIMEOUT = "timeout"


@dataclass
class ServerConfig:
    """Configuration for the fake search server's behavior."""

    mode: str = ServerMode.OK
    target_domain: str = "oursite.io"
    results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    received_requests: list[dict[str, Any]] = field(default_factory=list)
    api_key: str | None = None
    timeout_seconds: float = 1.0


@dataclass
class FakeSearchServer:
    """A fully in-process HTTP server using ``httpx.MockTransport``.

    Provides a real URL that ``HttpSearchProvider`` can be pointed at,
    with request capturing and configurable response behavior.

    Usage::

        server = FakeSearchServer()
        server.config.results["best crm software"] = [...]
        provider = HttpSearchProvider(
            base_url=server.base_url,
            client=server.client,
        )
        result = await provider.search(query)
        assert server.config.received_requests[0]["query"] == "best crm software"
    """

    base_url: str = "http://fake-test-server.local"

    def __init__(self, config: ServerConfig | None = None) -> None:
        self.config = config or ServerConfig()
        self._handler = self._build_handler()
        self._client: httpx.AsyncClient | None = None

    def _build_handler(self):
        """Build the MockTransport handler closure."""

        def handler(request: httpx.Request) -> httpx.Response:
            body: str | dict[str, Any]
            try:
                body = json.loads(request.content)
            except (json.JSONDecodeError, ValueError):
                body = {}

            self.config.received_requests.append(
                {
                    "url": str(request.url),
                    "method": request.method,
                    "headers": dict(request.headers),
                    "body": body if isinstance(body, dict) else str(body),
                }
            )

            mode = self.config.mode

            if mode == ServerMode.TIMEOUT:
                raise httpx.TimeoutException("simulated timeout")

            if mode == ServerMode.AUTH_ERROR:
                return self._json_response(401, {"error": "unauthorized"})

            if mode == ServerMode.RATE_LIMIT:
                return self._json_response(429, {"error": "rate limit exceeded"})

            if mode == ServerMode.SERVER_ERROR:
                return self._json_response(500, {"error": "internal server error"})

            if mode == ServerMode.MALFORMED_JSON:
                return httpx.Response(
                    status_code=200,
                    content=b"<<<not json>>>",
                    headers={"content-type": "application/json"},
                    request=request,
                )

            if mode == ServerMode.NOT_FOUND:
                query_str = str(body.get("query", "")) if isinstance(body, dict) else ""
                results = self._build_results(query_str, found=False)
                return self._json_response(200, {"results": results})

            query_str = str(body.get("query", "")) if isinstance(body, dict) else ""
            results = self._build_results(query_str, found=True)
            return self._json_response(200, {"results": results})

        return handler

    @staticmethod
    def _json_response(status_code: int, data: dict[str, Any]) -> httpx.Response:
        content = json.dumps(data).encode()
        request = httpx.Request("POST", "http://fake-test-server.local/search")
        return httpx.Response(
            status_code=status_code,
            content=content,
            headers={"content-type": "application/json"},
            request=request,
        )

    def _build_results(self, query: str, *, found: bool) -> list[dict[str, Any]]:
        """Build synthetic search results for a query.

        When *found* is True and the target domain appears, place it at a
        deterministic position.  When *found* is False, return only
        competitor domains.
        """
        if not found:
            return [
                {
                    "title": f"Competitor for {query}",
                    "url": "https://competitor.example.com/page",
                    "position": 1,
                },
                {
                    "title": f"Another Competitor for {query}",
                    "url": "https://other.example.com/entry",
                    "position": 2,
                },
            ]

        configured = self.config.results.get(query)
        if configured is not None:
            return configured

        domain = self.config.target_domain
        return [
            {
                "title": f"Example Result for {query}",
                "url": f"https://{domain}/page",
                "position": 1,
            },
            {
                "title": f"Competitor for {query}",
                "url": "https://competitor.example.com/page",
                "position": 2,
            },
        ]

    @property
    def client(self) -> httpx.AsyncClient:
        """Return a client bound to the mock transport (injectable into HttpSearchProvider)."""
        if self._client is None:
            transport = httpx.MockTransport(self._handler)
            self._client = httpx.AsyncClient(transport=transport, base_url=self.base_url)
        return self._client

    def set_mode(self, mode: str) -> None:
        """Switch the server to a new behavioral mode."""
        self.config.mode = mode

    def reset(self) -> None:
        """Clear captured requests and restore OK mode."""
        self.config.received_requests.clear()
        self.config.mode = ServerMode.OK

    @property
    def request_count(self) -> int:
        return len(self.config.received_requests)

    def get_request(self, index: int = 0) -> dict[str, Any]:
        """Return a captured request body by index."""
        return self.config.received_requests[index]

    async def close(self) -> None:
        """Close the internal client if it was created."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def make_provider(server: FakeSearchServer, **provider_kwargs: object) -> object:
    """Helper: create an ``HttpSearchProvider`` wired to *server*.

    Any keyword overrides (e.g. ``api_key``, ``timeout_seconds``) are passed
    through; ``base_url`` is always taken from the server.
    """
    from sie.infrastructure.search.http_provider import HttpSearchProvider

    kwargs: dict[str, object] = {"base_url": server.base_url, "client": server.client}
    kwargs.update(provider_kwargs)
    return HttpSearchProvider(**kwargs)  # type: ignore[arg-type]


def verify_target_domain_in_url(target_domain: str, url: str) -> bool:
    """Check whether *url* belongs to *target_domain* (case-insensitive, www-stripped)."""
    host = urlparse(url).netloc.split(":")[0].casefold()
    if host.startswith("www."):
        host = host[4:]
    return host == target_domain.casefold()
