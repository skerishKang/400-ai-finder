"""Crawl strategy router for AI-finder.

Takes site diagnostics results and produces a recommended crawl strategy
(provider, crawl order, feature flags, risk flags).
"""

from .strategy_router import StrategyRouter, route_strategy

__all__ = ["StrategyRouter", "route_strategy"]
