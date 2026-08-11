"""SiteProfile and SiteProfileLoader — site-specific configuration.

Each site profile captures the metadata, crawl strategy, and domain-specific
knowledge needed to ingest a target website. Profiles are stored as YAML
files under ``configs/sites/<site_id>.yml``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from src.config.constants import (
    PROFILE_DOCUMENT_EXTENSIONS,
    PROFILE_DEFAULT_BOARD_PATTERNS,
    PROFILE_DEFAULT_CRAWL_RULES,
)
from src.site_profiles.sitespec import (
    ID_PATTERN,
    SiteSpecNotFoundError,
    SiteSpecResolver,
    iter_sitespec_paths,
)

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs" / "sites"

REQUIRED_FIELDS = {
    "site_id": str,
    "name": str,
    "base_url": str,
}

DEFAULT_CRAWL_RULES: dict[str, Any] = dict(PROFILE_DEFAULT_CRAWL_RULES)

DEFAULT_DOCUMENT_EXTENSIONS: list[str] = list(PROFILE_DOCUMENT_EXTENSIONS)

DEFAULT_BOARD_PATTERNS: list[str] = list(PROFILE_DEFAULT_BOARD_PATTERNS)


# ------------------------------------------------------------------
# Data class
# ------------------------------------------------------------------


class SiteProfile:
    """Site-specific configuration profile.

    Attributes:
        site_id:         Unique identifier (e.g. ``bukgu_gwangju``).
        name:            Human-readable site name.
        base_url:        The root URL of the target site.
        allowed_domains: List of domains considered same-site.
        preferred_fetch_provider: Default fetch provider (e.g. ``requests``).
        classification:  Diagnostics classification label.
        important_keywords: List of Korean keywords relevant to the site.
        document_extensions: File extensions to treat as documents.
        board_patterns:  URL patterns that indicate board/list pages.
        fallback_strategy: Ordered list of fallback strategies.
        crawl_rules:     Dict with max_depth, max_pages, etc.
        notes:           Free-text notes about the site.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    # -- Required fields ------------------------------------------------

    @property
    def site_id(self) -> str:
        return str(self._data.get("site_id", ""))

    @property
    def name(self) -> str:
        return str(self._data.get("name", ""))

    @property
    def base_url(self) -> str:
        return str(self._data.get("base_url", ""))

    # -- Optional fields with defaults ----------------------------------

    @property
    def allowed_domains(self) -> list[str]:
        return list(self._data.get("allowed_domains", [self._extract_domain()]))

    @property
    def preferred_fetch_provider(self) -> str:
        return str(self._data.get("preferred_fetch_provider", "requests"))

    @property
    def classification(self) -> str:
        return str(self._data.get("classification", ""))

    @property
    def important_keywords(self) -> list[str]:
        return list(self._data.get("important_keywords", []))

    @property
    def document_extensions(self) -> list[str]:
        return list(
            self._data.get("document_extensions", DEFAULT_DOCUMENT_EXTENSIONS)
        )

    @property
    def board_patterns(self) -> list[str]:
        return list(self._data.get("board_patterns", DEFAULT_BOARD_PATTERNS))

    @property
    def fallback_strategy(self) -> list[str]:
        return list(self._data.get("fallback_strategy", []))

    @property
    def crawl_rules(self) -> dict[str, Any]:
        rules = dict(DEFAULT_CRAWL_RULES)
        rules.update(self._data.get("crawl_rules", {}))
        return rules

    @property
    def notes(self) -> str:
        return str(self._data.get("notes", ""))

    @property
    def synonym_dictionary(self) -> dict[str, list[str]]:
        """Optional site-specific synonym dictionary for retrieval expansion.

        Maps a normalized key (e.g. ``"민원"``) to a list of related
        retrieval terms (e.g. ``["종합민원", "온라인 민원", "민원서식"]``).

        The dictionary is **optional**. Profiles that omit
        ``synonym_dictionary`` return an empty dict. Invalid entries
        (non-string keys, non-list values, blank/duplicate/non-string
        items) are silently filtered out so that partial/legacy data
        does not break loaders.

        These values are retrieval candidates only. They are not answers
        and must not contain person names, incumbent officeholders, or
        volatile facts.
        """
        raw = self._data.get("synonym_dictionary", {})
        if not isinstance(raw, dict):
            return {}

        result: dict[str, list[str]] = {}
        for key, values in raw.items():
            if not isinstance(key, str):
                continue
            key = key.strip()
            if not key:
                continue
            if not isinstance(values, list):
                continue

            cleaned_values: list[str] = []
            seen: set[str] = set()
            for value in values:
                if not isinstance(value, str):
                    continue
                value = value.strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                cleaned_values.append(value)

            if cleaned_values:
                result[key] = cleaned_values

        return result

    @property
    def crawl_filters(self) -> dict[str, list[str]]:
        """Optional site-specific crawl filters for URL allow/deny decisions.

        Returns a dictionary containing 'allow_patterns', 'deny_patterns',
        and 'protected_patterns' list of strings. Missing or invalid
        properties fallback safely to empty lists.
        """
        raw = self._data.get("crawl_filters")
        if not isinstance(raw, dict):
            return {}

        supported_keys = ("allow_patterns", "deny_patterns", "protected_patterns")
        result: dict[str, list[str]] = {}

        for key in supported_keys:
            val = raw.get(key)
            if not isinstance(val, list):
                result[key] = []
                continue

            cleaned_values: list[str] = []
            seen: set[str] = set()
            for item in val:
                if not isinstance(item, str):
                    continue
                item_stripped = item.strip()
                if not item_stripped or item_stripped in seen:
                    continue
                seen.add(item_stripped)
                cleaned_values.append(item_stripped)

            result[key] = cleaned_values

        return result


    def _extract_domain(self) -> str:
        """Extract a domain from base_url as a fallback for allowed_domains."""
        m = re.search(r"https?://([^:/]+)", self.base_url)
        return m.group(1) if m else ""

    def to_dict(self) -> dict[str, Any]:
        """Convert the profile to a plain JSON-serializable dict."""
        return {
            "site_id": self.site_id,
            "name": self.name,
            "base_url": self.base_url,
            "allowed_domains": self.allowed_domains,
            "preferred_fetch_provider": self.preferred_fetch_provider,
            "classification": self.classification,
            "important_keywords": self.important_keywords,
            "document_extensions": self.document_extensions,
            "board_patterns": self.board_patterns,
            "fallback_strategy": self.fallback_strategy,
            "crawl_rules": self.crawl_rules,
            "notes": self.notes,
            "synonym_dictionary": self.synonym_dictionary,
        }

    def match_url(self, url: str) -> bool:
        """Check if a URL belongs to this site's allowed domains."""
        for domain in self.allowed_domains:
            if domain in url:
                return True
        return False


