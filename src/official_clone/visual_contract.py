"""Validator for the #1303 G2-B provenance-backed visual input contract.

The visual contract is the ONLY source of presentation values for the
faithful-clone renderer. It is produced offline from committed G1 evidence
(``scripts/measure_g1_visual_contract.py``); it is never fetched at runtime and
never modifies the immutable G1 capture tree.

This module makes the contract an executable gate:

  * identity: ``site_id`` / ``capture_id`` must equal the semantic model;
  * model checksum: the contract's ``model_checksum`` must equal the canonical
    checksum of the model document (wrong checksum -> fail-closed);
  * schema: every required section/field must exist (null is allowed but
    accounted);
  * provenance: every referenced ``provenance_state_id`` must exist in the
    model's states, and every referenced artifact SHA must exist/equal the
    committed screenshot SHA recorded in the model's ``document_geometry``;
  * numeric ranges: dimensions/colors must fall in sane ranges;
  * accounting: null/pending values are counted and the ``faithful_ready``
    readiness flag is derived from the *required measured* fields only.

``validate_visual_contract`` returns a normalized copy (the validated
contract). ``derive_theme`` extracts only measured (non-null, provenance-backed)
values for the generic renderer. Any identity/checksum/malformed-data failure
raises :class:`VisualContractValidationError` so build pipelines fail closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA_VERSION = 2
CONTRACT_KIND = "visual_input"

# Sections whose presence is mandatory (values may be null/gap).
REQUIRED_SECTIONS = (
    "layout",
    "colors",
    "typography",
    "spacing",
    "border",
    "responsive",
    "gaps",
)

# Required measured fields: the renderer derives its theme from exactly these.
# A null/pending value in any of these makes the contract NOT ready for a
# faithful-candidate claim (faithful_ready=False, faithful_clone_candidate
# must then be False).
REQUIRED_MEASURED_FIELDS = (
    "layout.header.height_px",
    "layout.gnb.height_px",
    "layout.main.max_width_px",
    "layout.footer.height_px",
    "colors.primary",
    "colors.background",
    "colors.header_bg",
    "colors.gnb_bg",
    "colors.gnb_text",
    "colors.footer_bg",
    "colors.text",
    "colors.text_muted",
    "colors.border",
    "typography.font_family",
    "typography.text_color",
    "border.width",
    "border.color",
)

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class VisualContractValidationError(ValueError):
    """Raised when a visual contract fails identity/checksum/schema checks."""


def canonical_model_json(model: dict[str, Any]) -> str:
    """Stable canonical JSON serialization of a model document."""
    return json.dumps(model, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_model_checksum(model: dict[str, Any]) -> str:
    """Canonical SHA-256 checksum of a model document (identity anchor)."""
    return hashlib.sha256(canonical_model_json(model).encode("utf-8")).hexdigest()


def _get_path(contract: dict[str, Any], dotted: str) -> Any:
    node: Any = contract
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _is_hex_color(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX_COLOR_RE.match(value))


def _measurement_entries(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the contract's ``measurements`` block into a list."""
    raw = contract.get("measurements") or []
    if isinstance(raw, dict):
        return list(raw.values())
    return raw


def _check_schema(contract: dict[str, Any]) -> None:
    for section in REQUIRED_SECTIONS:
        if section not in contract:
            raise VisualContractValidationError(f"missing required section: {section!r}")
    if contract.get("contract_kind") != CONTRACT_KIND:
        raise VisualContractValidationError(
            f"wrong contract_kind: {contract.get('contract_kind')!r}"
        )
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise VisualContractValidationError(
            f"wrong schema_version: {contract.get('schema_version')!r}"
        )
    for field in REQUIRED_MEASURED_FIELDS:
        section = field.split(".")[0]
        if section not in contract:
            raise VisualContractValidationError(f"missing section for {field!r}")


def _check_identity(contract: dict[str, Any], model: dict[str, Any]) -> None:
    if contract.get("site_id") != model.get("site_id"):
        raise VisualContractValidationError(
            "site_id mismatch: "
            f"contract={contract.get('site_id')!r} model={model.get('site_id')!r}"
        )
    if contract.get("capture_id") != model.get("capture_id"):
        raise VisualContractValidationError(
            "capture_id mismatch: "
            f"contract={contract.get('capture_id')!r} model={model.get('capture_id')!r}"
        )
    expected_checksum = compute_model_checksum(model)
    if contract.get("model_checksum") != expected_checksum:
        raise VisualContractValidationError(
            "model_checksum mismatch: "
            f"contract={contract.get('model_checksum')!r} expected={expected_checksum!r}"
        )


