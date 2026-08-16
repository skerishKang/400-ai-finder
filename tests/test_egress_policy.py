"""Unit tests for SSRF-safe public egress policy (#1295).

Deterministic offline test matrix covering all IP classification, URL normalization,
DNS resolution, and provider service endpoint validation rules.
Zero real network, zero real DNS.
"""

import socket

from src.fetch.egress_policy import (
    FULL_REBINDING_PREVENTION,
    EgressPolicy,
    PublicEgressPolicy,
    is_safe_public_ip,
    is_valid_firecrawl_service_endpoint,
)


class TestPublicEgressPolicyIpClassification:
    """Test IP address classification and filtering."""

    def test_public_ipv4_allow(self):
        policy = PublicEgressPolicy()
        assert is_safe_public_ip("93.184.216.34") is True
        assert is_safe_public_ip("8.8.8.8") is True
        assert is_safe_public_ip("1.1.1.1") is True
        assert policy.is_authorized("http://93.184.216.34/") is True
        assert policy.is_authorized("https://8.8.8.8/dns-query") is True

    def test_public_ipv6_allow(self):
        policy = PublicEgressPolicy()
        assert is_safe_public_ip("2606:2800:220:1:248:1893:25c8:1946") is True
        assert is_safe_public_ip("2001:4860:4860::8888") is True
        assert policy.is_authorized("http://[2606:2800:220:1:248:1893:25c8:1946]/") is True
        assert policy.is_authorized("https://[2001:4860:4860::8888]/") is True

    def test_localhost_reject(self):
        policy = PublicEgressPolicy()
        assert policy.is_authorized("http://localhost/") is False
        assert policy.is_authorized("http://localhost:8080/") is False
        assert policy.is_authorized("http://sub.localhost/") is False
        assert policy.is_authorized("http://app.internal.localhost/") is False
        assert policy.is_authorized("http://localhost.localdomain/") is False
        assert policy.is_authorized("http://ip6-localhost/") is False
        assert policy.is_authorized("http://ip6-loopback/") is False

    def test_loopback_reject(self):
        policy = PublicEgressPolicy()
        assert is_safe_public_ip("127.0.0.1") is False
        assert is_safe_public_ip("127.0.0.2") is False
        assert is_safe_public_ip("127.255.255.254") is False
        assert is_safe_public_ip("::1") is False
        assert is_safe_public_ip("0:0:0:0:0:0:0:1") is False
        assert policy.is_authorized("http://127.0.0.1/") is False
        assert policy.is_authorized("http://127.0.0.2:8000/") is False
        assert policy.is_authorized("http://[::1]/") is False
        assert policy.is_authorized("http://[0:0:0:0:0:0:0:1]:8080/") is False

    def test_private_rfc1918_and_ula_reject(self):
        policy = PublicEgressPolicy()
        # 10.0.0.0/8
        assert is_safe_public_ip("10.0.0.1") is False
        assert is_safe_public_ip("10.255.255.255") is False
        assert policy.is_authorized("http://10.0.0.1/") is False

        # 172.16.0.0/12
        assert is_safe_public_ip("172.16.0.1") is False
        assert is_safe_public_ip("172.31.255.254") is False
        assert policy.is_authorized("http://172.16.0.1/") is False
        assert policy.is_authorized("http://172.31.255.254:8080/") is False

        # 192.168.0.0/16
        assert is_safe_public_ip("192.168.0.1") is False
        assert is_safe_public_ip("192.168.1.1") is False
        assert is_safe_public_ip("192.168.255.254") is False
        assert policy.is_authorized("http://192.168.1.1/") is False

        # IPv6 ULA (fc00::/7)
        assert is_safe_public_ip("fc00::1") is False
        assert is_safe_public_ip("fd12:3456:789a:1::1") is False
        assert policy.is_authorized("http://[fc00::1]/") is False
        assert policy.is_authorized("http://[fd12:3456:789a:1::1]/") is False

    def test_link_local_reject(self):
        policy = PublicEgressPolicy()
        # IPv4 link-local (169.254.0.0/16)
        assert is_safe_public_ip("169.254.0.1") is False
        assert is_safe_public_ip("169.254.1.1") is False
        assert policy.is_authorized("http://169.254.1.1/") is False

        # IPv6 link-local (fe80::/10)
        assert is_safe_public_ip("fe80::1") is False
        assert is_safe_public_ip("fe80::200:5efe:10.0.0.1") is False
        assert policy.is_authorized("http://[fe80::1]/") is False

    def test_metadata_address_reject(self):
        policy = PublicEgressPolicy()
        assert is_safe_public_ip("169.254.169.254") is False
        assert policy.is_authorized("http://169.254.169.254/") is False
        assert policy.is_authorized("http://169.254.169.254/latest/meta-data/") is False
        assert policy.is_authorized("http://169.254.169.254:80/") is False
        assert policy.is_authorized("http://[fd00:ec2::254]/") is False

    def test_unspecified_reject(self):
        policy = PublicEgressPolicy()
        assert is_safe_public_ip("0.0.0.0") is False
        assert is_safe_public_ip("::") is False
        assert policy.is_authorized("http://0.0.0.0/") is False
        assert policy.is_authorized("http://0.0.0.0:80/") is False
        assert policy.is_authorized("http://[::]/") is False

    def test_multicast_reject(self):
        policy = PublicEgressPolicy()
        assert is_safe_public_ip("224.0.0.1") is False
        assert is_safe_public_ip("239.255.255.250") is False
        assert is_safe_public_ip("ff02::1") is False
        assert policy.is_authorized("http://224.0.0.1/") is False
        assert policy.is_authorized("http://239.255.255.250:1900/") is False
        assert policy.is_authorized("http://[ff02::1]/") is False

    def test_reserved_non_public_reject(self):
        policy = PublicEgressPolicy()
        # Carrier-grade NAT (100.64.0.0/10)
        assert is_safe_public_ip("100.64.0.1") is False
        assert policy.is_authorized("http://100.64.0.1/") is False

        # Broadcast
        assert is_safe_public_ip("255.255.255.255") is False
        assert policy.is_authorized("http://255.255.255.255/") is False

        # TEST-NET-1, 2, 3
        assert is_safe_public_ip("192.0.2.1") is False
        assert is_safe_public_ip("198.51.100.1") is False
        assert is_safe_public_ip("203.0.113.1") is False
        assert policy.is_authorized("http://192.0.2.1/") is False
        assert policy.is_authorized("http://198.51.100.1/") is False
        assert policy.is_authorized("http://203.0.113.1/") is False

        # Benchmarking (198.18.0.0/15)
        assert is_safe_public_ip("198.18.0.1") is False
        assert policy.is_authorized("http://198.18.0.1/") is False

        # Class E / Reserved (240.0.0.0/4)
        assert is_safe_public_ip("240.0.0.1") is False
        assert policy.is_authorized("http://240.0.0.1/") is False

        # IPv6 documentation (2001:db8::/32) & Discard (100::/64)
        assert is_safe_public_ip("2001:db8::1") is False
        assert is_safe_public_ip("100::1") is False
        assert policy.is_authorized("http://[2001:db8::1]/") is False
        assert policy.is_authorized("http://[100::1]/") is False

    def test_ipv4_mapped_ipv6_public_allow(self):
        policy = PublicEgressPolicy()
        assert is_safe_public_ip("::ffff:93.184.216.34") is True
        assert is_safe_public_ip("::ffff:8.8.8.8") is True
        assert is_safe_public_ip("::ffff:5db8:d822") is True  # 93.184.216.34 in hex
        assert policy.is_authorized("http://[::ffff:93.184.216.34]/") is True
        assert policy.is_authorized("http://[::ffff:93.184.216.34]:8080/") is True

    def test_ipv4_mapped_ipv6_private_reject(self):
        policy = PublicEgressPolicy()
        assert is_safe_public_ip("::ffff:127.0.0.1") is False
        assert is_safe_public_ip("::ffff:192.168.1.1") is False
        assert is_safe_public_ip("::ffff:10.0.0.1") is False
        assert is_safe_public_ip("::ffff:169.254.169.254") is False
        assert is_safe_public_ip("::ffff:7f00:1") is False  # 127.0.0.1 in hex
        assert policy.is_authorized("http://[::ffff:127.0.0.1]/") is False
        assert policy.is_authorized("http://[::ffff:192.168.1.1]/") is False
        assert policy.is_authorized("http://[::ffff:169.254.169.254]/") is False


