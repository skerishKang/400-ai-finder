"""Site profiles — site-specific configuration for AI-finder.

Each site profile captures the metadata, crawl strategy, and domain-specific
knowledge needed to ingest a target website (government, university, etc.)

Profiles are stored as YAML files under ``configs/sites/`` and loaded via
the ``SiteProfileLoader``.
"""

from .site_profile import SiteProfile, SiteProfileLoader, load_profile, list_profiles

__all__ = ["SiteProfile", "SiteProfileLoader", "load_profile", "list_profiles"]
