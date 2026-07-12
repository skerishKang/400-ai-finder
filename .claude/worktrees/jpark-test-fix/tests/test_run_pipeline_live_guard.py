"""Tests for scripts/run_pipeline.py --allow-live guard.

All tests use fakes/monkeypatch — no real HTTP calls, API keys, or live providers.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ------------------------------------------------------------------
# Track PipelineRunner construction calls across tests
# ------------------------------------------------------------------

# Shared mutable dict that gets cleared per-test and populated by FakePipelineRunner.
CALLS: dict[str, Any] = {}


class FakePipelineRunner:
    """Stand-in for PipelineRunner that never touches real providers."""

    def __init__(self, **kwargs: Any) -> None:
        CALLS["init"] = dict(kwargs)

    def run(self, **kwargs: Any) -> dict[str, Any]:
        CALLS["run"] = dict(kwargs)
        return {"ok": True, "steps": [], "answer_markdown": ""}


@pytest.fixture(autouse=True)
def _clear_calls() -> None:
    CALLS.clear()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove env vars that could influence provider selection."""
    monkeypatch.delenv("AI_FINDER_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AI_FINDER_FETCH_PROVIDER", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _fake_pipeline_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace PipelineRunner with FakePipelineRunner so no real execution occurs."""
    from scripts.run_pipeline import PipelineRunner as _RealPipelineRunner

    monkeypatch.setattr(
        "scripts.run_pipeline.PipelineRunner",
        FakePipelineRunner,
    )


@pytest.fixture(autouse=True)
def _fake_output_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid creating real timestamped directories."""
    monkeypatch.setattr(
        "scripts.run_pipeline.make_default_output_dir",
        lambda: "/tmp/fake-output",
    )


# ------------------------------------------------------------------
# Helper: invoke main() with argv and capture result
# ------------------------------------------------------------------


def _run_main(argv: list[str]) -> tuple[int | str, str, str]:
    """Run run_pipeline.main() with given argv and capture exit / stdout / stderr.

    Returns (exit_code, stdout, stderr).
    """
    import io
    import sys as _sys

    import scripts.run_pipeline as rp

    old_argv = _sys.argv
    old_stdout = _sys.stdout
    old_stderr = _sys.stderr

    _sys.argv = argv
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    _sys.stdout = stdout_buf
    _sys.stderr = stderr_buf

    exit_code: int | str = 0
    try:
        rp.main()
    except SystemExit as exc:
        exit_code = exc.code if exc.code is not None else 0
    finally:
        _sys.argv = old_argv
        _sys.stdout = old_stdout
        _sys.stderr = old_stderr

    return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_run_pipeline_blocks_default_fetch_without_allow_live() -> None:
    """Default fetch_provider=None is live-capable; must be blocked."""
    exit_code, _, stderr = _run_main(
        [
            "run_pipeline.py",
            "--url", "https://example.com",
            "--query", "hello",
        ]
    )

    assert exit_code == 2, (
        f"Expected SystemExit(2), got {exit_code}"
    )
    assert "--allow-live" in stderr or "allow-live" in stderr, (
        f"stderr should mention --allow-live: {stderr}"
    )
    assert "run_pipeline.py may execute live" in stderr
    assert CALLS.get("run") is None, "PipelineRunner.run() should not have been called"


def test_run_pipeline_allows_mock_fetch_without_allow_live() -> None:
    """--provider mock --fetch-provider mock is the safe offline path."""
    exit_code, _, _ = _run_main(
        [
            "run_pipeline.py",
            "--url", "https://example.com",
            "--query", "hello",
            "--fetch-provider", "mock",
        ]
    )

    assert exit_code == 0, f"Expected success, got exit code {exit_code}"
    assert CALLS.get("run") is not None, "PipelineRunner.run() should have been called"
    init_kwargs = CALLS.get("init", {})
    assert init_kwargs.get("provider") == "mock"
    assert init_kwargs.get("fetch_provider") == "mock"


def test_run_pipeline_allows_stub_llm_mock_fetch_without_allow_live() -> None:
    """--provider stub --fetch-provider mock is also safe."""
    exit_code, _, _ = _run_main(
        [
            "run_pipeline.py",
            "--url", "https://example.com",
            "--query", "hello",
            "--provider", "stub",
            "--fetch-provider", "mock",
        ]
    )

    assert exit_code == 0, f"Expected success, got exit code {exit_code}"
    assert CALLS.get("run") is not None
    init_kwargs = CALLS.get("init", {})
    assert init_kwargs.get("provider") == "stub"
    assert init_kwargs.get("fetch_provider") == "mock"


def test_run_pipeline_blocks_live_llm_provider_without_allow_live() -> None:
    """--provider openai_compatible is live-capable even with --fetch-provider mock."""
    exit_code, _, stderr = _run_main(
        [
            "run_pipeline.py",
            "--url", "https://example.com",
            "--query", "hello",
            "--provider", "openai_compatible",
            "--fetch-provider", "mock",
        ]
    )

    assert exit_code == 2, f"Expected SystemExit(2), got {exit_code}"
    assert "--allow-live" in stderr
    assert CALLS.get("run") is None, "PipelineRunner.run() should not have been called"


def test_run_pipeline_blocks_firecrawl_fetch_without_allow_live() -> None:
    """--fetch-provider firecrawl is live-capable; blocked regardless of API key."""
    exit_code, _, stderr = _run_main(
        [
            "run_pipeline.py",
            "--url", "https://example.com",
            "--query", "hello",
            "--fetch-provider", "firecrawl",
        ]
    )

    assert exit_code == 2, f"Expected SystemExit(2), got {exit_code}"
    assert "--allow-live" in stderr
    assert CALLS.get("run") is None


def test_run_pipeline_allow_live_permits_default_fetch_path() -> None:
    """--allow-live permits default fetch_provider=None path."""
    exit_code, _, _ = _run_main(
        [
            "run_pipeline.py",
            "--url", "https://example.com",
            "--query", "hello",
            "--allow-live",
        ]
    )

    assert exit_code == 0, f"Expected success, got exit code {exit_code}"
    assert CALLS.get("run") is not None, "PipelineRunner.run() should have been called"
    init_kwargs = CALLS.get("init", {})
    assert init_kwargs.get("fetch_provider") is None


def test_run_pipeline_allow_live_permits_requests_fetch() -> None:
    """--allow-live --fetch-provider requests should be permitted."""
    exit_code, _, _ = _run_main(
        [
            "run_pipeline.py",
            "--url", "https://example.com",
            "--query", "hello",
            "--fetch-provider", "requests",
            "--allow-live",
        ]
    )

    assert exit_code == 0, f"Expected success, got exit code {exit_code}"
    assert CALLS.get("run") is not None


def test_run_pipeline_allow_live_permits_live_llm() -> None:
    """--allow-live --provider openai_compatible should be permitted."""
    exit_code, _, _ = _run_main(
        [
            "run_pipeline.py",
            "--url", "https://example.com",
            "--query", "hello",
            "--provider", "openai_compatible",
            "--fetch-provider", "mock",
            "--allow-live",
        ]
    )

    assert exit_code == 0, f"Expected success, got exit code {exit_code}"
    assert CALLS.get("run") is not None
    init_kwargs = CALLS.get("init", {})
    assert init_kwargs.get("provider") == "openai_compatible"
