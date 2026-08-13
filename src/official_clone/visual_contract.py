"""Validator for the #1303 G2-B provenance-backed visual input contract.

The visual contract is the ONLY source of presentation values for the
faithful-clone renderer. It is produced offline from committed G1 evidence
(``scripts/measure_g1_visual_contract.py``); it is never fetched at runtime and
never modifies the immutable G1 capture tree.

This module makes the contract an executable gate. Validation is *fail-closed*:
any of the following raises :class:`VisualContractValidationError`:

  * identity: ``site_id`` / ``capture_id`` differ from the semantic model;
  * model checksum: the contract's ``model_checksum`` differs from the canonical
    checksum of the model document;
  * schema: a required section/field is missing;
  * evidence binding (1:1): every non-null measured contract field MUST have
    exactly one evidence record, and every evidence record MUST resolve to an
    existing contract field with a matching value and unit. Specifically:
      - required field with no evidence record            -> fail;
      - duplicate evidence for the same field             -> fail;
      - unknown / unbound evidence field                  -> fail;
      - evidence value != contract field value            -> fail;
      - evidence unit != expected unit for the field      -> fail;
      - evidence source state not in the model            -> fail;
      - evidence artifact SHA mismatch vs committed SHA   -> fail;
      - evidence present but not connected to the contract -> fail;
  * evidence type: ``pixel_analysis`` / ``asset_provenance`` (ledger is NOT
     supported in G2-B — any ledger evidence record is rejected);
  * numeric ranges and color format sanity.

``validate_visual_contract`` returns a normalized copy (the validated
contract). ``derive_theme`` extracts only measured (non-null, provenance-backed)
values for the generic renderer. ``faithful_ready`` is True only when every
required measured field is non-null AND has a valid 1:1 evidence record; any
null/pending/mismatch/unbound required evidence keeps it False.
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
# must then be False). Mobile geometry is required too: desktop-only evidence
# cannot promote a faithful candidate.
REQUIRED_MEASURED_FIELDS = (
    # desktop geometry
    "layout.header.height_px",
    "layout.gnb.height_px",
    "layout.main.max_width_px",
    "layout.footer.height_px",
    # desktop colors
    "colors.primary",
    "colors.background",
    "colors.header_bg",
    "colors.gnb_bg",
    "colors.gnb_text",
    "colors.footer_bg",
    "colors.text",
    "colors.text_muted",
    "colors.border",
    # typography observation
    "typography.font_family",
    "typography.text_color",
    # border
    "border.width",
    "border.color",
    # mobile (390px) provenance — required for the faithful gate
    "responsive.mobile.header_height_px",
    "responsive.mobile.gnb_height_px",
    "responsive.mobile.max_width_px",
    "responsive.mobile.main_padding_x",
)

# Expected unit per required measured field (None = unitless string value).
FIELD_UNITS: dict[str, str | None] = {
    "layout.header.height_px": "px",
    "layout.gnb.height_px": "px",
    "layout.main.max_width_px": "px",
    "layout.footer.height_px": "px",
    "colors.primary": "hex",
    "colors.background": "hex",
    "colors.header_bg": "hex",
    "colors.gnb_bg": "hex",
    "colors.gnb_text": "hex",
    "colors.footer_bg": "hex",
    "colors.text": "hex",
    "colors.text_muted": "hex",
    "colors.border": "hex",
    "typography.font_family": None,
    "typography.text_color": "hex",
    "border.width": "px",
    "border.color": "hex",
    "responsive.mobile.header_height_px": "px",
    "responsive.mobile.gnb_height_px": "px",
    "responsive.mobile.max_width_px": "px",
    "responsive.mobile.main_padding_x": "px",
}

# Evidence record types supported by the validator.
# ledger is NOT supported in G2-B: there is no authoritative ledger/artifact
# identity validation path in scope. Any ledger evidence is rejected.
EVIDENCE_TYPES = ("pixel_analysis", "asset_provenance")

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class VisualContractValidationError(ValueError):
    """Raised when a visual contract fails identity/checksum/schema/evidence
    binding checks."""


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


def _field_exists(contract: dict[str, Any], dotted: str) -> bool:
    node: Any = contract
    parts = dotted.split(".")
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


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


def _screenshot_sha_map(model: dict[str, Any]) -> dict[str, str]:
    """Map state_id -> committed full-page screenshot SHA from the model."""
    out: dict[str, str] = {}
    for state in model.get("states", []):
        geometry = state.get("document_geometry") or {}
        full = geometry.get("full_page_screenshot") or {}
        if isinstance(full, dict) and full.get("sha256"):
            out[state.get("state_id")] = full["sha256"]
    return out


def _provenance_assets_by_state(model: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Map state_id -> list of provenance-manifest asset records."""
    out: dict[str, list[dict[str, Any]]] = {}
    for entry in model.get("provenance_manifest", []) or []:
        state_id = entry.get("state_id")
        if state_id:
            out.setdefault(state_id, []).append(entry)
    return out


