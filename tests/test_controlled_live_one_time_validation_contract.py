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
* does not introduce any new Python file beyond this test file;
* does not add forbidden imports (requests / httpx / urllib /
  Firecrawl / subprocess / threading / asyncio / concurrent /
  browser / crawler SDK) to the runner / guard / smoke modules;
* leaves the runner / guard / smoke modules in their expected
  public-API shape (proxy for "unchanged");
* leaves ``scripts/run_all_demos.py`` free of any live / controlled
  runner import (proxy for "unchanged").

The tests are intentionally pure content-based: they read files via
``pathlib`` and parse with ``ast``. They do NOT shell out to ``git``,
``subprocess``, or any external tool, so the test file itself does
not import or use anything in the forbidden set.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "controlled-live-one-time-validation-contract.md"
SCRIPTS_RUN_ALL_DEMOS = REPO_ROOT / "scripts" / "run_all_demos.py"
RUNNER_PATH = REPO_ROOT / "src" / "demo" / "controlled_live_ux_runner.py"
GUARD_PATH = REPO_ROOT / "src" / "demo" / "controlled_live_command_guard.py"
SMOKE_CONTRACT_PATH = REPO_ROOT / "src" / "demo" / "controlled_live_smoke_contract.py"


# --- Forbidden import set (closed vocabulary) -----------------------------

FORBIDDEN_IMPORTS = frozenset({
    "requests", "httpx", "urllib", "urllib.request",
    "firecrawl", "subprocess", "threading", "asyncio",
    "concurrent", "concurrent.futures",
    "playwright", "crawl4ai", "scrapy",
    "browser_use", "browser",
})


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
    "No API",
    "No Firecrawl",
    "No live LLM",
    "No LLM",
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
    "no api",
    "no firecrawl",
    "no llm",
    "no provider",
    "no persistence",
    "no live",
)


# --- Helpers --------------------------------------------------------------

def _read(path: Path) -> str:
    assert path.exists(), f"File missing: {path}"
    return path.read_text(encoding="utf-8")


def _read_doc() -> str:
    return _read(DOC_PATH)


