"""Real-site compatibility diagnostics for AI-finder.

Provides tools to diagnose fetch compatibility with institutional/governmental
websites that may use legacy CMS, PHP boards, JS menus, frames, WAF, etc.
"""

from .site_diagnostics import SiteDiagnostics, run_diagnostics

__all__ = ["SiteDiagnostics", "run_diagnostics"]
