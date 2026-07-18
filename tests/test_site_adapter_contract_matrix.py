"""Site adapter contract matrix tests (#1221).

Validates that the site-compatibility registry and all registered adapters
satisfy the generic adapter/source contract.

The registry is loaded from REGISTRY_PATH and its adapters form the pytest
matrix via ADAPTER_CASES.  No site-id strings are hard-coded; row IDs are
derived from the registry at runtime.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]

REGISTRY_PATH = ROOT / "configs" / "site-registry.json"
SCHEMA_PATH = ROOT / "configs" / "site-registry.schema.json"

SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

ADAPTER_REQUIRED = frozenset(SCHEMA["$defs"]["adapter"]["required"])
SOURCE_REQUIRED = frozenset(SCHEMA["$defs"]["contract_source"]["required"])
SOURCE_KIND_ENUM = frozenset(SCHEMA["$defs"]["contract_source"]["properties"]["kind"]["enum"])
SOURCE_CLASSIFICATION_ENUM = frozenset(SCHEMA["$defs"]["contract_source"]["properties"]["classification"]["enum"])
SITE_ID_PATTERN = re.compile(SCHEMA["$defs"]["adapter"]["properties"]["site_id"]["pattern"])
GOLDEN_COMMIT_PATTERN = re.compile(SCHEMA["$defs"]["adapter"]["properties"]["golden_commit"]["pattern"])
SOURCE_PATH_PATTERN = re.compile(SCHEMA["$defs"]["contract_source"]["properties"]["path"]["pattern"])
ROLE_CONST = SCHEMA["$defs"]["adapter"]["properties"]["role"]["const"]
CLASSIFICATION_TAGS_ENUM = frozenset(SCHEMA["$defs"]["adapter"]["properties"]["classification_tags"]["items"]["enum"])


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def validate_adapter(adapter: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    data = _require_mapping(adapter, "adapter")

    for field in ADAPTER_REQUIRED:
        if field not in data:
            errors.append(f"missing adapter field: {field}")

    site_id = data.get("site_id")
    if site_id is not None:
        if type(site_id) is not str:
            errors.append("adapter.site_id must be a string")
        elif not site_id.strip():
            errors.append("adapter.site_id must not be empty")
        elif not SITE_ID_PATTERN.match(site_id):
            errors.append(f"adapter.site_id does not match pattern: {site_id!r}")

    role = data.get("role")
    if role is not None:
        if type(role) is not str:
            errors.append("adapter.role must be a string")
        elif role != ROLE_CONST:
            errors.append(f"adapter.role must be {ROLE_CONST!r}, got: {role!r}")

    golden_commit = data.get("golden_commit")
    if golden_commit is not None:
        if type(golden_commit) is not str:
            errors.append("adapter.golden_commit must be a string")
        elif not GOLDEN_COMMIT_PATTERN.match(golden_commit):
            errors.append(f"adapter.golden_commit does not match 40-hex pattern: {golden_commit!r}")

    classification_tags = data.get("classification_tags")
    if classification_tags is not None:
        if not isinstance(classification_tags, list):
            errors.append("adapter.classification_tags must be an array")
        elif not classification_tags:
            errors.append("adapter.classification_tags must not be empty")
        else:
            for idx, tag in enumerate(classification_tags):
                if tag not in CLASSIFICATION_TAGS_ENUM:
                    errors.append(f"adapter.classification_tags[{idx}]: {tag!r} not in enum")

    sources = data.get("frozen_contract_sources")
    if sources is None:
        errors.append("adapter missing frozen_contract_sources")
        return errors

    if not isinstance(sources, list):
        errors.append("adapter.frozen_contract_sources must be an array")
        return errors

    if not sources:
        errors.append("adapter.frozen_contract_sources must not be empty")
        return errors

    for idx, source in enumerate(sources):
        src_data = _require_mapping(source, f"adapter.frozen_contract_sources[{idx}]")
        for field in SOURCE_REQUIRED:
            if field not in src_data:
                errors.append(
                    f"adapter.frozen_contract_sources[{idx}] missing required field: {field}"
                )

        path = src_data.get("path")
        if path is not None:
            if type(path) is not str or not path.strip():
                errors.append(f"adapter.frozen_contract_sources[{idx}].path must be a non-empty string")
            else:
                if not SOURCE_PATH_PATTERN.match(path):
                    errors.append(f"adapter.frozen_contract_sources[{idx}].path does not match schema pattern: {path!r}")
                if ".." in path.split("/"):
                    errors.append(f"adapter.frozen_contract_sources[{idx}].path contains parent traversal: {path!r}")
                resolved = (ROOT / path).resolve()
                if ROOT.resolve() not in resolved.parents and resolved != ROOT.resolve():
                    errors.append(f"adapter.frozen_contract_sources[{idx}].path escapes repository: {path!r}")
                elif not resolved.is_file():
                    errors.append(f"adapter.frozen_contract_sources[{idx}].path file not found: {path!r}")

        kind = src_data.get("kind")
        if kind is not None and kind not in SOURCE_KIND_ENUM:
            errors.append(
                f"adapter.frozen_contract_sources[{idx}].kind: {kind!r} not in allowed values"
            )

        classification = src_data.get("classification")
        if classification is not None and classification not in SOURCE_CLASSIFICATION_ENUM:
            errors.append(
                f"adapter.frozen_contract_sources[{idx}].classification: {classification!r} not in allowed values"
            )

        symbols = src_data.get("symbols")
        if symbols is not None:
            if not isinstance(symbols, list) or not symbols:
                errors.append(f"adapter.frozen_contract_sources[{idx}].symbols must be a non-empty array")
            else:
                source_text: str | None = None
                if path and (ROOT / path).resolve().is_file():
                    source_text = (ROOT / path).resolve().read_text(encoding="utf-8", errors="replace")
                for sym_idx, symbol in enumerate(symbols):
                    if not isinstance(symbol, str) or not symbol.strip():
                        errors.append(f"adapter.frozen_contract_sources[{idx}].symbols[{sym_idx}] must be a non-empty string")
                    elif source_text is not None and symbol not in source_text:
                        errors.append(f"adapter.frozen_contract_sources[{idx}].symbols[{sym_idx}]: {symbol!r} not found in {path!r}")

    return errors


def validate_local(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    adapters = registry.get("adapters")
    if not isinstance(adapters, list):
        errors.append("registry.adapters must be a list")
        return errors
    if not adapters:
        errors.append("registry.adapters must not be empty")
        return errors

    site_ids = []
    for i, adapter in enumerate(adapters):
        data = _require_mapping(adapter, f"registry.adapters[{i}]")
        site_id = data.get("site_id")
        if not isinstance(site_id, str) or not site_id.strip():
            errors.append(f"registry.adapters[{i}] missing valid site_id")
        else:
            site_ids.append(site_id.strip())

    if len(site_ids) != len(set(site_ids)):
        seen: set[str] = set()
        for sid in site_ids:
            if sid in seen:
                errors.append(f"duplicate site_id in registry: {sid}")
            seen.add(sid)

    default_site_id = registry.get("default_site_id")
    if default_site_id is None:
        errors.append("registry.default_site_id must be present")
    elif not isinstance(default_site_id, str):
        errors.append("registry.default_site_id must be a string")
    elif not default_site_id.strip():
        errors.append("registry.default_site_id must not be blank")
    elif default_site_id.strip() not in site_ids:
        errors.append(
            f"registry.default_site_id '{default_site_id}' is not registered"
        )

    for i, adapter in enumerate(adapters):
        adapter_errors = validate_adapter(adapter)
        for err in adapter_errors:
            errors.append(f"registry.adapters[{i}]: {err}")

    return errors


def _adapter_id(adapter: dict[str, Any]) -> str:
    sid = adapter.get("site_id", "<missing-site-id>")
    return str(sid)


_registry_data: dict[str, Any] = _load_json(REGISTRY_PATH)
ADAPTER_CASES = tuple(_registry_data.get("adapters", []))


@pytest.mark.parametrize(
    "adapter",
    ADAPTER_CASES,
    ids=_adapter_id,
)
def test_registered_adapter_satisfies_generic_contract(adapter):
    assert validate_adapter(adapter) == []


class TestRegistryLevel:
    def test_adapters_non_empty(self):
        assert validate_local(_registry_data) == []
        assert len(ADAPTER_CASES) > 0

    def test_unique_site_ids(self):
        site_ids = [a.get("site_id") for a in ADAPTER_CASES]
        assert len(site_ids) == len(set(site_ids))

    def test_default_site_id_registered(self):
        default_id = _registry_data.get("default_site_id")
        assert default_id is not None, "registry must have default_site_id"
        assert isinstance(default_id, str), "default_site_id must be a string"
        assert default_id.strip(), "default_site_id must not be blank"
        site_ids = [a.get("site_id") for a in ADAPTER_CASES]
        assert default_id in site_ids, f"default_site_id {default_id!r} must be in registered site_ids"

    def test_strict_schema_objects(self):
        assert SCHEMA.get("additionalProperties") is False
        assert SCHEMA["$defs"]["adapter"].get("additionalProperties") is False
        assert SCHEMA["$defs"]["contract_source"].get("additionalProperties") is False
        assert validate_local(_registry_data) == []


class TestAdapterMutation:
    @pytest.mark.parametrize(
        "adapter",
        ADAPTER_CASES,
        ids=_adapter_id,
    )
    def test_missing_display_name(self, adapter):
        mutated = copy.deepcopy(adapter)
        mutated.pop("display_name", None)
        errors = validate_adapter(mutated)
        assert "missing adapter field: display_name" in errors

    @pytest.mark.parametrize(
        "adapter",
        ADAPTER_CASES,
        ids=_adapter_id,
    )
    def test_missing_site_id(self, adapter):
        mutated = copy.deepcopy(adapter)
        mutated.pop("site_id", None)
        errors = validate_adapter(mutated)
        assert "missing adapter field: site_id" in errors

    @pytest.mark.parametrize(
        "adapter",
        ADAPTER_CASES,
        ids=_adapter_id,
    )
    def test_missing_source(self, adapter):
        mutated = copy.deepcopy(adapter)
        mutated.pop("frozen_contract_sources", None)
        errors = validate_adapter(mutated)
        assert errors != []
        assert any("frozen_contract_sources" in e for e in errors)

    @pytest.mark.parametrize(
        "adapter",
        ADAPTER_CASES,
        ids=_adapter_id,
    )
    def test_source_path_missing_file(self, adapter):
        mutated = copy.deepcopy(adapter)
        sources = mutated.get("frozen_contract_sources", [])
        if sources:
            sources[0]["path"] = "src/web/static/does-not-exist-file-xyz.js"
        errors = validate_adapter(mutated)
        assert errors != []
        assert any("file not found" in e for e in errors)

    @pytest.mark.parametrize(
        "adapter",
        ADAPTER_CASES,
        ids=_adapter_id,
    )
    def test_missing_symbol(self, adapter):
        mutated = copy.deepcopy(adapter)
        sources = mutated.get("frozen_contract_sources", [])
        if sources:
            sources[0]["symbols"] = ["NONEXISTENT_SYMBOL_XYZ_12345"]
        errors = validate_adapter(mutated)
        assert errors != []
        assert any("not found in" in e for e in errors)

    @pytest.mark.parametrize(
        "adapter",
        ADAPTER_CASES,
        ids=_adapter_id,
    )
    def test_invalid_kind(self, adapter):
        mutated = copy.deepcopy(adapter)
        sources = mutated.get("frozen_contract_sources", [])
        if sources:
            sources[0]["kind"] = ""
        errors = validate_adapter(mutated)
        assert errors != []

    @pytest.mark.parametrize(
        "adapter",
        ADAPTER_CASES,
        ids=_adapter_id,
    )
    def test_invalid_classification(self, adapter):
        mutated = copy.deepcopy(adapter)
        sources = mutated.get("frozen_contract_sources", [])
        if sources:
            sources[0]["classification"] = ""
        errors = validate_adapter(mutated)
        assert errors != []