def _expected_provenance_state(contract: dict[str, Any], field: str) -> str | None:
    """Walk the dotted field path from leaf to root to find the nearest
    ``provenance_state_id``. Returns ``None`` when no parent section declares
    one (fail-safe: the caller decides how to enforce)."""
    parts = field.split(".")
    for i in range(len(parts), 0, -1):
        node: Any = contract
        for part in parts[:i]:
            if not isinstance(node, dict) or part not in node:
                node = None
                break
            node = node[part]
        if isinstance(node, dict) and "provenance_state_id" in node:
            return node["provenance_state_id"]
    return None


def _check_evidence(contract: dict[str, Any], model: dict[str, Any]) -> None:
    """Enforce 1:1 binding between measured contract fields and evidence.

    Fail-closed on: required field without evidence, duplicate evidence,
    unknown/unbound evidence field, field/value mismatch, unit mismatch,
    source state mismatch, artifact SHA mismatch, evidence not connected to a
    contract field, and unsupported evidence types.
    """
    state_ids = {s.get("state_id") for s in model.get("states", [])}
    shot_shas = _screenshot_sha_map(model)
    assets_by_state = _provenance_assets_by_state(model)

    entries = _measurement_entries(contract)
    seen_fields: set[str] = set()
    bound_fields: set[str] = set()

    for entry in entries:
        field = entry.get("field")
        value = entry.get("value")
        unit = entry.get("unit")
        ev_type = entry.get("evidence_type")
        state_id = entry.get("source_state_id")
        artifact_sha = entry.get("artifact_sha256")

        # Unknown / unbound evidence field: must resolve to a contract field.
        if not isinstance(field, str) or not field:
            raise VisualContractValidationError(
                f"evidence record missing field name: {entry!r}"
            )
        if not _field_exists(contract, field):
            raise VisualContractValidationError(
                f"unknown/unbound evidence field: {field!r} (no such contract field)"
            )

        # Duplicate evidence.
        if field in seen_fields:
            raise VisualContractValidationError(f"duplicate evidence for field: {field!r}")
        seen_fields.add(field)

        # Field/value mismatch: evidence value must equal the contract value.
        contract_value = _get_path(contract, field)
        if contract_value != value:
            raise VisualContractValidationError(
                f"field/value mismatch for {field!r}: "
                f"contract={contract_value!r} evidence={value!r}"
            )

        # Unit mismatch (only for known required/expected-unit fields).
        expected_unit = FIELD_UNITS.get(field)
        if expected_unit is not None and unit != expected_unit:
            raise VisualContractValidationError(
                f"unit mismatch for {field!r}: expected={expected_unit!r} got={unit!r}"
            )

        # Source state must exist in the model.
        if not state_id or state_id not in state_ids:
            raise VisualContractValidationError(
                f"source state mismatch for {field!r}: {state_id!r} not in model states"
            )

        # Source state must match the field's expected provenance state (fail-closed
        # on field-to-state binding). Every required section declares a
        # ``provenance_state_id`` that the evidence must respect.
        expected_state = _expected_provenance_state(contract, field)
        if expected_state and state_id != expected_state:
            raise VisualContractValidationError(
                f"source state binding violation for {field!r}: "
                f"expected {expected_state!r} got {state_id!r}"
            )

        # Evidence type + artifact checksum validation.
        if ev_type not in EVIDENCE_TYPES:
            raise VisualContractValidationError(
                f"unsupported evidence_type for {field!r}: {ev_type!r}"
            )
        if not artifact_sha:
            raise VisualContractValidationError(
                f"evidence for {field!r} has no artifact_sha256"
            )
        if ev_type == "pixel_analysis":
            expected_sha = shot_shas.get(state_id)
            if not expected_sha or artifact_sha != expected_sha:
                raise VisualContractValidationError(
                    f"artifact SHA mismatch for {field!r} ({state_id}): "
                    f"evidence={artifact_sha!r} committed={expected_sha!r}"
                )
        elif ev_type == "asset_provenance":
            assets = assets_by_state.get(state_id, [])
            asset_shas = {a.get("sha256") for a in assets}
            if artifact_sha not in asset_shas:
                raise VisualContractValidationError(
                    f"asset artifact SHA mismatch for {field!r} ({state_id}): "
                    f"{artifact_sha!r} not in committed provenance manifest"
                )

        bound_fields.add(field)

    # Every non-null required measured field must have a bound evidence record.
    for field in REQUIRED_MEASURED_FIELDS:
        if _get_path(contract, field) is not None and field not in bound_fields:
            raise VisualContractValidationError(
                f"required field has no evidence record: {field!r}"
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


def _count_nulls(contract: dict[str, Any]) -> tuple[int, list[str]]:
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
    _check_evidence(contract, model)
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

    # Responsive differences are required per-device extras (never guessed).
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
