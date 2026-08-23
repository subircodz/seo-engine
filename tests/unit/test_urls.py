"""URL normalization, scope checks, and link extraction."""

from sie.infrastructure.crawling.urls import (
    extract_links,
    host_of,
    is_crawlable,
    normalize_url,
    same_site,
)


class TestNormalizeUrl:
    def test_strips_fragment(self):
        assert normalize_url("https://example.com/#top") == "https://example.com/"

    def test_lowercases_scheme_and_host(self):
        assert normalize_url("HTTP://Example.COM/") == "http://example.com/"

    def test_strips_default_port_443(self):
        assert normalize_url("https://example.com:443/path") == "https://example.com/path"

    def test_preserves_non_default_port(self):
        assert normalize_url("https://example.com:8443/path") == "https://example.com:8443/path"

    def test_empty_path_becomes_slash(self):
        assert normalize_url("https://example.com") == "https://example.com/"

    def test_sorts_query_params(self):
        url = normalize_url("https://example.com/?b=2&a=1")
        assert url == "https://example.com/?a=1&b=2"

    def test_strips_trailing_slash_consistency(self):
        assert normalize_url("https://example.com/a/") == "https://example.com/a/"

    def test_dedup_different_input_same_output(self):
        a = normalize_url("HTTP://Example.COM:80/a?q=1&x=2#f")
        b = normalize_url("http://example.com/a?x=2&q=1")
        assert a == b


class TestIsCrawlable:
    def test_http_ok(self):
        assert is_crawlable("http://example.com/")

    def test_https_ok(self):
        assert is_crawlable("https://example.com/")

    def test_ftp_rejected(self):
        assert not is_crawlable("ftp://example.com/file")

    def test_no_host_rejected(self):
        assert not is_crawlable("https://")


class TestHostOf:
    def test_strips_port(self):
        assert host_of("https://example.com:8443/x") == "example.com"


class TestSameSite:
    def test_identical_hosts(self):
        assert same_site("https://a.com/x", "https://a.com/y")

    def test_www_prefix_ignored(self):
        assert same_site("https://www.example.com/", "https://example.com/")

    def test_different_hosts(self):
        assert not same_site("https://a.com/", "https://b.com/")


class TestExtractLinks:
    def test_absolutes_and_relatives(self):
        links = extract_links('<a href="/a">A</a><a href="https://b.com/c">B</a>', "https://x.com/")
        assert links == ["https://x.com/a", "https://b.com/c"]

    def test_deduplicates(self):
        links = extract_links('<a href="/x"></a><a href="/x"></a>', "https://example.com/")
        assert links == ["https://example.com/x"]

    def test_resolves_base_tag(self):
        links = extract_links('<base href="/sub/"><a href="deep">deep</a>', "https://example.com/")
        assert links == ["https://example.com/sub/deep"]

    def test_mailto_filtered_at_enqueue(self):
        links = extract_links('<a href="mailto:x@y.com">mail</a>', "https://x.com/")
        # extract_links returns raw urls; filter by is_crawlable is a caller concern
        assert "mailto:x@y.com" in links