def _check_provenance(contract: dict[str, Any], model: dict[str, Any]) -> None:
    state_ids = {s.get("state_id") for s in model.get("states", [])}
    screenshot_sha = {}
    for state in model.get("states", []):
        geometry = state.get("document_geometry") or {}
        full = geometry.get("full_page_screenshot") or {}
        if isinstance(full, dict) and full.get("sha256"):
            screenshot_sha[state.get("state_id")] = full["sha256"]

    for entry in _measurement_entries(contract):
        state_id = entry.get("source_state_id")
        if not state_id:
            continue
        if state_id not in state_ids:
            raise VisualContractValidationError(
                f"measurement provenance_state_id not in model states: {state_id!r}"
            )
        artifact_sha = entry.get("artifact_sha256")
        if not artifact_sha:
            continue
        if artifact_sha != screenshot_sha.get(state_id):
            raise VisualContractValidationError(
                f"artifact_sha256 mismatch for {state_id!r}: "
                f"contract={artifact_sha!r} model={screenshot_sha.get(state_id)!r}"
            )


def _check_ranges(contract: dict[str, Any]) -> None:
    def _validate_measurement(entry: dict[str, Any]) -> None:
        value = entry.get("value")
        if value is None:
            return
        if isinstance(value, (int, float)):
            if not (0 <= value <= 100000):
                raise VisualContractValidationError(
                    f"out-of-range numeric value: {value!r}"
                )
        if isinstance(value, str) and value.startswith("#"):
            if not _is_hex_color(value):
                raise VisualContractValidationError(
                    f"malformed color value: {value!r}"
                )

    for entry in _measurement_entries(contract):
        _validate_measurement(entry)

    # Whole-contract color sanity (embedded colors must be well-formed).
    colors = contract.get("colors") or {}
    for key, value in colors.items():
        if key == "provenance_state_id" or value is None:
            continue
        if isinstance(value, str) and value.startswith("#") and not _is_hex_color(value):
            raise VisualContractValidationError(f"malformed color field {key}: {value!r}")


def _count_nulls(contract: dict[str, Any]) -> tuple[int, int]:
    measured = [f for f in _measurement_entries(contract) if f.get("value") is not None]
    missing = [
        f for f in REQUIRED_MEASURED_FIELDS if _get_path(contract, f) is None
    ]
    return len(measured), missing


def validate_visual_contract(
    contract: dict[str, Any] | None, model: dict[str, Any]
) -> dict[str, Any]:
    """Validate a visual contract against the semantic model.

    Returns a normalized (deep-copied) contract with derived accounting fields.
    Raises :class:`VisualContractValidationError` on any identity/checksum/
    schema/provenance/range failure, and on a malformed contract object.
    """
    if contract is None or not isinstance(contract, dict):
        raise VisualContractValidationError("visual contract is missing or malformed")

    _check_schema(contract)
    _check_identity(contract, model)
    _check_provenance(contract, model)
    _check_ranges(contract)

    measured_count, missing_required = _count_nulls(contract)
    gap_count = len([g for g in contract.get("gaps") or [] if isinstance(g, dict)])

    validated = json.loads(json.dumps(contract))
    validated["readiness"] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "required_measured_count": len(REQUIRED_MEASURED_FIELDS),
        "measured_required_count": len(REQUIRED_MEASURED_FIELDS) - len(missing_required),
        "missing_required": sorted(missing_required),
        "measured_value_count": measured_count,
        "gap_count": gap_count,
        "faithful_ready": not missing_required,
    }
    return validated


def faithful_ready(validated: dict[str, Any] | None) -> bool:
    """Whether a validated contract permits a faithful-candidate claim."""
    if not validated:
        return False
    readiness = validated.get("readiness") or {}
    return bool(readiness.get("faithful_ready"))


def derive_theme(validated: dict[str, Any]) -> dict[str, Any]:
    """Extract only provenance-backed measured values for the renderer.

    Values that are null/gap are omitted; the renderer must then fail closed on
    that fidelity (no guessed substitute) or render an explicit gap.
    """
    theme: dict[str, Any] = {}
    for field in REQUIRED_MEASURED_FIELDS:
        value = _get_path(validated, field)
        if value is not None:
            theme[field] = value

    # Responsive differences are optional per-device extras (never guessed).
    responsive = validated.get("responsive") or {}
    for key, value in (responsive.get("mobile") or {}).items():
        if isinstance(value, (int, float)) and value is not None:
            theme[f"responsive.mobile.{key}"] = value
    for key in ("breakpoint_mobile",):
        if responsive.get(key) is not None:
            theme[f"responsive.{key}"] = responsive[key]

    theme["_validated"] = True
    return theme


def load_visual_contract(path: str | Path) -> dict[str, Any]:
    """Load a visual contract JSON file (pure reader, no validation)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
