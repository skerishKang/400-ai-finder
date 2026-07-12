"""Regression guard for Issue #1101.

The full pytest suite must collect independently of any third-party
top-level ``tests`` package installed in the environment. Several pipeline
test modules import shared fake data from ``tests.helpers.pipeline_fakes``;
this test proves that module is resolved from THIS repository (not from a
shadowing ``site-packages/tests``).

No network, provider, fetch, or Firecrawl calls are performed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _assert_repo_local(module_file: str) -> None:
    resolved = Path(module_file).resolve()
    assert resolved.exists(), f"imported helper missing: {resolved}"
    assert REPO_ROOT in resolved.parents or resolved == (
        REPO_ROOT / "tests" / "helpers" / "pipeline_fakes.py"
    ), f"imported helper is NOT repository-local: {resolved}"


def test_pipeline_fakes_imported_from_repo():
    from tests.helpers import pipeline_fakes

    _assert_repo_local(pipeline_fakes.__file__)
    # The shared fixtures are actually present and usable.
    assert pipeline_fakes.FAKE_HOMEPAGE_MAP["base_url"] == "https://example.com"
    assert pipeline_fakes.FAKE_DOCS[0]["id"] == "doc-000001"
    assert isinstance(pipeline_fakes.FAKE_ANSWER_RESULT, dict)


def test_import_resolves_with_installed_external_tests_package():
    """A fresh interpreter (cwd = repo root) must still pick the repo helper
    even though a third-party ``tests`` package is installed in site-packages.
    """
    code = (
        "import tests.helpers.pipeline_fakes as m\n"
        "print(m.__file__)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    helper_path = Path(proc.stdout.strip()).resolve()
    _assert_repo_local(str(helper_path))


def test_import_resolves_with_shadowing_external_tests_ahead():
    """Worst case: a fake external ``tests`` package is placed ahead of the
    repo on PYTHONPATH. The repository-local helper must still win because the
    repository root (cwd) is prepended to sys.path by pytest / python -m.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fake_tests = Path(tmp) / "tests"
        fake_tests.mkdir()
        (fake_tests / "__init__.py").write_text(
            "# hostile external tests package\n", encoding="utf-8"
        )
        (fake_tests / "helpers").mkdir()
        (fake_tests / "helpers" / "__init__.py").write_text("", encoding="utf-8")

        code = (
            "import tests.helpers.pipeline_fakes as m\n"
            "print(m.__file__)\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO_ROOT),
            env={**os.environ, "PYTHONPATH": tmp},
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        helper_path = Path(proc.stdout.strip()).resolve()
        _assert_repo_local(str(helper_path))
        # The hostile package must NOT have been the one resolved.
        assert "site-packages" not in str(helper_path)
        assert tmp not in helper_path.parents
