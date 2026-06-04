"""Live opt-in guard tests for scripts.demo_answer.

These tests verify that --allow-live is required for default/live execution
paths while --snapshot and --provider mock --fetch-provider mock remain
allowed without --allow-live. No network/API calls are made during these tests.
"""

from __future__ import annotations

import sys
from unittest.mock import Mock

import pytest


def _setup_clean_env(monkeypatch) -> None:
    """Remove environment variables that could affect guard resolution."""
    monkeypatch.delenv("AI_FINDER_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AI_FINDER_FETCH_PROVIDER", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)


def _make_run_demo_mock() -> Mock:
    """Return a Mock that simulates a successful run_demo."""
    return Mock(return_value={"ok": True})


class TestBlockingPaths:
    """Tests that verify paths blocked without --allow-live."""

    def test_blocks_default_path(self, monkeypatch, capsys) -> None:
        """All-default invocation without --allow-live must be blocked."""
        _setup_clean_env(monkeypatch)

        import src.demo

        monkeypatch.setattr(
            src.demo,
            "run_demo",
            Mock(side_effect=AssertionError("run_demo must not be called")),
        )

        monkeypatch.setattr(
            sys,
            "argv",
            ["scripts/demo_answer.py", "--site-id", "example", "--question", "hello"],
        )

        import scripts.demo_answer as demo_answer

        with pytest.raises(SystemExit) as exc_info:
            demo_answer.main()

        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "--allow-live" in captured.err or "offline" in captured.err.lower()

    def test_blocks_live_llm_provider(self, monkeypatch, capsys) -> None:
        """Live LLM provider with mock fetch must be blocked."""
        _setup_clean_env(monkeypatch)

        import src.demo

        monkeypatch.setattr(
            src.demo,
            "run_demo",
            Mock(side_effect=AssertionError("run_demo must not be called")),
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scripts/demo_answer.py",
                "--site-id",
                "example",
                "--question",
                "hello",
                "--provider",
                "openai_compatible",
                "--fetch-provider",
                "mock",
            ],
        )

        import scripts.demo_answer as demo_answer

        with pytest.raises(SystemExit) as exc_info:
            demo_answer.main()

        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "--allow-live" in captured.err

    def test_blocks_live_fetch_provider(self, monkeypatch, capsys) -> None:
        """Mock LLM with live fetch provider must be blocked."""
        _setup_clean_env(monkeypatch)

        import src.demo

        monkeypatch.setattr(
            src.demo,
            "run_demo",
            Mock(side_effect=AssertionError("run_demo must not be called")),
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scripts/demo_answer.py",
                "--site-id",
                "example",
                "--question",
                "hello",
                "--provider",
                "mock",
                "--fetch-provider",
                "requests",
            ],
        )

        import scripts.demo_answer as demo_answer

        with pytest.raises(SystemExit) as exc_info:
            demo_answer.main()

        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "--allow-live" in captured.err

    def test_blocks_firecrawl_fetch(self, monkeypatch, capsys) -> None:
        """Firecrawl fetch provider must be blocked without --allow-live."""
        _setup_clean_env(monkeypatch)

        import src.demo

        monkeypatch.setattr(
            src.demo,
            "run_demo",
            Mock(side_effect=AssertionError("run_demo must not be called")),
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scripts/demo_answer.py",
                "--site-id",
                "example",
                "--question",
                "hello",
                "--provider",
                "mock",
                "--fetch-provider",
                "firecrawl",
            ],
        )

        import scripts.demo_answer as demo_answer

        with pytest.raises(SystemExit) as exc_info:
            demo_answer.main()

        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "--allow-live" in captured.err

    def test_blocks_preset_path(self, monkeypatch, capsys) -> None:
        """Preset path must be blocked without --allow-live even with mock fetch."""
        _setup_clean_env(monkeypatch)

        import src.demo

        monkeypatch.setattr(
            src.demo,
            "run_demo",
            Mock(side_effect=AssertionError("run_demo must not be called")),
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scripts/demo_answer.py",
                "--site-id",
                "example",
                "--question",
                "hello",
                "--preset",
                "deepseek-primary",
                "--fetch-provider",
                "mock",
            ],
        )

        import scripts.demo_answer as demo_answer

        with pytest.raises(SystemExit) as exc_info:
            demo_answer.main()

        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "--allow-live" in captured.err


class TestAllowingPaths:
    """Tests that verify paths allowed without --allow-live."""

    def test_allows_snapshot(self, monkeypatch) -> None:
        """--snapshot path must be allowed without --allow-live."""
        _setup_clean_env(monkeypatch)

        import src.demo

        fake_run_demo = _make_run_demo_mock()
        monkeypatch.setattr(src.demo, "run_demo", fake_run_demo)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scripts/demo_answer.py",
                "--site-id",
                "example",
                "--question",
                "hello",
                "--snapshot",
                "/fake/snapshot.json",
            ],
        )

        import scripts.demo_answer as demo_answer

        demo_answer.main()
        fake_run_demo.assert_called_once()

    def test_allows_mock_provider_and_mock_fetch(self, monkeypatch) -> None:
        """--provider mock --fetch-provider mock must be allowed without --allow-live."""
        _setup_clean_env(monkeypatch)

        import src.demo

        fake_run_demo = _make_run_demo_mock()
        monkeypatch.setattr(src.demo, "run_demo", fake_run_demo)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scripts/demo_answer.py",
                "--site-id",
                "example",
                "--question",
                "hello",
                "--provider",
                "mock",
                "--fetch-provider",
                "mock",
            ],
        )

        import scripts.demo_answer as demo_answer

        demo_answer.main()
        fake_run_demo.assert_called_once()

    def test_allow_live_permits_default_path(self, monkeypatch) -> None:
        """--allow-live must permit the default invocation."""
        _setup_clean_env(monkeypatch)

        import src.demo

        fake_run_demo = _make_run_demo_mock()
        monkeypatch.setattr(src.demo, "run_demo", fake_run_demo)

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "scripts/demo_answer.py",
                "--site-id",
                "example",
                "--question",
                "hello",
                "--allow-live",
            ],
        )

        import scripts.demo_answer as demo_answer

        demo_answer.main()
        fake_run_demo.assert_called_once()
