"""Tests for SSRF protection — IP validation, URL safety, hostname checks."""

from __future__ import annotations

import ipaddress

from sie.domain.security.ssrf import (
    is_cloud_metadata_ip,
    is_private_ip,
    is_safe_hostname,
    validate_url,
)


class TestIsPrivateIP:
    def test_localhost_ipv4(self):
        assert is_private_ip(ipaddress.IPv4Address("127.0.0.1")) is True

    def test_loopback_range(self):
        assert is_private_ip(ipaddress.IPv4Address("127.0.0.2")) is True

    def test_private_10(self):
        assert is_private_ip(ipaddress.IPv4Address("10.0.0.1")) is True

    def test_private_172(self):
        assert is_private_ip(ipaddress.IPv4Address("172.16.0.1")) is True

    def test_private_192(self):
        assert is_private_ip(ipaddress.IPv4Address("192.168.1.1")) is True

    def test_link_local(self):
        assert is_private_ip(ipaddress.IPv4Address("169.254.1.1")) is True

    def test_public_ip(self):
        assert is_private_ip(ipaddress.IPv4Address("8.8.8.8")) is False

    def test_google_dns(self):
        assert is_private_ip(ipaddress.IPv4Address("1.1.1.1")) is False

    def test_ipv6_loopback(self):
        assert is_private_ip(ipaddress.IPv6Address("::1")) is True

    def test_ipv6_ula(self):
        assert is_private_ip(ipaddress.IPv6Address("fd00::1")) is True

    def test_ipv6_public(self):
        assert is_private_ip(ipaddress.IPv6Address("2606:4700::1")) is False


class TestIsCloudMetadataIP:
    def test_aws_metadata(self):
        assert is_cloud_metadata_ip(ipaddress.IPv4Address("169.254.169.254")) is True

    def test_normal_ip(self):
        assert is_cloud_metadata_ip(ipaddress.IPv4Address("8.8.8.8")) is False

    def test_aws_ipv6_metadata(self):
        assert is_cloud_metadata_ip(ipaddress.IPv6Address("fd00:ec2::254")) is True


class TestIsSafeHostname:
    def test_public_hostname(self):
        safe, err = is_safe_hostname("example.com")
        assert safe is True
        assert err is None

    def test_localhost_blocked(self):
        safe, err = is_safe_hostname("localhost")
        assert safe is False
        assert "blocked" in err.lower()

    def test_localhost_allowed(self):
        safe, _err = is_safe_hostname("localhost", allow_localhost=True)
        assert safe is True

    def test_private_ip_blocked(self):
        safe, _err = is_safe_hostname("192.168.1.1")
        assert safe is False

    def test_private_ip_allowed(self):
        safe, _err = is_safe_hostname("127.0.0.1", allow_localhost=True)
        assert safe is True

    def test_cloud_metadata_blocked(self):
        safe, err = is_safe_hostname("169.254.169.254")
        assert safe is False
        assert "metadata" in err.lower()


class TestValidateURL:
    def test_valid_https(self):
        safe, err = validate_url("https://example.com")
        assert safe is True
        assert err is None

    def test_valid_http(self):
        safe, _err = validate_url("http://example.com")
        assert safe is True

    def test_ftp_blocked(self):
        safe, err = validate_url("ftp://example.com/file")
        assert safe is False
        assert "scheme" in err.lower()

    def test_file_scheme_blocked(self):
        safe, _err = validate_url("file:///etc/passwd")
        assert safe is False

    def test_missing_hostname(self):
        safe, err = validate_url("https://")
        assert safe is False
        assert "hostname" in err.lower()

    def test_localhost_blocked(self):
        safe, _err = validate_url("http://localhost:8000")
        assert safe is False

    def test_localhost_allowed(self):
        safe, _err = validate_url("http://localhost:8000", allow_localhost=True)
        assert safe is True

    def test_private_ip_blocked(self):
        safe, _err = validate_url("http://192.168.1.1/api")
        assert safe is False

    def test_cloud_metadata_blocked(self):
        safe, _err = validate_url("http://169.254.169.254/latest/meta-data/")
        assert safe is False

    def test_path_with_private_ip(self):
        safe, _err = validate_url("https://10.0.0.1:8080/secret")
        assert safe is False

    def test_valid_url_with_path(self):
        safe, _err = validate_url("https://example.com/path/to/page?q=1")
        assert safe is True
