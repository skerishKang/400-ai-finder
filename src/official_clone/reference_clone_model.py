"""Deterministic, generic reference clone model builder (#1303 G2-A).

Reads a committed G1 named-site reference capture ledger plus its committed
artifact files and produces a renderer-agnostic semantic ``clone-model.json``.

Fail-closed contract:
  * The input capture directory is selected EXPLICITLY (never discovered by
    glob); the ledger must exist at ``<capture_root>/ledger.json``.
  * The builder refuses to produce a model when the G1 evidence is incomplete
    or tampered: plan identity checksum mismatch, artifact paths escaping the
    capture root, missing artifact files, artifact SHA-256 mismatches, or
    invalid visible-region inventories all fail the build.
  * ``reference_baseline_ready`` is DERIVED from that validation, never a
    constant.

The model is a semantic intermediate layer so a later faithful renderer
(G2-B) does not need to read raw G1 artifacts: each state carries its page
title, observed header/nav/main landmarks and controls, asset provenance,
capture exceptions, list numbers, and attachment/download signals — all
derived from the committed G1 evidence. Screenshots are referenced as
evidence but never consumed as runtime source. No network is performed.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

SCHEMA_VERSION = 1
MODEL_KIND = "reference_clone_model"
GENERATOR_VERSION = "2.0.0"

# Stage claim gates. reference_baseline_ready is derived at build time;
# the stronger claims are fixed False for G2-A.
FIXED_GATES = {
    "faithful_clone_candidate": False,
    "clone_mvp_ready": False,
    "visual_approval": False,
    "actual_site_integrated": False,
}

BOUNDARIES = {
    "screenshot_used_at_runtime": False,
    "network_at_generation": 0,
    "renderer_wired": False,
    "exact_clone_claimed": False,
}

# Generic document/attachment signal (language- and board-system-agnostic).
_DOC_EXT_RE = re.compile(r"\.([a-z0-9]{1,6})$", re.IGNORECASE)
_DOWNLOAD_HREF_RE = re.compile(r"(download|act=download|boarddownload)", re.IGNORECASE)
_ANCHOR_HREF_RE = re.compile(r"""<a\b[^>]*\bhref\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_DOC_TOKEN_RE = re.compile(r"\.(hwp[x]?|pdf|zip|docx?|xlsx?|pptx?|csv|txt)", re.IGNORECASE)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CAPTURE_PREFIX_RE = re.compile(r"^data/official_captures/([^/]+)/g1/([^/]+)/$")


