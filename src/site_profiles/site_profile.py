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

DEFAULT_CRAWL_RULES: dict[str, Any] = {
    "max_depth": 3,
    "max_pages": 200,
    "include_documents": True,
    "respect_robots": True,
}

DEFAULT_DOCUMENT_EXTENSIONS: list[str] = [
    "pdf", "hwp", "hwpx", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip",
]

DEFAULT_BOARD_PATTERNS: list[str] = [
    "board", "bbs", "list", "view", "article", "notice",
]


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
    """

    def __init__(self, configs_dir: str | Path | None = None) -> None:
        self._dir = Path(configs_dir) if configs_dir else CONFIGS_DIR

    def load_by_id(self, site_id: str) -> SiteProfile:
        """Load a profile by its site_id.

        Looks for ``<site_id>.yml`` inside the configs directory.

        Raises:
            FileNotFoundError: If the profile file does not exist.
            ValueError: If the YAML is malformed or required fields are missing.
        """
        path = self._dir / f"{site_id}.yml"
        return self.load_file(path)

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


def load_profile(site_id_or_path: str) -> SiteProfile:
    """One-shot convenience function.

    Tries ``site_id_or_path`` as a site_id first (looks in ``configs/sites/``).
    If not found or if it looks like a file path, tries as a file path.

    Args:
        site_id_or_path: Either a site_id (e.g. ``bukgu_gwangju``) or
            a file path to a YAML profile.

    Returns:
        A ``SiteProfile`` instance.

    Raises:
        FileNotFoundError: If neither resolution succeeds.
    """
    loader = SiteProfileLoader()

    # Try as site_id
    profile_path = CONFIGS_DIR / f"{site_id_or_path}.yml"
    if profile_path.exists():
        return loader.load_file(profile_path)

    # Try as a file path
    path = Path(site_id_or_path)
    if path.exists():
        return loader.load_file(path)

    # Try nested
    for p in [Path(site_id_or_path), CONFIGS_DIR / f"{site_id_or_path}.yml"]:
        if p.exists():
            return loader.load_file(p)

    raise FileNotFoundError(
        f"Cannot find site profile: {site_id_or_path} "
        f"(checked as site_id and as file path)"
    )
