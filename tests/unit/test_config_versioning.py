import importlib.metadata

from sie import __version__
from sie.config import Settings


def test_default_crawler_user_agent_tracks_package_version() -> None:
    settings = Settings()

    assert f"SEOIntelligenceEngine/{__version__}" in settings.crawler.user_agent


def test_installed_metadata_tracks_source_version() -> None:
    assert importlib.metadata.version("seo-intelligence-engine") == __version__
