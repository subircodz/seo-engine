"""Composition helpers for external analytics/backlink providers."""

from __future__ import annotations

from typing import Any

from sie.config import Settings

__all__ = ["create_external_providers"]


def create_external_providers(settings: Settings) -> dict[str, Any]:
    """Construct configured external providers without making network calls."""
    providers: dict[str, Any] = {
        "search_console": None,
        "analytics": None,
        "backlinks": None,
    }

    if settings.search_console.enabled:
        from sie.infrastructure.google.oauth_client import GoogleOAuthClient
        from sie.infrastructure.google.search_console import SearchConsoleProvider

        oauth = GoogleOAuthClient(
            client_id=settings.search_console.client_id,
            client_secret=settings.search_console.client_secret,
            refresh_token=settings.search_console.refresh_token,
            access_token=settings.search_console.access_token,
            timeout_seconds=settings.search_console.timeout_seconds,
        )
        providers["search_console"] = SearchConsoleProvider(
            oauth,
            settings.search_console.property_url,
            timeout_seconds=settings.search_console.timeout_seconds,
        )

    if settings.analytics.enabled:
        from sie.infrastructure.google.analytics_data import AnalyticsDataProvider
        from sie.infrastructure.google.oauth_client import GoogleOAuthClient

        oauth = GoogleOAuthClient(
            client_id=settings.analytics.client_id,
            client_secret=settings.analytics.client_secret,
            refresh_token=settings.analytics.refresh_token,
            access_token=settings.analytics.access_token,
            timeout_seconds=settings.analytics.timeout_seconds,
        )
        providers["analytics"] = AnalyticsDataProvider(
            oauth,
            settings.analytics.property_id,
            timeout_seconds=settings.analytics.timeout_seconds,
        )

    if settings.backlinks.enabled:
        from sie.infrastructure.backlinks.dataforseo import DataForSeoBacklinkProvider

        providers["backlinks"] = DataForSeoBacklinkProvider(
            login=settings.backlinks.login,
            password=settings.backlinks.password,
            base_url=settings.backlinks.base_url,
            timeout_seconds=settings.backlinks.timeout_seconds,
        )

    return providers
