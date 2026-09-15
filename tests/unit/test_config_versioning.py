from sie import __version__
from sie.config import Settings


def test_default_crawler_user_agent_tracks_package_version() -> None:
    settings = Settings()

    assert f"SEOIntelligenceEngine/{__version__}" in settings.crawler.user_agent
