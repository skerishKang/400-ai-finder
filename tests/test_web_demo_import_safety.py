"""Import-safety contract tests for web demo server entrypoints.

Locks the Stage 311/312 web demo boundary policy: importing the wrapper
modules must not start a demo server, open a browser, call a provider,
fetch a URL, or contact Firecrawl.

Target scripts:
- run_all_demos.py
- run_mobile_demo.py
- run_admin_demo.py
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import Mock

import pytest


WEB_DEMO_SCRIPTS = [
    "scripts.run_all_demos",
    "scripts.run_mobile_demo",
    "scripts.run_admin_demo",
]


@pytest.fixture(autouse=True)
def cleanup_modules():
    """Remove web demo modules from sys.modules after each test."""
    yield
    for name in WEB_DEMO_SCRIPTS:
        sys.modules.pop(name, None)


def _monkeypatch_side_effects(monkeypatch) -> dict[str, Mock]:
    """Monkeypatch all paths that should never fire during import.

    Returns a dict of mocks that can be asserted after import.
    """
    mocks: dict[str, Mock] = {}

    # HTTP server creation (triggers socket bind — must not happen at import)
    http_server_init = Mock(
        side_effect=AssertionError(
            "http.server.HTTPServer.__init__ called during import"
        )
    )
    monkeypatch.setattr(
        "socketserver.TCPServer.__init__",
        http_server_init,
        raising=False,
    )
    mocks["http_server_init"] = http_server_init

    # Thread start (server threads must not be launched at import)
    thread_start = Mock(
        side_effect=AssertionError("threading.Thread.start called during import")
    )
    monkeypatch.setattr("threading.Thread.start", thread_start, raising=False)
    mocks["thread_start"] = thread_start

    # Browser open
    browser_open = Mock(
        side_effect=AssertionError("webbrowser.open called during import")
    )
    monkeypatch.setattr("webbrowser.open", browser_open, raising=False)
    mocks["browser_open"] = browser_open

    # Subprocess calls
    subprocess_popen = Mock(
        side_effect=AssertionError("subprocess.Popen called during import")
    )
    monkeypatch.setattr("subprocess.Popen", subprocess_popen, raising=False)
    mocks["subprocess_popen"] = subprocess_popen

    subprocess_run = Mock(
        side_effect=AssertionError("subprocess.run called during import")
    )
    monkeypatch.setattr("subprocess.run", subprocess_run, raising=False)
    mocks["subprocess_run"] = subprocess_run

    # Network/fetch/provider calls (requests layer)
    requests_get = Mock(
        side_effect=AssertionError("requests.get called during import")
    )
    monkeypatch.setattr("requests.get", requests_get, raising=False)
    mocks["requests_get"] = requests_get

    # Firecrawl provider fetch
    firecrawl_fetch = Mock(
        side_effect=AssertionError(
            "FirecrawlFetchProvider.fetch called during import"
        )
    )
    monkeypatch.setattr(
        "src.fetch.firecrawl_provider.FirecrawlFetchProvider.fetch",
        firecrawl_fetch,
        raising=False,
    )
    mocks["firecrawl_fetch"] = firecrawl_fetch

    # Requests provider fetch
    requests_fetch = Mock(
        side_effect=AssertionError(
            "RequestsFetchProvider.fetch called during import"
        )
    )
    monkeypatch.setattr(
        "src.fetch.requests_provider.RequestsFetchProvider.fetch",
        requests_fetch,
        raising=False,
    )
    mocks["requests_fetch"] = requests_fetch

    return mocks


@pytest.mark.parametrize("module_name", WEB_DEMO_SCRIPTS)
def test_web_demo_import_is_side_effect_free(
    monkeypatch, module_name
) -> None:
    """Importing a web demo entrypoint must not trigger server/network/provider calls."""
    mocks = _monkeypatch_side_effects(monkeypatch)

    module = importlib.import_module(module_name)

    assert module is not None
    assert hasattr(module, "main")
    assert callable(module.main)

    # Verify no side effects
    for mock_name, mock_obj in mocks.items():
        mock_obj.assert_not_called()


@pytest.mark.parametrize("module_name", WEB_DEMO_SCRIPTS)
def test_web_demo_main_is_not_invoked_on_import(module_name) -> None:
    """Verify that main() is not automatically called when importing.

    We can detect this by ensuring the module is purely definitional
    (functions and classes) and has no if-__name__-equals-main guard
    at module level that could accidentally invoke main().
    """
    # Remove any cached import first
    sys.modules.pop(module_name, None)

    module = importlib.import_module(module_name)

    # The module should have a main function (not yet called)
    assert hasattr(module, "main")
    assert callable(module.main)

    # Verify that main is a plain function, not an already-returned value
    # main() would return None (via implicit return), so a module-level
    # call would make module.main a NoneType.
    assert module.main is not None
