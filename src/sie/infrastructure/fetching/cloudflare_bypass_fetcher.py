"""Cloudflare bypass fetcher using SeleniumBase + Playwright CDP session hijacking.

When a Cloudflare challenge is detected, this fetcher:
1. Launches undetected Chrome via SeleniumBase
2. Connects via Playwright CDP to bypass Cloudflare
3. Extracts cookies and headers from the browser session
4. Uses the hijacked session for fast HTTP requests
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from sie.domain.errors import FetchError
from sie.domain.models.page import FetchedPage
from sie.infrastructure.fetching.httpx_fetcher import HttpxFetcher
from sie.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _SessionData:
    cookies: dict[str, str]
    headers: dict[str, str]
    domain: str


class CloudflareBypassFetcher:
    """Fetcher that bypasses Cloudflare using SeleniumBase + Playwright CDP session hijacking.

    This fetcher wraps a base HTTP fetcher and falls back to browser-based
    Cloudflare bypass when a challenge is detected.
    """

    def __init__(
        self,
        *,
        base_fetcher: HttpxFetcher,
        browser_timeout_seconds: float = 30.0,
        browser_wait_seconds: float = 10.0,
        headless: bool = True,
        max_browser_retries: int = 2,
    ) -> None:
        self._base_fetcher = base_fetcher
        self._browser_timeout = browser_timeout_seconds
        self._browser_wait = browser_wait_seconds
        self._headless = headless
        self._max_browser_retries = max_browser_retries
        self._session = None
        self._domain = None
        self._driver = None

    async def fetch(self, url: str) -> FetchedPage:
        # Try normal HTTP fetch first
        try:
            page = await self._base_fetcher.fetch(url)
        except FetchError as exc:
            raise FetchError(f"base fetch failed for {url}: {exc}") from exc

        # Check for Cloudflare challenge
        if self._is_cloudflare_challenge(page):
            logger.info("Cloudflare challenge detected for %s, initiating bypass", url)
            await self._bypass_cloudflare(url)
            # Retry with hijacked session
            return await self._fetch_with_session(url)

        return page

    def _is_cloudflare_challenge(self, page: FetchedPage) -> bool:
        """Detect Cloudflare challenge page."""
        if page.status_code == 403:
            return True
        if page.status_code == 503:
            return True
        # Check content for Cloudflare indicators
        if page.is_html and page.decoded_text():
            content = page.decoded_text().lower()
            if "just a moment" in content:
                return True
            if "checking your browser" in content.lower():
                return True
            if "cloudflare" in content and "challenge" in content:
                return True
        return False

    async def _bypass_cloudflare(self, url: str) -> None:
        """Launch browser, bypass Cloudflare, extract session."""
        parsed = urlparse(url)
        self._domain = parsed.netloc

        # Import here to avoid hard dependency
        from playwright.async_api import async_playwright
        from seleniumbase import Driver

        last_error = None
        for attempt in range(self._max_browser_retries):
            try:
                logger.info(
                    "Launching undetected Chrome (attempt %d/%d)",
                    attempt + 1,
                    self._max_browser_retries,
                )

                # Launch undetected Chrome
                driver = Driver(uc=True, headless=True)
                driver_instance = driver

                cdp_port = driver.capabilities["goog:chromeOptions"]["debuggerAddress"]
                cdp_url = f"http://{cdp_port}"

                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(cdp_url)
                    context = browser.contexts[0]
                    page = context.pages[0]

                    logger.info("Navigating to %s to bypass Cloudflare", url)

                    await page.goto(url, wait_until="domcontentloaded")
                    await page.wait_for_timeout(int(self._browser_wait * 1000))

                    title = await page.title()
                    if "Just a moment" in title or "checking your browser" in title.lower():
                        raise RuntimeError("Cloudflare challenge still present after bypass")

                    # Extract session data
                    await self._extract_session(page)

                    await browser.close()

                driver_instance.quit()
                self._driver = None
                logger.info("Cloudflare bypass successful, session hijacked")
                return

            except Exception as exc:
                last_error = exc
                logger.warning("Browser bypass attempt %d failed: %s", attempt + 1, exc)
                if "driver_instance" in locals():
                    with contextlib.suppress(Exception):
                        driver_instance.quit()

        raise FetchError(
            f"Cloudflare bypass failed after {self._max_browser_retries} attempts: {last_error}"
        )

    async def _extract_session(self, page) -> None:
        """Extract cookies and headers from browser page."""
        if not self._domain:
            return

        context = page.context

        # Extract cookies
        cookies = await context.cookies()
        cookie_dict = {
            c["name"]: c["value"]
            for c in cookies
            if self._domain and self._domain in c.get("domain", "")
        }

        # Extract headers from a real request
        captured_headers = {}

        async def on_request(request):
            if self._domain and self._domain in request.url:
                for k, v in request.headers.items():
                    if k.lower() in (
                        "user-agent",
                        "accept",
                        "accept-language",
                        "accept-encoding",
                        "cache-control",
                        "referer",
                    ):
                        captured_headers[k] = v

        page.on("request", on_request)
        await page.reload(wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        self._session = _SessionData(
            cookies=cookie_dict, headers=captured_headers, domain=self._domain
        )

        logger.info(
            "Extracted %d cookies and %d headers for %s",
            len(cookie_dict),
            len(captured_headers),
            self._domain,
        )

    async def _fetch_with_session(self, url: str) -> FetchedPage:
        """Fetch URL using hijacked session cookies/headers."""
        if not self._session:
            raise FetchError("No session available for hijacked fetch")

        # Apply session to base fetcher's client
        client = self._base_fetcher._client

        # Apply cookies
        for name, value in self._session.cookies.items():
            client.cookies.set(name, value, domain=self._session.domain)

        # Apply headers
        for k, v in self._session.headers.items():
            client.headers[k] = v

        # Fetch with session
        try:
            response = await client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise FetchError(f"session fetch failed for {url}: {exc}") from exc

        final_url = str(response.url)
        return FetchedPage(
            url=url,
            final_url=final_url,
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            content_type=response.headers.get("content-type"),
            encoding=response.encoding,
            duration_ms=0,
        )

    async def close(self) -> None:
        """Close browser and underlying clients."""
        if self._driver:
            with contextlib.suppress(Exception):
                self._driver.quit()
        await self._base_fetcher.close()
