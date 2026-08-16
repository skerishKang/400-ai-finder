"""SSRF-safe public egress policy for live URL acquisition (#1295).

This module provides a provider-independent public egress policy that enforces
network safety boundaries before any network socket connection is established:
- Allowed schemes: http, https only.
- Strict fail-closed parsing: malformed URLs, empty/missing host, userinfo/credentials,
  malformed IPv6 brackets, invalid ports (must be 1..65535).
- Prohibited IP spaces (IPv4 & IPv6): localhost, loopback, private (RFC 1918, RFC 4193 ULA),
  link-local, cloud metadata endpoints (169.254.169.254, fd00:ec2::254), unspecified,
  multicast, broadcast, carrier-grade NAT (100.64.0.0/10), documentation / test networks.
- IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1, ::ffff:93.184.216.34): mapped IPv4
  is extracted and evaluated against all IPv4 rules.
- Hostname normalization: trailing dot handling (FQDN e.g. example.com. -> example.com),
  IDNA normalization (e.g. 광주.kr -> xn--i20b41k.kr).
- DNS hostname resolution: resolves all A and AAAA records via an injectable resolver;
  all resolved IP addresses must be public; mixed public/private results, resolver errors,
  or empty answers fail closed (rejected).
- Injectable / monkeypatchable DNS resolver for 100% offline, deterministic testing.

DNS REBINDING / TOCTOU LIMITATION:
FULL_REBINDING_PREVENTION = False
This policy performs pre-dispatch DNS resolution and address verification. Without socket-level
address pinning or verified-address connection binding, a DNS server with TTL=0 could theoretically
return a public IP during policy resolution and a private IP during socket connection. Full DNS
rebinding prevention is explicitly limited and not claimed.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Callable
from urllib.parse import urlsplit


FULL_REBINDING_PREVENTION: bool = False

# Explicit prohibited IPv4 networks (RFCs 1122, 1918, 2544, 3927, 5737, 5771, 6598, 6890, 7526)
PROHIBITED_IPV4_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.ip_network("0.0.0.0/8"),          # "This" network / unspecified
    ipaddress.ip_network("10.0.0.0/8"),         # Private (RFC 1918)
    ipaddress.ip_network("100.64.0.0/10"),      # Carrier-grade NAT (RFC 6598)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback (RFC 1122)
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local / Cloud metadata (RFC 3927)
    ipaddress.ip_network("172.16.0.0/12"),      # Private (RFC 1918)
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments (RFC 6890)
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1 (RFC 5737)
    ipaddress.ip_network("192.88.99.0/24"),     # 6to4 Relay Anycast (RFC 7526)
    ipaddress.ip_network("192.168.0.0/16"),     # Private (RFC 1918)
    ipaddress.ip_network("198.18.0.0/15"),      # Benchmarking (RFC 2544)
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2 (RFC 5737)
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3 (RFC 5737)
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast (RFC 5771)
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved / Future use (RFC 1112)
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
)

# Explicit prohibited IPv6 networks (RFCs 2928, 3056, 3849, 3879, 4193, 4291, 6666)
PROHIBITED_IPV6_NETWORKS: tuple[ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("::/128"),             # Unspecified (RFC 4291)
    ipaddress.ip_network("::1/128"),            # Loopback (RFC 4291)
    ipaddress.ip_network("100::/64"),           # Discard prefix (RFC 6666)
    ipaddress.ip_network("2001::/23"),          # IETF Protocol Assignments (RFC 2928)
    ipaddress.ip_network("2001:db8::/32"),      # Documentation (RFC 3849)
    ipaddress.ip_network("2002::/16"),          # 6to4 (RFC 3056)
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address ULA / Private (RFC 4193)
    ipaddress.ip_network("fe80::/10"),          # Link-Local (RFC 4291)
    ipaddress.ip_network("fec0::/10"),          # Site-Local deprecated (RFC 3879)
    ipaddress.ip_network("ff00::/8"),           # Multicast (RFC 4291)
)

PROHIBITED_HOST_SUFFIXES: tuple[str, ...] = (
    "localhost",
    "localdomain",
    "local",
    "internal",
    "lan",
    "home",
    "corp",
    "intranet",
    "onion",
    "invalid",
)

ResolverFunc = Callable[[str], list[str]]


def default_dns_resolver(hostname: str) -> list[str]:
    """Default DNS resolver using standard socket.getaddrinfo.

    Returns a list of resolved IP address strings (A and AAAA records).
    Returns [] on DNS resolution failure (gaierror, herror, etc.).
    """
    try:
        results = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        ips: list[str] = []
        for res in results:
            sockaddr = res[4]
            if sockaddr and sockaddr[0]:
                ips.append(sockaddr[0])
        # Preserve order while deduplicating
        return list(dict.fromkeys(ips))
    except (socket.gaierror, socket.herror, OSError, ValueError):
        return []


def is_safe_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address | str) -> bool:
    """Return True if *ip* is a valid, globally routable public IP address."""
    if isinstance(ip, str):
        try:
            ip = ipaddress.ip_address(ip)
        except ValueError:
            return False

    # Special handling: IPv4-mapped IPv6 (::ffff:0:0/96)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return is_safe_public_ip(ip.ipv4_mapped)

    if isinstance(ip, ipaddress.IPv4Address):
        if not ip.is_global:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_unspecified
            or ip.is_multicast
            or ip.is_reserved
        ):
            return False
        for net in PROHIBITED_IPV4_NETWORKS:
            if ip in net:
                return False
        return True

    if isinstance(ip, ipaddress.IPv6Address):
        if not ip.is_global:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_unspecified
            or ip.is_multicast
            or ip.is_reserved
        ):
            return False
        for net in PROHIBITED_IPV6_NETWORKS:
            if ip in net:
                return False
        return True

    return False


class PublicEgressPolicy:
    """SSRF-safe public egress policy.

    Enforces that URLs target safe public HTTP/HTTPS destinations.
    """

    def __init__(self, resolver: ResolverFunc | None = None) -> None:
        self._resolver: ResolverFunc = resolver if resolver is not None else default_dns_resolver

    @property
    def resolver(self) -> ResolverFunc:
        return self._resolver

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate *url* against the public egress policy.

        Returns:
            (True, "") if allowed.
            (False, "<reason>") if rejected.
        """
        if not url or not isinstance(url, str):
            return False, "Empty or non-string URL"

        url_clean = url.strip()
        if not url_clean:
            return False, "Empty URL"

        try:
            parsed = urlsplit(url_clean)
        except ValueError as exc:
            return False, f"Malformed URL: {exc}"

        # 1. Scheme check: only http and https allowed
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            return False, f"Prohibited scheme: '{scheme}' (only http and https allowed)"

        # 2. Authority / Netloc checks
        netloc = parsed.netloc
        if not netloc:
            return False, "Missing authority / netloc in URL"

        # Userinfo / credentials check
        if "@" in netloc or parsed.username is not None or parsed.password is not None:
            return False, "Prohibited userinfo / credentials in URL"

        # 3. Port check
        try:
            port = parsed.port
        except ValueError as exc:
            return False, f"Invalid port in URL: {exc}"

        if port is not None:
            if not (1 <= port <= 65535):
                return False, f"Port out of range (1..65535): {port}"

        # 4. Hostname extraction and normalization
        raw_hostname = parsed.hostname
        if not raw_hostname:
            return False, "Missing or empty hostname in URL"

        # Trailing dot normalization (DNS FQDN notation e.g. example.com. -> example.com)
        hostname = raw_hostname.rstrip(".")
        if not hostname:
            return False, "Invalid empty hostname after trailing dot removal"

        # IDNA normalization for internationalized domain names
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii").lower()
        except (UnicodeError, ValueError) as exc:
            return False, f"Invalid IDNA hostname: {exc}"

        if not ascii_hostname:
            return False, "Empty hostname after IDNA encoding"

        # 5. Check if hostname is an IP literal
        try:
            ip_obj = ipaddress.ip_address(ascii_hostname)
            is_ip = True
        except ValueError:
            is_ip = False

        if is_ip:
            if is_safe_public_ip(ip_obj):
                return True, ""
            return False, f"Prohibited IP address literal: {ascii_hostname}"

        # 6. Hostname checks (non-IP)
        if ascii_hostname in ("localhost", "ip6-localhost", "ip6-loopback"):
            return False, f"Prohibited localhost name: {ascii_hostname}"

        for suffix in PROHIBITED_HOST_SUFFIXES:
            if ascii_hostname == suffix or ascii_hostname.endswith("." + suffix):
                return False, f"Prohibited reserved local domain suffix: .{suffix}"

        # Check hostname syntax: labels cannot start/end with hyphen, max 63 per label, max 253 total
        if len(ascii_hostname) > 253:
            return False, "Hostname exceeds 253 characters"

        labels = ascii_hostname.split(".")
        for label in labels:
            if not label or len(label) > 63:
                return False, f"Invalid domain label: '{label}'"
            if label.startswith("-") or label.endswith("-"):
                return False, f"Domain label cannot start or end with hyphen: '{label}'"
            if not all(c.isalnum() or c == "-" or c == "_" for c in label):
                return False, f"Domain label contains invalid characters: '{label}'"

        # 7. DNS resolution check
        try:
            resolved_ips = self._resolver(ascii_hostname)
        except Exception as exc:
            return False, f"DNS resolution error for {ascii_hostname}: {exc}"

        if not resolved_ips:
            return False, f"DNS resolution returned no addresses for {ascii_hostname}"

        for ip_str in resolved_ips:
            try:
                ip_addr = ipaddress.ip_address(ip_str)
            except ValueError:
                return False, f"DNS resolution returned malformed IP: '{ip_str}'"

            if not is_safe_public_ip(ip_addr):
                return False, f"DNS resolution returned prohibited IP address: {ip_str}"

        return True, ""

    def is_authorized(self, url: str) -> bool:
        """Return True iff *url* is safe to acquire under this public egress policy.

        Never raises exceptions; fails closed on any error.
        """
        try:
            allowed, _ = self.validate_url(url)
            return allowed
        except Exception:
            return False


