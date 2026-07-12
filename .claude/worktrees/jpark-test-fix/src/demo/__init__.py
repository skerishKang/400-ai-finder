"""Demo module — grounded answer runner for site profile-based Q&A.

Provides a ``SiteDemoRunner`` that loads a site profile, runs the full
pipeline (homepage_map → document_index → enrich → search → answer),
and returns a structured result with sources.
"""

from .site_demo_runner import SiteDemoRunner, run_demo

__all__ = ["SiteDemoRunner", "run_demo"]