class TestPublicEgressPolicyUrlParsing:
    """Test URL parsing, scheme, port, userinfo, and normalization."""

    def test_userinfo_reject(self):
        policy = PublicEgressPolicy(resolver=lambda h: ["93.184.216.34"])
        assert policy.is_authorized("http://user:password@example.com/") is False
        assert policy.is_authorized("http://user@example.com/") is False
        assert policy.is_authorized("https://admin:secret@93.184.216.34/") is False
        assert policy.is_authorized("http://:pass@example.com/") is False
        assert policy.is_authorized("http://user:@example.com/") is False

    def test_malformed_authority_reject(self):
        policy = PublicEgressPolicy(resolver=lambda h: ["93.184.216.34"])
        assert policy.is_authorized("http://[::1/path") is False  # unclosed bracket
        assert policy.is_authorized("http:///path") is False       # missing host
        assert policy.is_authorized("http://") is False            # empty host
        assert policy.is_authorized("http://:/path") is False      # empty host with port colon
        assert policy.is_authorized("http://-example.com/") is False  # leading hyphen in label
        assert policy.is_authorized("http://example-.com/") is False  # trailing hyphen in label
        assert policy.is_authorized("not-a-url") is False
        assert policy.is_authorized("") is False
        assert policy.is_authorized(None) is False  # type: ignore[arg-type]

    def test_invalid_port_reject(self):
        policy = PublicEgressPolicy(resolver=lambda h: ["93.184.216.34"])
        assert policy.is_authorized("http://example.com:0/") is False
        assert policy.is_authorized("http://example.com:65536/") is False
        assert policy.is_authorized("http://example.com:99999/") is False
        assert policy.is_authorized("http://example.com:-1/") is False
        assert policy.is_authorized("http://example.com:abc/") is False
        assert policy.is_authorized("http://example.com:80/") is True
        assert policy.is_authorized("https://example.com:443/") is True
        assert policy.is_authorized("https://example.com:8443/") is True

    def test_non_https_scheme_reject(self):
        policy = PublicEgressPolicy(resolver=lambda h: ["93.184.216.34"])
        assert policy.is_authorized("ftp://example.com/file.txt") is False
        assert policy.is_authorized("file:///etc/passwd") is False
        assert policy.is_authorized("gopher://example.com/") is False
        assert policy.is_authorized("javascript:alert(1)") is False
        assert policy.is_authorized("data:text/html,<h1>hi</h1>") is False
        assert policy.is_authorized("ws://example.com/socket") is False

    def test_protocol_relative_reject(self):
        policy = PublicEgressPolicy(resolver=lambda h: ["93.184.216.34"])
        assert policy.is_authorized("//example.com/path") is False
        assert policy.is_authorized("//93.184.216.34/path") is False

    def test_trailing_dot_hostname_normalization(self):
        resolved_hosts = []

        def mock_resolver(host: str) -> list[str]:
            resolved_hosts.append(host)
            return ["93.184.216.34"]

        policy = PublicEgressPolicy(resolver=mock_resolver)
        assert policy.is_authorized("http://example.com./path") is True
        assert resolved_hosts == ["example.com"]

    def test_idna_normalization(self):
        resolved_hosts = []

        def mock_resolver(host: str) -> list[str]:
            resolved_hosts.append(host)
            return ["93.184.216.34"]

        policy = PublicEgressPolicy(resolver=mock_resolver)
        # 광주.kr -> xn--hc0bl34c.kr
        assert policy.is_authorized("http://광주.kr/notice") is True
        assert resolved_hosts == ["xn--hc0bl34c.kr"]