EgressPolicy = PublicEgressPolicy


OFFICIAL_FIRECRAWL_HOST = "api.firecrawl.dev"


def is_valid_firecrawl_service_endpoint(
    base_url: str,
    allow_test_endpoint: bool = False,
) -> tuple[bool, str]:
    """Validate Firecrawl provider service endpoint URL.

    Bearer API keys are transmitted to this socket endpoint. Ordinary/default
    operation only permits the reviewed official Firecrawl service endpoint
    (https://api.firecrawl.dev). An unapproved arbitrary/private/third-party
    endpoint is rejected. ``allow_test_endpoint=True`` is deliberately narrow:
    it permits only explicit loopback test endpoints (localhost, 127.0.0.0/8,
    or ::1) and never turns endpoint validation off.
    """
    if not base_url or not isinstance(base_url, str):
        return False, "Empty or non-string service endpoint URL"

    try:
        parsed = urlsplit(base_url.strip())
    except Exception as exc:
        return False, f"Malformed service endpoint URL: {exc}"

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"Prohibited service endpoint scheme: '{scheme}'"

    if "@" in (parsed.netloc or "") or parsed.username or parsed.password:
        return False, "Prohibited userinfo in service endpoint URL"

    hostname = (parsed.hostname or "").rstrip(".").lower()
    if not hostname:
        return False, "Missing hostname in service endpoint URL"

    try:
        port = parsed.port
    except ValueError as exc:
        return False, f"Invalid service endpoint port: {exc}"

    if port is not None and not (1 <= port <= 65535):
        return False, f"Service endpoint port out of range (1..65535): {port}"

    # Official reviewed Firecrawl service endpoint.
    if scheme == "https" and hostname == OFFICIAL_FIRECRAWL_HOST:
        if port is None or port == 443:
            return True, ""
        return False, "Firecrawl official endpoint only permits the default HTTPS port 443"

    if allow_test_endpoint:
        # Explicit local/test seam only. Do not resolve arbitrary hostnames here:
        # the seam is intentionally restricted to syntactically obvious
        # loopback destinations rather than becoming a general endpoint bypass.
        if hostname == "localhost":
            return True, ""
        try:
            endpoint_ip = ipaddress.ip_address(hostname)
        except ValueError:
            endpoint_ip = None
        if endpoint_ip is not None and endpoint_ip.is_loopback:
            return True, ""
        return False, (
            f"Firecrawl test endpoint '{base_url}' is not a loopback-only local test endpoint"
        )

    return False, (
        f"Firecrawl service endpoint '{base_url}' is not the approved official endpoint "
        f"(https://{OFFICIAL_FIRECRAWL_HOST}) and loopback test endpoint seam is not enabled"
    )
