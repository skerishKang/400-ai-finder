"""Tests for scripts/run_all_demos.py CLI options (PR #799).

These tests exercise ``--pipeline-timeout-s`` end-to-end through ``main()``.
They do NOT spin up real HTTP servers; ``create_app`` and
``create_admin_app`` are monkeypatched to capture kwargs, and
``Thread.join`` is short-circuited so ``main()`` returns immediately after
the server-creation phase.
"""

from __future__ import annotations

import signal
import sys
import threading

import pytest


class _FakeServer:
    """Stand-in for HTTPServer used during CLI tests."""

    def serve_forever(self) -> None:  # pragma: no cover - never reached
        pass

    def shutdown(self) -> None:
        pass

    def server_close(self) -> None:
        pass


def _run_main_with_captured_kwargs(
    monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> dict[str, dict | None]:
    """Invoke ``run_all_demos.main()`` with monkeypatched servers.

    Returns a dict with keys ``"mobile"`` and ``"admin"`` whose values are
    the kwargs each demo-app factory was called with (``None`` if not
    called). The function short-circuits ``Thread.join`` so main returns
    immediately after the server-creation phase.
    """
    captured: dict[str, dict | None] = {"mobile": None, "admin": None}

    def fake_create_app(**kwargs):  # type: ignore[no-untyped-def]
        captured["mobile"] = kwargs
        return _FakeServer()

    def fake_create_admin_app(**kwargs):  # type: ignore[no-untyped-def]
        captured["admin"] = kwargs
        return _FakeServer()

    # ``run_all_demos.main()`` does ``from src.web.mobile_demo import create_app``
    # inside the function body, so we must patch the source modules, not the
    # script module. Patching the module attribute is enough because Python
    # rebinds the local name on every function call.
    from scripts import run_all_demos as mod

    monkeypatch.setattr("src.web.mobile_demo.create_app", fake_create_app)
    monkeypatch.setattr("src.web.admin_demo.create_admin_app", fake_create_admin_app)
    monkeypatch.setattr(sys, "argv", argv)

    # Block the main loop right after thread.start(): raise KeyboardInterrupt
    # inside join() so the except-branch in main() invokes shutdown().
    def fake_join(self, timeout=None):  # type: ignore[no-untyped-def]
        raise KeyboardInterrupt

    monkeypatch.setattr(threading.Thread, "join", fake_join)

    # Suppress real signal handler registration so the shutdown path does
    # not collide with pytest's own SIGINT handling.
    monkeypatch.setattr(signal, "signal", lambda *a, **k: None)

    try:
        mod.main()
    except SystemExit:
        # ``shutdown()`` calls sys.exit(0); this is expected.
        pass

    return captured


def test_pipeline_timeout_s_default_is_30s(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``--pipeline-timeout-s`` is omitted, both apps receive 30.0.

    This locks in the existing default behavior so the new flag does not
    silently change production callers.
    """
    captured = _run_main_with_captured_kwargs(
        monkeypatch,
        [
            "run_all_demos.py",
            "--site-id",
            "bukgu_gwangju",
            "--provider",
            "stub",
            "--mobile-port",
            "18400",
            "--admin-port",
            "18090",
        ],
    )

    assert captured["mobile"] is not None
    assert captured["admin"] is not None
    assert captured["mobile"]["pipeline_timeout_s"] == 30.0
    assert captured["admin"]["pipeline_timeout_s"] == 30.0


def test_pipeline_timeout_s_cli_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--pipeline-timeout-s 1.5`` must reach both demo apps as a float."""
    captured = _run_main_with_captured_kwargs(
        monkeypatch,
        [
            "run_all_demos.py",
            "--site-id",
            "bukgu_gwangju",
            "--provider",
            "stub",
            "--mobile-port",
            "18400",
            "--admin-port",
            "18090",
            "--pipeline-timeout-s",
            "1.5",
        ],
    )

    assert captured["mobile"] is not None
    assert captured["admin"] is not None
    assert captured["mobile"]["pipeline_timeout_s"] == 1.5
    assert captured["admin"]["pipeline_timeout_s"] == 1.5
    # site_id and other kwargs must also flow through unchanged.
    assert captured["mobile"]["site_id"] == "bukgu_gwangju"
    assert captured["admin"]["site_id"] == "bukgu_gwangju"


def test_pipeline_timeout_s_rejects_non_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-numeric values must be rejected by argparse (SystemExit code 2).

    This guards the type=float contract — accidental string values would
    silently break the runner's ``future.result(timeout=...)`` call.
    """
    from scripts import run_all_demos as mod

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_all_demos.py",
            "--site-id",
            "bukgu_gwangju",
            "--provider",
            "stub",
            "--pipeline-timeout-s",
            "not-a-number",
        ],
    )
    monkeypatch.setattr(signal, "signal", lambda *a, **k: None)

    with pytest.raises(SystemExit) as exc_info:
        mod.main()

    # argparse exits with code 2 on bad arguments.
    assert exc_info.value.code == 2