class TestPublicEgressPolicyDnsResolution:
    """Test DNS resolution handling, injection, and error cases."""

    def test_dns_all_public_allow(self):
        def mock_resolver(host: str) -> list[str]:
            return ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"]

        policy = PublicEgressPolicy(resolver=mock_resolver)
        assert policy.is_authorized("https://example.com/") is True

    def test_dns_mixed_public_private_reject(self):
        # Mixed IPv4 public and IPv4 private -> REJECT
        policy_v4 = PublicEgressPolicy(resolver=lambda h: ["93.184.216.34", "127.0.0.1"])
        assert policy_v4.is_authorized("https://example.com/") is False

        # Mixed IPv4 public and IPv4 RFC1918 -> REJECT
        policy_rfc = PublicEgressPolicy(resolver=lambda h: ["93.184.216.34", "10.0.0.1"])
        assert policy_rfc.is_authorized("https://example.com/") is False

        # Mixed IPv6 public and IPv6 loopback -> REJECT
        policy_v6 = PublicEgressPolicy(resolver=lambda h: ["2606:2800:220:1:248:1893:25c8:1946", "::1"])
        assert policy_v6.is_authorized("https://example.com/") is False

    def test_dns_resolver_error_reject(self):
        def failing_resolver(host: str) -> list[str]:
            raise socket.gaierror(-2, "Name or service not known")

        policy = PublicEgressPolicy(resolver=failing_resolver)
        assert policy.is_authorized("https://example.com/") is False

    def test_dns_empty_answers_reject(self):
        policy = PublicEgressPolicy(resolver=lambda h: [])
        assert policy.is_authorized("https://example.com/") is False

    def test_dns_malformed_ip_answer_reject(self):
        policy = PublicEgressPolicy(resolver=lambda h: ["not-an-ip"])
        assert policy.is_authorized("https://example.com/") is False

    def test_alias_egress_policy(self):
        assert EgressPolicy is PublicEgressPolicy


