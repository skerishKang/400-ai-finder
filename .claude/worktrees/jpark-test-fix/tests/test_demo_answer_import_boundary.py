"""Import boundary tests for scripts.demo_answer.

These tests lock that importing the CLI module is network-free and does not
execute demo answer or pipeline paths. Live execution belongs behind explicit
CLI invocation only.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import Mock

import pytest
import requests

from src.fetch.firecrawl_provider import FirecrawlFetchProvider
from src.fetch.requests_provider import RequestsFetchProvider
from src.pipeline.pipeline_runner import PipelineRunner


def test_importing_demo_answer_is_network_free(monkeypatch) -> None:
    """Importing scripts.demo_answer must not execute fetch/network/pipeline paths."""
    requests_get = Mock(
        side_effect=AssertionError("requests.get() must not run during import")
    )
    requests_fetch = Mock(
        side_effect=AssertionError(
            "RequestsFetchProvider.fetch() must not run during import"
        )
    )
    firecrawl_fetch = Mock(
        side_effect=AssertionError(
            "FirecrawlFetchProvider.fetch() must not run during import"
        )
    )
    pipeline_run = Mock(
        side_effect=AssertionError("PipelineRunner.run() must not run during import")
    )

    monkeypatch.setattr(requests, "get", requests_get)
    monkeypatch.setattr(RequestsFetchProvider, "fetch", requests_fetch)
    monkeypatch.setattr(FirecrawlFetchProvider, "fetch", firecrawl_fetch)
    monkeypatch.setattr(PipelineRunner, "run", pipeline_run)
    monkeypatch.delenv("AI_FINDER_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AI_FINDER_FETCH_PROVIDER", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    sys.modules.pop("scripts.demo_answer", None)

    module = importlib.import_module("scripts.demo_answer")

    assert module is not None
    requests_get.assert_not_called()
    requests_fetch.assert_not_called()
    firecrawl_fetch.assert_not_called()
    pipeline_run.assert_not_called()