def _imported_top_level_names(path: Path) -> set[str]:
    """Return the set of top-level module names imported by ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
    return names


def _defined_classes(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}


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
    assert keyword in text.lower(), f"Missing no-live keyword: {keyword}"


def test_doc_contains_future_template_placeholder() -> None:
    text = _read_doc()
    assert "Future Execution Request Template" in text
    assert "DO NOT EXECUTE" in text
    assert "<EXACT_QUESTION_NONBLANK_<=500_CHARS>" in text
    assert "<NO_PERSIST_TEXT_EXPLICITLY_STATING_cleanup>" in text


def test_doc_does_not_invite_live_execution() -> None:
    text = _read_doc()
    lowered = text.lower()
    assert "how to run live" not in lowered
    assert "live execution approved" not in lowered
    assert "this contract approves live execution" not in lowered
    assert "this contract authorizes live execution" not in lowered


# --- Test 8: scripts/run_all_demos.py must not import the live runner ----

# Patterns that would indicate a live-execution conversion of the script.
_LIVE_CONVERSION_PATTERNS = (
    "controlled_live_ux_runner",
    "controlled_live_command_guard",
    "controlled_live_one_shot",
    "live_execution",
    "real_fetch",
    "firecrawl",
)


@pytest.mark.skipif(
    not SCRIPTS_RUN_ALL_DEMOS.exists(),
    reason="scripts/run_all_demos.py not present in this checkout",
)
def test_scripts_run_all_demos_py_does_not_import_live_runner() -> None:
    text = _read(SCRIPTS_RUN_ALL_DEMOS)
    for pattern in _LIVE_CONVERSION_PATTERNS:
        assert pattern not in text, (
            f"scripts/run_all_demos.py contains live-runner reference "
            f"{pattern!r}; Stage #821 contract forbids it."
        )


def test_scripts_run_all_demos_py_does_not_have_live_run_branch() -> None:
    if not SCRIPTS_RUN_ALL_DEMOS.exists():
        pytest.skip("scripts/run_all_demos.py not present in this checkout")
    text = _read(SCRIPTS_RUN_ALL_DEMOS)
    lowered = text.lower()
    # No "real fetch" or "firecrawl" call sites injected.
    assert "firecrawl" not in lowered
    assert "subprocess.run" not in lowered  # still a script-side primitive
    # No live LLM provider wired in.
    assert "openai" not in lowered
    assert "anthropic" not in lowered


# --- Test 9: runner / guard / smoke modules are free of forbidden imports

@pytest.mark.parametrize(
    "path",
    [RUNNER_PATH, GUARD_PATH, SMOKE_CONTRACT_PATH],
    ids=["runner", "guard", "smoke_contract"],
)
def test_runner_guard_smoke_have_no_forbidden_imports(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"{path} not present in this checkout")
    imported = _imported_top_level_names(path)
    leaked = imported & FORBIDDEN_IMPORTS
    assert not leaked, (
        f"Forbidden imports detected in {path.name}: {sorted(leaked)}"
    )


# --- Test 10: runner / guard / smoke have the expected public API shape --

def test_runner_has_expected_public_api() -> None:
    assert RUNNER_PATH.exists()
    classes = _defined_classes(RUNNER_PATH)
    assert "LockedControlledLiveUxError" in classes
    assert "LockedControlledLiveUxRequest" in classes
    assert "LockedControlledLiveUxResponse" in classes


def test_guard_has_expected_public_api() -> None:
    assert GUARD_PATH.exists()
    classes = _defined_classes(GUARD_PATH)
    assert "CommandDecision" in classes


def test_smoke_contract_has_expected_public_api() -> None:
    assert SMOKE_CONTRACT_PATH.exists()
    classes = _defined_classes(SMOKE_CONTRACT_PATH)
    assert "ControlledLiveSmokeRequest" in classes
    assert "ControlledLiveSmokePlan" in classes


# --- Test 11: this test file is itself import-clean -----------------------

def test_this_test_file_has_no_forbidden_imports() -> None:
    """The test file is allowed to use stdlib but never the live set."""
    path = Path(__file__).resolve()
    imported = _imported_top_level_names(path)
    # The test file uses ``ast`` and ``re`` and ``pathlib`` and
    # ``pytest``; all are stdlib or test deps. The forbidden live
    # set must be empty.
    leaked = imported & FORBIDDEN_IMPORTS
    assert not leaked, (
        f"This test file imported forbidden modules: {sorted(leaked)}"
    )


# --- Test 12: this contract test does not introduce new Python files ----
#
# The test file itself is the only new Python file Stage #821 is
# allowed to add. We pin that by listing every Python file under
# the test/ source/ scripts/ paths and comparing the count against
# a known expected set is not portable, so instead we just check
# that the doc + test + repo's existing Python tree does not gain
# any unexpected runner / guard / smoke / firecrawl / subprocess
# / playwright / scrapy modules. If a new file appears in those
# directories, it must NOT be a runner / guard / smoke / live
# variant. This keeps Stage #821 documentation-only.

_LIVE_FILE_BASENAMES = frozenset({
    "live_runner",
    "live_executor",
    "firecrawl_runner",
    "controlled_live_live",
    "controlled_live_real",
    "real_fetch",
})


def test_no_new_live_runner_files_added() -> None:
    """Stage #821 must not add a new live-runner / executor file.

    The test file itself is allowed; this guard is for any other
    new file whose name suggests a live execution surface.
    """
    for directory in (
        REPO_ROOT / "src" / "demo",
        REPO_ROOT / "src" / "fetch",
        REPO_ROOT / "src" / "llm",
        REPO_ROOT / "src" / "crawler",
    ):
        if not directory.exists():
            continue
        for path in directory.glob("*.py"):
            if path.name == "__init__.py":
                continue
            stem = path.stem
            for forbidden in _LIVE_FILE_BASENAMES:
                assert forbidden not in stem, (
                    f"Stage #821 must not add live-execution file: {path}"
                )


# --- Test 13: the contract doc does not enable or invite execution --------

def test_doc_does_not_contain_a_runnable_command() -> None:
    """The doc is a contract, not a script. No shell-runnable example."""
    text = _read_doc()
    # No ``python -m ...`` invocation that wires the live runner.
    assert "python -m src.demo.controlled_live" not in text
    # No explicit "run the live runner" instruction.
    assert re.search(r"run\s+the\s+live\s+runner", text, re.IGNORECASE) is None
