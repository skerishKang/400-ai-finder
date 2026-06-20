"""No-live contract tests for the Stage #821 execution contract document.

The Stage #821 contract is a **pre-execution lock**: it documents the
exact shape of a future one-time controlled validation, the exact
result envelope, and the exact non-goals. It is intentionally
documentation-first, with no live execution permitted.

These tests pin that the document:

* exists at the agreed path;
* enumerates every required field of the future request;
* enumerates every required precondition;
* enumerates every hard non-goal;
* enumerates every Stage #806 answer status;
* enumerates every leak-prevention rule;
* contains a non-executable template;
* does not accidentally invite live execution;
* does not modify ``scripts/run_all_demos.py``;
* does not introduce forbidden imports (requests / httpx / urllib /
  Firecrawl / subprocess / threading / asyncio / concurrent /
  browser / crawler SDK).
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path
from typing import Iterable

import pytest


DOC_PATH = Path("docs/controlled-live-one-time-validation-contract.md")
SCRIPTS_RUN_ALL_DEMOS = Path("scripts/run_all_demos.py")
REPO_ROOT = Path(__file__).resolve().parent.parent


# --- Required structural elements -----------------------------------------

REQUIRED_SECTIONS = (
    "Purpose and Scope",
    "Required Preconditions",
    "Future Controlled Validation Request",
    "Hard Non-Goals",
    "Safe Result Envelope",
    "Leak Prevention",
    "Future Execution Request Template",
    "Cross-References",
    "Validation",
)


REQUIRED_REQUEST_FIELDS = (
    "question",
    "site_id",
    "fetch_provider",
    "llm_provider",
    "fetch_mode",
    "expected_result_envelope",
    "operator_acknowledgement",
    "rollback_procedure",
)


REQUIRED_PRECONDITIONS = (
    "Stage #817 one-shot runner seam",
    "Stage #819 command guard",
    "Default dry-run remains unchanged",
    "Explicit human approval required",
)


HARD_NON_GOALS = (
    "No live validation in this issue",
    "No network",
    "No Firecrawl",
    "No live LLM",
    "No provider",
    "No browser",
    "No crawler",
    "No subprocess",
    "No thread",
    "No asyncio",
    "No concurrent",
    "No durable logging",
    "No scenario",
    "No cache",
    "No snapshot",
    "No config",
    "No automatic promotion",
    "No public endpoint",
    "No `scripts/run_all_demos.py` live conversion",
)


STAGE_806_STATUSES = (
    "answered_with_evidence",
    "fallback_no_match",
    "fallback_unavailable",
    "error",
)


LEAK_RULES = (
    "raw question",
    "exception",
    "URL credentials",
    "userinfo",
    "headers",
    "body",
    "Bearer token",
    "API key",
    "provider payload",
)


NO_LIVE_KEYWORDS = (
    "no network",
    "no API",
    "no Firecrawl",
    "no LLM",
    "no provider",
    "no persistence",
    "no live",
)


FORBIDDEN_IMPORTS_FOR_SCAN = (
    "requests",
    "httpx",
    "urllib",
    "urllib.request",
    "firecrawl",
    "subprocess",
    "threading",
    "asyncio",
    "concurrent",
    "concurrent.futures",
    "playwright",
    "crawl4ai",
    "scrapy",
    "browser_use",
    "browser",
)


# --- Helpers --------------------------------------------------------------

def _read_doc() -> str:
    assert DOC_PATH.exists(), f"Contract document missing: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=str(REPO_ROOT),
        stderr=subprocess.STDOUT,
    ).decode("utf-8")


# --- Test 1: document exists and has required structure -------------------

def test_doc_exists_and_is_nonempty() -> None:
    text = _read_doc()
    assert len(text) > 0
    assert text.startswith("#")


def test_doc_contains_stage_821_marker() -> None:
    text = _read_doc()
    assert "Stage 821" in text


@pytest.mark.parametrize("section", REQUIRED_SECTIONS)
def test_doc_contains_required_section(section: str) -> None:
    text = _read_doc()
    assert section in text, f"Missing required section: {section}"


# --- Test 2: required request fields are documented -----------------------

@pytest.mark.parametrize("field", REQUIRED_REQUEST_FIELDS)
def test_doc_documents_required_request_field(field: str) -> None:
    text = _read_doc()
    assert field in text, f"Missing required request field: {field}"


def test_doc_documents_exact_operator_acknowledgement_value() -> None:
    text = _read_doc()
    assert '"I_ACKNOWLEDGE_CONTROLLED_LIVE"' in text


def test_doc_documents_closed_allowlist_site_and_providers() -> None:
    text = _read_doc()
    assert '"bukgu_gwangju"' in text
    assert '"requests"' in text
    assert '"stub"' in text
    assert '"subprocess_process_group"' in text


# --- Test 3: preconditions ------------------------------------------------

@pytest.mark.parametrize("precondition", REQUIRED_PRECONDITIONS)
def test_doc_documents_required_precondition(precondition: str) -> None:
    text = _read_doc()
    assert precondition in text, f"Missing required precondition: {precondition}"


# --- Test 4: hard non-goals -----------------------------------------------

@pytest.mark.parametrize("non_goal", HARD_NON_GOALS)
def test_doc_documents_hard_non_goal(non_goal: str) -> None:
    text = _read_doc()
    assert non_goal in text, f"Missing hard non-goal: {non_goal}"


# --- Test 5: Stage #806 result envelope ----------------------------------

@pytest.mark.parametrize("status", STAGE_806_STATUSES)
def test_doc_documents_stage_806_answer_status(status: str) -> None:
    text = _read_doc()
    assert status in text, f"Missing Stage #806 status: {status}"


# --- Test 6: leak prevention ----------------------------------------------

@pytest.mark.parametrize("rule", LEAK_RULES)
def test_doc_documents_leak_prevention_rule(rule: str) -> None:
    text = _read_doc()
    assert rule in text, f"Missing leak rule: {rule}"


# --- Test 7: no-live keywords --------------------------------------------

@pytest.mark.parametrize("keyword", NO_LIVE_KEYWORDS)
def test_doc_states_no_live_keyword(keyword: str) -> None:
    text = _read_doc()
    assert keyword.lower() in text.lower(), f"Missing no-live keyword: {keyword}"


def test_doc_contains_future_template_placeholder() -> None:
    text = _read_doc()
    assert "Future Execution Request Template" in text
    assert "DO NOT EXECUTE" in text
    # The template must use placeholders, not real values.
    assert "<EXACT_QUESTION_NONBLANK_<=500_CHARS>" in text
    assert "<NO_PERSIST_TEXT_EXPLICITLY_STATING_cleanup>" in text


def test_doc_does_not_invite_live_execution() -> None:
    text = _read_doc()
    # The contract must not be a how-to-run-live document.
    assert "how to run live" not in text.lower()
    assert "live execution approved" not in text.lower()
    # The contract is a lock, not an authorization.
    assert "this contract approves live execution" not in text.lower()
    assert "this contract authorizes live execution" not in text.lower()


# --- Test 8: scripts/run_all_demos.py is unchanged -----------------------

def test_scripts_run_all_demos_py_unchanged_vs_origin_main() -> None:
    """The contract must not require any change to run_all_demos.py.

    Any PR that widens this contract must be reviewed before that
    file is touched. For now the contract explicitly forbids it.
    """
    if not SCRIPTS_RUN_ALL_DEMOS.exists():
        pytest.skip("scripts/run_all_demos.py not present in this checkout")

    diff = _git(
        "diff",
        "--quiet",
        "origin/main",
        "--",
        str(SCRIPTS_RUN_ALL_DEMOS),
    )
    # If git diff --quiet exits 0, there is NO change. Non-zero
    # means the file was modified. We want exit code 0.
    assert diff == "", (
        f"scripts/run_all_demos.py was modified vs origin/main; "
        f"the Stage #821 contract explicitly forbids it."
    )


# --- Test 9: AST / no forbidden imports in changed Python files --------

def _iter_python_files_changed_vs_origin() -> Iterable[Path]:
    out = _git(
        "diff",
        "--name-only",
        "--diff-filter=AM",
        "origin/main",
        "HEAD",
        "--",
        "*.py",
    )
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        yield REPO_ROOT / line


def _new_python_files() -> Iterable[Path]:
    """Files that exist in HEAD but not in origin/main."""
    out = _git(
        "diff",
        "--name-only",
        "--diff-filter=A",
        "origin/main",
        "HEAD",
        "--",
        "*.py",
    )
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        yield REPO_ROOT / line


def test_changed_python_files_have_no_forbidden_imports() -> None:
    changed = list(_iter_python_files_changed_vs_origin())
    if not changed:
        pytest.skip("No Python files changed vs origin/main")
    for path in changed:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".", 1)[0]
                    assert top not in FORBIDDEN_IMPORTS_FOR_SCAN, (
                        f"Forbidden import {alias.name!r} in {path}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".", 1)[0]
                assert top not in FORBIDDEN_IMPORTS_FOR_SCAN, (
                    f"Forbidden import {node.module!r} in {path}"
                )


def test_no_new_python_files_added_vs_origin_main() -> None:
    """Stage #821 is documentation-only; no new Python files.

    If a follow-up issue legitimately needs to add a Python file,
    this test should be updated in that PR.
    """
    new_files = list(_new_python_files())
    assert not new_files, (
        "Stage #821 must not add new Python files. "
        f"Found: {[str(p.relative_to(REPO_ROOT)) for p in new_files]}"
    )


# --- Test 10: runner / guard / seam modules are byte-identical ----------

def _files_byte_identical_to_origin(*paths: str) -> bool:
    for p in paths:
        diff = _git(
            "diff",
            "--quiet",
            "origin/main",
            "HEAD",
            "--",
            p,
        )
        if diff != "":
            return False
    return True


def test_runner_guard_and_smoke_modules_are_unchanged() -> None:
    """Stage #821 is documentation-only.

    The runner, the guard, and the Stage #807 contract modules
    must remain byte-identical to ``origin/main``. Any future
    contract amendment must come with a separate code PR.
    """
    for relpath in (
        "src/demo/controlled_live_ux_runner.py",
        "src/demo/controlled_live_command_guard.py",
        "src/demo/controlled_live_smoke_contract.py",
    ):
        diff = _git("diff", "--quiet", "origin/main", "HEAD", "--", relpath)
        assert diff == "", (
            f"{relpath} was modified vs origin/main; "
            f"Stage #821 is documentation-only."
        )