class ReferenceCloneModelError(ValueError):
    """Raised when the G1 capture evidence is missing, incomplete, or tampered."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_safe_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not SAFE_ID_RE.fullmatch(value):
        raise ReferenceCloneModelError(f"{label} has unsafe characters: {value!r}")
    return value


def _is_within(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _parse_list_no(final_url: str) -> str | None:
    try:
        values = parse_qs(urlsplit(final_url or "").query).get("list_no")
    except Exception:
        return None
    if values and values[0]:
        return values[0]
    return None


def _extract_download_references(html: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for href in _ANCHOR_HREF_RE.findall(html):
        if not _DOWNLOAD_HREF_RE.search(href):
            continue
        if href in seen:
            continue
        seen.add(href)
        match = _DOC_EXT_RE.search(href.split("?")[0])
        refs.append({"href": href, "ext": match.group(1).lower() if match else ""})
    return refs


def _extract_document_extensions(html: str) -> list[str]:
    return sorted({m.group(1).lower() for m in _DOC_TOKEN_RE.finditer(html)})


def _resolve_plan_path(repo_root: Path, plan_path: str | None) -> Path | None:
    if not plan_path:
        return None
    candidate = Path(plan_path)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        return None
    full = (repo_root / candidate).resolve()
    if not _is_within(repo_root, full):
        return None
    return full


def _resolve_artifact_path(
    capture_root: Path, site_id: str, capture_id: str, artifact_id: str | None
) -> Path | None:
    """Resolve a ledger artifact_id to a file inside the capture root.

    Production artifact ids are repo-relative
    ``data/official_captures/<site>/g1/<capture_id>/states/...``; the capture-
    relative portion is recovered by stripping the declared capture prefix.
    Absolute paths and any ``..`` escape are rejected.
    """
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    prefix = f"data/official_captures/{site_id}/g1/{capture_id}/"
    rel = artifact_id[len(prefix):] if artifact_id.startswith(prefix) else artifact_id
    rel_path = Path(rel)
    if rel_path.is_absolute() or any(part == ".." for part in rel_path.parts):
        return None
    candidate = (capture_root / rel_path).resolve()
    if not _is_within(capture_root, candidate):
        return None
    return candidate


def _load_plan(repo_root: Path, plan_identity: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(plan_identity, dict):
        return None, "plan_identity missing"
    plan_path_str = plan_identity.get("path")
    plan_sha = plan_identity.get("sha256")
    if not plan_path_str or not plan_sha:
        return None, "plan_identity.path or sha256 missing"
    plan_path = _resolve_plan_path(repo_root, plan_path_str)
    if plan_path is None:
        return None, "plan path escapes repo root"
    if not plan_path.is_file():
        return None, f"plan file not found: {plan_path_str}"
    if not SHA256_RE.fullmatch(str(plan_sha)):
        return None, "plan_identity.sha256 is not a lowercase 64-hex SHA-256"
    if sha256_file(plan_path) != plan_sha:
        return None, "ledger plan checksum does not match approved plan bytes"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"plan is not valid JSON: {exc}"
    return plan, None


def _inventory_is_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not isinstance(value.get("title"), str) or not value["title"]:
        return False
    for key in ("landmarks", "controls"):
        if not isinstance(value.get(key), list):
            return False
    return True


def validate_reference_evidence(repo_root: Path, capture_root: Path) -> dict[str, Any]:
    """Validate the G1 evidence without building the model.

    Never raises for invalid evidence; returns a report of derived booleans.
    ``reference_baseline_ready`` is the AND of every gate below.
    """
    repo_root = Path(repo_root).resolve()
    capture_root = Path(capture_root).resolve()
    ledger_path = capture_root / "ledger.json"
    if not ledger_path.is_file():
        raise ReferenceCloneModelError(f"ledger not found: {ledger_path}")
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReferenceCloneModelError(f"ledger is not valid JSON: {exc}") from exc

    site_id = _require_safe_id(str(ledger.get("site_id")), "site_id")
    capture_id = _require_safe_id(capture_root.name, "capture_id")
    capture_mode = ledger.get("capture_mode")

    # 1. Ledger identity (plan checksum + basic ledger fields).
    plan, identity_problem = _load_plan(repo_root, ledger.get("plan_identity"))
    ledger_identity_valid = (
        identity_problem is None
        and bool(site_id)
        and bool(capture_mode)
        and bool(ledger.get("capture_mode"))
    )

    # 2. States complete: every captured state succeeded and every
    #    capture-required plan state is present and successful.
    captured = ledger.get("captured_states")
    states_complete = False
    if isinstance(captured, list) and captured and ledger_identity_valid:
        by_id = {str(s.get("state_id")): s for s in captured}
        all_success = all(s.get("result_status") == "success" for s in captured)
        required = {
            str(st.get("state_id"))
            for st in (plan or {}).get("states", [])
            if st.get("capture_required")
        }
        required_present = bool(required) and required <= set(by_id)
        states_complete = all_success and required_present

    # 3-5. Artifact containment, presence, and SHA-256 linkage.
    artifacts_within_capture_root = True
    artifact_files_present = True
    artifact_sha256_match = True
    if isinstance(captured, list):
        for state in captured:
            for artifact in state.get("artifacts", []):
                path = _resolve_artifact_path(capture_root, site_id, capture_id, artifact.get("artifact_id"))
                if path is None:
                    artifacts_within_capture_root = False
                    continue
                if not path.is_file():
                    artifact_files_present = False
                    continue
                if not SHA256_RE.fullmatch(str(artifact.get("sha256") or "")):
                    artifact_sha256_match = False
                    continue
                if sha256_file(path) != artifact["sha256"]:
                    artifact_sha256_match = False

    # 6. Visible-region inventories valid for states carrying html evidence.
    inventories_valid = True
    if isinstance(captured, list):
        for state in captured:
            inventory_artifact = next(
                (a for a in state.get("artifacts", []) if a.get("class") == "visible_region_inventory"),
                None,
            )
            if inventory_artifact is None:
                inventories_valid = False
                continue
            path = _resolve_artifact_path(capture_root, site_id, capture_id, inventory_artifact.get("artifact_id"))
            if path is None or not path.is_file():
                inventories_valid = False
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                inventories_valid = False
                continue
            if not _inventory_is_valid(value):
                inventories_valid = False

    reference_baseline_ready = (
        ledger_identity_valid
        and states_complete
        and artifacts_within_capture_root
        and artifact_files_present
        and artifact_sha256_match
        and inventories_valid
    )
    return {
        "ledger_identity_valid": ledger_identity_valid,
        "states_complete": states_complete,
        "artifacts_within_capture_root": artifacts_within_capture_root,
        "artifact_files_present": artifact_files_present,
        "artifact_sha256_match": artifact_sha256_match,
        "inventories_valid": inventories_valid,
        "reference_baseline_ready": reference_baseline_ready,
        "identity_problem": identity_problem,
    }


def _load_inventory(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not _inventory_is_valid(value):
        raise ReferenceCloneModelError(f"invalid visible-region inventory: {path}")
    return value


def build_reference_clone_model(repo_root: Path, capture_root: Path) -> dict[str, Any]:
    """Build the semantic clone model from validated G1 evidence.

    ``capture_root`` must be provided explicitly (never discovered by glob).
    """
    if capture_root is None:
        raise ReferenceCloneModelError("capture_root is required (glob discovery is forbidden)")
    repo_root = Path(repo_root).resolve()
    capture_root = Path(capture_root).resolve()
    validation = validate_reference_evidence(repo_root, capture_root)
    if not validation["reference_baseline_ready"]:
        problem = validation.get("identity_problem") or "G1 evidence is incomplete or tampered"
        raise ReferenceCloneModelError(f"refusing to build: {problem}")

    ledger_path = capture_root / "ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    site_id = _require_safe_id(str(ledger.get("site_id")), "site_id")
    capture_id = _require_safe_id(capture_root.name, "capture_id")
    plan_identity = ledger.get("plan_identity") or {}
    plan, _ = _load_plan(repo_root, plan_identity)
    allowed_hosts: list[str] = list(ledger.get("allowed_hosts") or (plan or {}).get("allowed_hosts") or [])

    claim_gates = dict(FIXED_GATES)
    claim_gates["reference_baseline_ready"] = bool(validation["reference_baseline_ready"])

    model: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "model_kind": MODEL_KIND,
        "model_id": f"{site_id}.g1.reference_clone.{capture_id}",
        "site_id": site_id,
        "capture_id": capture_id,
        "capture_mode": ledger.get("capture_mode"),
        "generator_id": "scripts/build_reference_clone_model.py",
        "generator_version": GENERATOR_VERSION,
        "source_identity": {
            "capture_root": str(ledger_path.parent.relative_to(repo_root).as_posix()),
            "ledger_path": str(ledger_path.relative_to(repo_root).as_posix()),
            "ledger_sha256": sha256_file(ledger_path),
            "plan_id": plan_identity.get("plan_id"),
            "plan_path": plan_identity.get("path"),
            "plan_sha256": plan_identity.get("sha256"),
            "allowed_hosts": allowed_hosts,
            "g1_completion_claim": bool(ledger.get("g1_completion_claim")),
        },
        "validation": {
            key: bool(validation[key])
            for key in (
                "ledger_identity_valid",
                "states_complete",
                "artifacts_within_capture_root",
                "artifact_files_present",
                "artifact_sha256_match",
                "inventories_valid",
                "reference_baseline_ready",
            )
        },
        "claim_gates": claim_gates,
        "boundaries": dict(BOUNDARIES),
    }

    states: list[dict[str, Any]] = []
    artifact_count = 0
    for captured in ledger.get("captured_states", []):
        state_id = _require_safe_id(str(captured.get("state_id")), "state_id")
        device_class = "mobile" if "mobile" in state_id.split(".") else "desktop"
        state_name = (captured.get("state") or {}).get("name")

        artifacts = []
        for artifact in captured.get("artifacts", []):
            artifacts.append(
                {
                    "class": artifact.get("class"),
                    "artifact_id": artifact.get("artifact_id"),
                    "sha256": artifact.get("sha256"),
                }
            )
        artifact_count += len(artifacts)

        def _artifact_file(artifact_class: str) -> Path | None:
            artifact = next((a for a in captured.get("artifacts", []) if a.get("class") == artifact_class), None)
            if artifact is None:
                return None
            return _resolve_artifact_path(capture_root, site_id, capture_id, artifact.get("artifact_id"))

        html_path = _artifact_file("html_dom_content")
        download_references: list[dict[str, str]] = []
        document_extensions: list[str] = []
        if html_path is not None and html_path.is_file():
            html = html_path.read_text(encoding="utf-8", errors="replace")
            download_references = _extract_download_references(html)
            document_extensions = _extract_document_extensions(html)

        inventory_path = _artifact_file("visible_region_inventory")
        page_title: str | None = None
        landmarks: list[Any] = []
        controls: list[Any] = []
        if inventory_path is not None and inventory_path.is_file():
            inventory = _load_inventory(inventory_path)
            page_title = inventory.get("title")
            landmarks = inventory.get("landmarks", [])
            controls = inventory.get("controls", [])

        states.append(
            {
                "state_id": state_id,
                "device_class": device_class,
                "state_name": state_name,
                "viewport": captured.get("viewport"),
                "requested_url": captured.get("requested_url"),
                "final_url": captured.get("final_url"),
                "result_status": captured.get("result_status"),
                "page_title": page_title,
                "landmarks": landmarks,
                "controls": controls,
                "list_no": _parse_list_no(captured.get("final_url") or ""),
                "download_references": download_references,
                "attachment_document_extensions": document_extensions,
                "public_assets": captured.get("public_assets", []),
                "exceptions": captured.get("exceptions", []),
                "artifacts": artifacts,
            }
        )

    model["state_count"] = len(states)
    model["artifact_count"] = artifact_count
    model["states"] = states
    model["model_sha256"] = model_body_checksum(model)
    return model


def stable_dump(model: dict[str, Any]) -> str:
    body = {key: value for key, value in model.items() if key != "model_sha256"}
    return json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def model_body_checksum(model: dict[str, Any]) -> str:
    return hashlib.sha256(stable_dump(model).encode("utf-8")).hexdigest()


def fixture_path_for(repo_root: Path, capture_root: Path) -> Path:
    ledger = json.loads((capture_root / "ledger.json").read_text(encoding="utf-8"))
    site_id = _require_safe_id(str(ledger.get("site_id")), "site_id")
    capture_id = _require_safe_id(capture_root.name, "capture_id")
    return repo_root / "data" / "official_clone_fixtures" / site_id / "g1" / capture_id / "clone-model.json"


def write_model(repo_root: Path, capture_root: Path) -> Path:
    fixture_path = fixture_path_for(repo_root, capture_root)
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(
        stable_dump(build_reference_clone_model(repo_root, capture_root)),
        encoding="utf-8",
        newline="\n",
    )
    return fixture_path


def check_model(repo_root: Path, capture_root: Path) -> list[str]:
    fixture_path = fixture_path_for(repo_root, capture_root)
    if not fixture_path.is_file():
        return [f"fixture missing: {fixture_path}"]
    expected = stable_dump(build_reference_clone_model(repo_root, capture_root))
    committed = fixture_path.read_text(encoding="utf-8")
    if committed != expected:
        return ["committed clone-model fixture does not match regenerated model"]
    return []


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--capture-root" not in args:
        print("usage: build_reference_clone_model.py --capture-root PATH [--check]")
        return 2
    capture_root = Path(args[args.index("--capture-root") + 1])
    repo_root = Path.cwd()
    try:
        if "--check" in args:
            problems = check_model(repo_root, capture_root)
            for problem in problems:
                print(f"REFERENCE_CLONE_MODEL_CHECK_FAIL: {problem}")
            if problems:
                return 2
            print("REFERENCE_CLONE_MODEL_OK")
            return 0
        fixture_path = write_model(repo_root, capture_root)
        print(f"WROTE {fixture_path}")
        return 0
    except ReferenceCloneModelError as exc:
        print(f"REFERENCE_CLONE_MODEL_ERROR: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
