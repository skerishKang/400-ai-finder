"""Deterministic, generic reference clone model builder (#1303 G2-A).

Reads a committed G1 named-site reference capture ledger plus its committed
artifact files and produces a renderer-agnostic semantic ``clone-model.json``.
Everything is derived from G1 evidence only (ledger + committed artifacts);
nothing is invented and no network is performed.

This stage builds the MODEL only. It does NOT build a faithful renderer
(G2-B) and must never claim stronger readiness than the fail-closed gates
below allow. Screenshots are referenced as evidence artifacts but are not
consumed as runtime source. The builder is generic: it branches on no specific
site, and derives device class, list numbers, and attachment signals from the
captured data itself.
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
GENERATOR_VERSION = "1.0.0"

# Fail-closed claim gates for G2-A. Stronger claims are always False here.
CLAIM_GATES = {
    "reference_baseline_ready": True,
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


class ReferenceCloneModelError(ValueError):
    """Raised when the G1 capture evidence is missing or inconsistent."""


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


def find_capture_root(repo_root: Path) -> Path:
    """Discover the single G1 capture directory (data/official_captures/*/g1/*/ledger.json)."""
    ledgers = sorted(repo_root.glob("data/official_captures/*/g1/*/ledger.json"))
    if not ledgers:
        raise ReferenceCloneModelError("no G1 capture ledger found")
    if len(ledgers) > 1:
        raise ReferenceCloneModelError(f"multiple G1 capture ledgers found: {ledgers}")
    return ledgers[0].parent


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


def build_reference_clone_model(repo_root: Path, capture_root: Path | None = None) -> dict[str, Any]:
    if capture_root is None:
        capture_root = find_capture_root(repo_root)
    ledger_path = capture_root / "ledger.json"
    if not ledger_path.is_file():
        raise ReferenceCloneModelError(f"ledger not found: {ledger_path}")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    capture_id = _require_safe_id(capture_root.name, "capture_id")
    site_id = _require_safe_id(str(ledger.get("site_id")), "site_id")

    plan_identity = ledger.get("plan_identity") or {}
    allowed_hosts: list[str] = list(ledger.get("allowed_hosts") or [])
    plan_path_str = plan_identity.get("path")
    if not allowed_hosts and plan_path_str:
        plan_file = repo_root / plan_path_str
        if plan_file.is_file():
            try:
                allowed_hosts = list(json.loads(plan_file.read_text(encoding="utf-8")).get("allowed_hosts") or [])
            except Exception:
                allowed_hosts = []
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
        "claim_gates": dict(CLAIM_GATES),
        "boundaries": dict(BOUNDARIES),
    }

    states: list[dict[str, Any]] = []
    artifact_count = 0
    for captured in ledger.get("captured_states", []):
        state_id = _require_safe_id(str(captured.get("state_id")), "state_id")
        device_class = "mobile" if "mobile" in state_id.split(".") else "desktop"
        artifacts = [
            {
                "class": art.get("class"),
                "artifact_id": art.get("artifact_id"),
                "sha256": art.get("sha256"),
            }
            for art in captured.get("artifacts", [])
        ]
        artifact_count += len(artifacts)

        download_references: list[dict[str, str]] = []
        document_extensions: list[str] = []
        html_art = next(
            (a for a in captured.get("artifacts", []) if a.get("class") == "html_dom_content"),
            None,
        )
        if html_art:
            html_path = repo_root / html_art.get("artifact_id")
            if html_path.is_file():
                html = html_path.read_text(encoding="utf-8", errors="replace")
                download_references = _extract_download_references(html)
                document_extensions = _extract_document_extensions(html)

        states.append(
            {
                "state_id": state_id,
                "device_class": device_class,
                "state_name": (captured.get("state") or {}).get("name"),
                "viewport": captured.get("viewport"),
                "requested_url": captured.get("requested_url"),
                "final_url": captured.get("final_url"),
                "result_status": captured.get("result_status"),
                "list_no": _parse_list_no(captured.get("final_url") or ""),
                "download_references": download_references,
                "attachment_document_extensions": document_extensions,
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


def fixture_path_for(repo_root: Path, capture_root: Path | None = None) -> Path:
    if capture_root is None:
        capture_root = find_capture_root(repo_root)
    ledger = json.loads((capture_root / "ledger.json").read_text(encoding="utf-8"))
    site_id = str(ledger.get("site_id"))
    capture_id = capture_root.name
    return repo_root / "data" / "official_clone_fixtures" / site_id / "g1" / capture_id / "clone-model.json"


def write_model(repo_root: Path, capture_root: Path | None = None) -> Path:
    if capture_root is None:
        capture_root = find_capture_root(repo_root)
    fixture_path = fixture_path_for(repo_root, capture_root)
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(
        stable_dump(build_reference_clone_model(repo_root, capture_root)),
        encoding="utf-8",
        newline="\n",
    )
    return fixture_path


def check_model(repo_root: Path, capture_root: Path | None = None) -> list[str]:
    if capture_root is None:
        capture_root = find_capture_root(repo_root)
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
    repo_root = Path.cwd()
    capture_root: Path | None = None
    if "--capture-root" in args:
        index = args.index("--capture-root")
        capture_root = Path(args[index + 1])
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


if __name__ == "__main__":
    raise SystemExit(main())