class TestFirecrawlServiceEndpointValidation:
    """Test provider service endpoint validation (Boundary B)."""

    def test_default_official_endpoint_allowed(self):
        ok, reason = is_valid_firecrawl_service_endpoint("https://api.firecrawl.dev")
        assert ok is True
        assert reason == ""

        ok2, _ = is_valid_firecrawl_service_endpoint("https://api.firecrawl.dev/")
        assert ok2 is True

        ok3, _ = is_valid_firecrawl_service_endpoint("https://api.firecrawl.dev:443")
        assert ok3 is True

    def test_arbitrary_service_endpoint_rejected(self):
        ok, reason = is_valid_firecrawl_service_endpoint("https://evil.example.com")
        assert ok is False
        assert "not the approved official endpoint" in reason

        ok2, _ = is_valid_firecrawl_service_endpoint("http://api.firecrawl.dev")  # http not https
        assert ok2 is False

        ok3, _ = is_valid_firecrawl_service_endpoint("https://api.firecrawl.dev:8443")  # non-standard port
        assert ok3 is False

        ok4, _ = is_valid_firecrawl_service_endpoint("http://169.254.169.254")
        assert ok4 is False

        ok5, _ = is_valid_firecrawl_service_endpoint("http://localhost:8080")
        assert ok5 is False

    def test_test_endpoint_seam_allowed_when_enabled(self):
        ok, _ = is_valid_firecrawl_service_endpoint(
            "http://localhost:8080", allow_test_endpoint=True
        )
        assert ok is True

        ok2, _ = is_valid_firecrawl_service_endpoint(
            "http://127.0.0.1:9999", allow_test_endpoint=True
        )
        assert ok2 is True

        ok3, _ = is_valid_firecrawl_service_endpoint(
            "http://[::1]:9999", allow_test_endpoint=True
        )
        assert ok3 is True

    def test_test_endpoint_seam_still_rejects_external_hosts(self):
        for endpoint in (
            "https://evil.example.com",
            "https://example.com:8443",
            "http://10.0.0.1:8080",
            "http://169.254.169.254",
        ):
            ok, reason = is_valid_firecrawl_service_endpoint(
                endpoint, allow_test_endpoint=True
            )
            assert ok is False
            assert "loopback" in reason.lower()

    def test_service_endpoint_invalid_port_fails_closed(self):
        for endpoint in (
            "http://localhost:0",
            "http://localhost:65536",
            "http://localhost:not-a-port",
        ):
            ok, _ = is_valid_firecrawl_service_endpoint(
                endpoint, allow_test_endpoint=True
            )
            assert ok is False


class TestLimitationDeclaration:
    """Verify explicit documentation of TOCTOU / DNS rebinding limitation."""

    def test_rebinding_limitation_constant(self):
        assert FULL_REBINDING_PREVENTION is False