# ------------------------------------------------------------------
# Loader
# ------------------------------------------------------------------


class SiteProfileLoader:
    """Load ``SiteProfile`` objects from YAML files.

    Args:
        configs_dir: Directory containing ``<site_id>.yml`` files.
            Defaults to ``configs/sites/`` relative to this file.
        sitespec_dir: Directory containing ``*.sitespec.json`` files for
            dual-read identifier resolution (#1225-D1). Defaults to
            ``configs_dir`` when not given.
        sitespec_resolver: Optional pre-built :class:`SiteSpecResolver`.
            When provided, it is used directly; otherwise the resolver is
            constructed lazily on the first identifier lookup (never in the
            constructor), so YAML-only directories keep working unchanged.

    Dual-read behavior (#1225-D1):

    * identifier → SiteSpec resolver → canonical SiteSpec →
      ``runtime.python_profile`` → ``<python_profile>.yml``
    * identifiers with no SiteSpec fall back to the historical exact-YAML
      lookup ``<identifier>.yml`` (transitional, safe for unmigrated
      profiles)
    * once a SiteSpec resolves an identifier, the resolver is the authority:
      a missing/malformed ``runtime.python_profile`` fails closed and never
      falls back to ``<identifier>.yml``
    """

    def __init__(
        self,
        configs_dir: str | Path | None = None,
        *,
        sitespec_dir: str | Path | None = None,
        sitespec_resolver: SiteSpecResolver | None = None,
    ) -> None:
        self._dir = Path(configs_dir) if configs_dir else CONFIGS_DIR
        self._sitespec_dir = (
            Path(sitespec_dir) if sitespec_dir is not None else self._dir
        )
        self._resolver = sitespec_resolver
        self._resolver_checked = sitespec_resolver is not None

    def _get_sitespec_resolver(self) -> SiteSpecResolver | None:
        """Return the SiteSpec resolver, or None for YAML-only directories.

        The resolver is constructed lazily on first use (never in the
        constructor) so existing ``SiteProfileLoader()`` /
        ``SiteProfileLoader(temp_dir)`` calls with YAML-only directories are
        unaffected. A directory that contains no ``*.sitespec.json`` files
        caches ``None``; a directory that contains SiteSpecs loads them
        fail-closed (malformed sets raise ``SiteSpecLoadError``).
        """
        if self._resolver_checked:
            return self._resolver
        self._resolver_checked = True
        if not iter_sitespec_paths(self._sitespec_dir):
            self._resolver = None
            return None
        self._resolver = SiteSpecResolver(self._sitespec_dir)
        return self._resolver

    def load_by_id(self, site_id: str) -> SiteProfile:
        """Load a profile by its site_id (canonical or legacy alias).

        Identifier resolution (#1225-D1):

        * ``requested identifier → SiteSpec resolver → canonical SiteSpec
          → runtime.python_profile → <python_profile>.yml``
        * if the identifier has no SiteSpec, the historical exact-YAML
          lookup ``<site_id>.yml`` is preserved (transitional)
        * once SiteSpec resolution succeeds, ``runtime.python_profile`` is
          authoritative; a missing/malformed projection fails closed and
          never falls back to ``<site_id>.yml``

        Raises:
            FileNotFoundError: If no profile can be resolved (unknown
                identifier and no exact YAML profile).
            ValueError: If a resolved SiteSpec's ``runtime.python_profile``
                is missing or malformed (configuration error).
        """
        path = self._resolve_profile_path(site_id)
        return self.load_file(path)

    def _resolve_profile_path(self, site_id: str) -> Path:
        """Map an identifier to the YAML profile path to load.

        ``load_by_id`` is an **identifier-only boundary**: the value is
        normalized/validated with the shared ``ID_PATTERN`` semantics before
        any SiteSpec lookup or path construction. Malformed, empty, or
        path-like values fail closed (``FileNotFoundError``) and can never
        contribute to a filesystem path — only a valid identifier that
        misses the SiteSpec may use the transitional exact-YAML lookup.
        """
        if not isinstance(site_id, str):
            raise FileNotFoundError(f"Site profile not found: {site_id!r}")
        identifier = site_id.strip()
        if not ID_PATTERN.match(identifier):
            raise FileNotFoundError(f"Site profile not found: {site_id!r}")
        resolver = self._get_sitespec_resolver()
        if resolver is not None:
            try:
                metadata = resolver.resolve_with_metadata(identifier)
            except SiteSpecNotFoundError:
                # Transitional: a *valid* identifier with no SiteSpec. Keep
                # the historical exact-YAML lookup (Section B of #1225-D1).
                pass
            else:
                python_profile = self._python_profile_from_spec(
                    metadata["spec"], identifier
                )
                return self._dir / f"{python_profile}.yml"
        return self._dir / f"{identifier}.yml"

    @staticmethod
    def _python_profile_from_spec(spec: dict[str, Any], identifier: str) -> str:
        """Extract ``runtime.python_profile`` from a resolved SiteSpec.

        Raises:
            ValueError: If ``runtime`` is missing/not a mapping or
                ``python_profile`` is missing, empty, non-string, or not a
                safe identifier. SiteSpec projection is the canonical
                authority once resolution succeeds — callers must not fall
                back to the requested-ID YAML after this raises.
        """
        runtime = spec.get("runtime")
        if not isinstance(runtime, dict):
            raise ValueError(
                f"SiteSpec for {identifier!r} has no valid 'runtime' mapping: "
                f"cannot resolve runtime.python_profile"
            )
        python_profile = runtime.get("python_profile")
        if (
            not isinstance(python_profile, str)
            or not python_profile.strip()
            or not ID_PATTERN.match(python_profile)
        ):
            raise ValueError(
                f"SiteSpec for {identifier!r} has invalid runtime.python_profile "
                f"{python_profile!r}: cannot project to a YAML profile"
            )
        return python_profile

    def load_file(self, path: str | Path) -> SiteProfile:
        """Load a profile from an explicit file path.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the YAML is malformed or required fields are missing.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Site profile not found: {p}")

        if yaml is None:
            raise ImportError("PyYAML is required to load site profiles.")

        with open(p, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {p}: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Profile file {p} must contain a YAML mapping.")

        self._validate(data, str(p))
        return SiteProfile(data)

    def list_ids(self) -> list[str]:
        """List all available site profile IDs (without ``.yml`` extension)."""
        if not self._dir.exists():
            return []
        return sorted(
            f.stem for f in self._dir.iterdir() if f.suffix == ".yml"
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(data: dict[str, Any], source: str) -> None:
        """Validate required fields and basic types.

        Raises:
            ValueError: On missing or wrong-type fields.
        """
        for field, expected_type in REQUIRED_FIELDS.items():
            if field not in data:
                raise ValueError(
                    f"Missing required field '{field}' in {source}"
                )
            if not isinstance(data[field], expected_type):
                raise ValueError(
                    f"Field '{field}' in {source} must be {expected_type.__name__}, "
                    f"got {type(data[field]).__name__}"
                )
            if not data[field]:
                raise ValueError(
                    f"Field '{field}' in {source} must not be empty"
                )

        # base_url must look like a URL
        base_url = data.get("base_url", "")
        if not base_url.startswith("http"):
            raise ValueError(
                f"Field 'base_url' in {source} must start with http:// or https://, "
                f"got: {base_url}"
            )


# ------------------------------------------------------------------
# Convenience
# ------------------------------------------------------------------


def list_profiles() -> list[dict[str, str]]:
    """List all available site profiles with basic metadata.

    Returns:
        A list of dicts, each with ``site_id``, ``name``, ``base_url``,
        and ``classification`` keys.
    """
    loader = SiteProfileLoader()
    profiles: list[dict[str, str]] = []
    for sid in loader.list_ids():
        try:
            p = loader.load_by_id(sid)
            profiles.append({
                "site_id": p.site_id,
                "name": p.name,
                "base_url": p.base_url,
                "classification": p.classification,
            })
        except Exception:
            continue
    return profiles


def load_profile(site_id_or_path: str) -> SiteProfile:
    """One-shot convenience function.

    Resolution priority:

    1. structurally explicit path (path separators, ``*.yml``/``*.yaml``)
       → loaded directly as a file path, never reinterpreted as an ID
    2. bare identifier (canonical ID, legacy alias, or unmigrated exact
       config YAML) → SiteSpec dual-read / exact config YAML resolution
    3. genuinely unknown bare identifier that matches an existing
       same-named extensionless filesystem file → historical
       explicit-file fallback (e.g. ``custom_local``)

    Canonical/legacy identifiers always win over same-named CWD files, so
    a stray ``bukgu`` file in the working directory can never hijack the
    legacy alias.

    Args:
        site_id_or_path: Either a site_id / legacy alias (e.g.
            ``bukgu_gwangju``, ``bukgu``) or a file path to a YAML profile.

    Returns:
        A ``SiteProfile`` instance.

    Raises:
        FileNotFoundError: If neither resolution succeeds.
    """
    loader = SiteProfileLoader()

    if _looks_like_file_path(site_id_or_path):
        return loader.load_file(site_id_or_path)

    try:
        return loader.load_by_id(site_id_or_path)
    except FileNotFoundError:
        # Historical extensionless-file compatibility: identifier resolution
        # already failed, so a same-named filesystem file may only be loaded
        # when the value itself is a safe bare identifier.
        if ID_PATTERN.match(site_id_or_path) and Path(site_id_or_path).exists():
            return loader.load_file(site_id_or_path)
        raise


def _looks_like_file_path(value: str) -> bool:
    """Return True when *value* is structurally an explicit file path.

    Site identifiers follow ``[a-z0-9][a-z0-9_-]*`` and never contain path
    separators or a YAML suffix. Any value with a separator or a YAML suffix
    is therefore unambiguous as a file path and is loaded directly. Bare
    identifiers (no separator, no suffix) are **never** treated as paths
    here — they go through identifier resolution first, so an extensionless
    CWD file cannot shadow a canonical SiteSpec identifier or legacy alias.
    """
    if "/" in value or "\\" in value:
        return True
    if value.endswith(".yml") or value.endswith(".yaml"):
        return True
    return False
