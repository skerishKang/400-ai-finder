"""#1228-A — runtime vocabulary inventory/schema contract test.

Derives the current runtime vocabulary truth from:
  - Python source (AST): routing._JOURNEY_RULES, models.FreshnessStatus,
    runtime_status.LIVE_PROVIDERS / _NO_API_STATUSES, __init__.BUILTIN_PROVIDERS
  - Cloudflare source (bounded block/regex parsing): ask.js constants,
    evidence-policy.js constants, bukgu-official-snapshots.js route IDs
  - Config (JSON/YAML): SiteSpec, site-registry, sitespec yml

Compares each derived value against the declarative manifest in
configs/contracts/runtime-vocabulary.json. No network, no provider, no Firecrawl.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

# Manifest paths
MANIFEST_PATH = REPO_ROOT / "configs" / "contracts" / "runtime-vocabulary.json"
SCHEMA_PATH = REPO_ROOT / "configs" / "contracts" / "runtime-vocabulary.schema.json"

# Config paths
SITESPEC_PATH = REPO_ROOT / "configs" / "sites" / "bukgu_gwangju.sitespec.json"
SITESPEC_YML_PATH = REPO_ROOT / "configs" / "sites" / "bukgu_gwangju.yml"
REGISTRY_PATH = REPO_ROOT / "configs" / "site-registry.json"

# Python source paths
ROUTING_PY = REPO_ROOT / "src" / "official_source" / "routing.py"
MODELS_PY = REPO_ROOT / "src" / "official_source" / "models.py"
RUNTIME_STATUS_PY = REPO_ROOT / "src" / "llm" / "runtime_status.py"
LLM_INIT_PY = REPO_ROOT / "src" / "llm" / "__init__.py"

# Cloudflare source paths
ASK_JS = REPO_ROOT / "functions" / "api" / "mvp" / "ask.js"
EVIDENCE_POLICY_JS = REPO_ROOT / "functions" / "api" / "mvp" / "evidence-policy.js"
SNAPSHOTS_JS = REPO_ROOT / "functions" / "api" / "mvp" / "bukgu-official-snapshots.js"


# ---------------------------------------------------------------------------
# JS bounded source parsing helpers (string-aware brace/bracket matching)
# ---------------------------------------------------------------------------

def _find_js_matching_close(source: str, open_pos: int, open_ch: str, close_ch: str) -> int:
    """Find position of the matching close char for the open char at open_pos.
    String-aware: skips content inside single- and double-quoted strings."""
    assert source[open_pos] == open_ch
    depth = 1
    pos = open_pos + 1
    in_string = False
    string_char = None
    while pos < len(source) and depth > 0:
        ch = source[pos]
        if in_string:
            if ch == '\\':
                pos += 2
                continue
            if ch == string_char:
                in_string = False
                string_char = None
        elif ch in "'\"":
            in_string = True
            string_char = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
        pos += 1
    assert depth == 0, f"Unbalanced {open_ch}{close_ch} in JS source"
    return pos - 1


def _extract_js_string_array(source: str, const_name: str) -> list[str]:
    """Extract string literals from a JS const declared as Object.freeze([...])."""
    pattern = rf'(?:export\s+)?const\s+{re.escape(const_name)}\s*=\s*Object\.freeze\(\s*\['
    match = re.search(pattern, source)
    assert match is not None, f"Could not find JS const {const_name}"
    bracket_pos = match.end() - 1  # position of [
    close_pos = _find_js_matching_close(source, bracket_pos, '[', ']')
    content = source[bracket_pos + 1:close_pos]
    return re.findall(r"'([^']*)'", content)


def _extract_js_string_const(source: str, const_name: str) -> str:
    """Extract a string constant value from JS source."""
    pattern = rf'(?:export\s+)?const\s+{re.escape(const_name)}\s*=\s*\'([^\']*)\''
    match = re.search(pattern, source)
    assert match is not None, f"Could not find JS const {const_name}"
    return match.group(1)


def _extract_js_string_map(source: str, const_name: str) -> dict[str, str]:
    """Extract key: 'value' pairs from a JS const declared as Object.freeze({})."""
    pattern = rf'(?:export\s+)?const\s+{re.escape(const_name)}\s*=\s*Object\.freeze\(\s*\{{'
    match = re.search(pattern, source)
    assert match is not None, f"Could not find JS const {const_name}"
    brace_pos = match.end() - 1
    close_pos = _find_js_matching_close(source, brace_pos, '{', '}')
    content = source[brace_pos + 1:close_pos]
    pairs = re.findall(r"(\w+):\s*'([^']*)'", content)
    return dict(pairs)


def _extract_js_action_rule_ids(source: str) -> list[str]:
    """Extract action IDs from the ACTION_RULES array in JS ask.js."""
    pattern = r'const ACTION_RULES\s*=\s*Object\.freeze\(\s*\['
    match = re.search(pattern, source)
    assert match is not None, "Could not find ACTION_RULES"
    bracket_pos = match.end() - 1
    close_pos = _find_js_matching_close(source, bracket_pos, '[', ']')
    content = source[bracket_pos + 1:close_pos]
    return re.findall(r"action:\s*'([^']*)'", content)


def _extract_js_provider_defaults(source: str) -> dict[str, str]:
    """Extract provider_id -> default_model from PROVIDER_DEFAULTS in JS."""
    pattern = r'PROVIDER_DEFAULTS\s*=\s*Object\.freeze\(\s*\{'
    match = re.search(pattern, source)
    assert match is not None, "Could not find PROVIDER_DEFAULTS"
    brace_pos = match.end() - 1
    close_pos = _find_js_matching_close(source, brace_pos, '{', '}')
    content = source[brace_pos + 1:close_pos]

    result: dict[str, str] = {}
    for m in re.finditer(r'(\w+):\s*Object\.freeze\(\s*\{', content):
        provider = m.group(1)
        sub_brace = m.end() - 1
        sub_close = _find_js_matching_close(content, sub_brace, '{', '}')
        sub_content = content[sub_brace + 1:sub_close]
        model_match = re.search(r"model:\s*'([^']*)'", sub_content)
        if model_match:
            result[provider] = model_match.group(1)
    return result


def _extract_js_function_body(source: str, func_name: str) -> str:
    """Extract the body of a JS function declaration."""
    pattern = rf'function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{'
    match = re.search(pattern, source)
    assert match is not None, f"Could not find function {func_name}"
    brace_pos = match.end() - 1
    close_pos = _find_js_matching_close(source, brace_pos, '{', '}')
    return source[brace_pos + 1:close_pos]


def _classify_env_vars(env_calls: list[str]) -> dict[str, str]:
    """Classify env var names into secret_env and model_env by naming pattern."""
    result: dict[str, str] = {}
    for env in env_calls:
        if env.endswith('_API_KEY'):
            result['secret_env'] = env
        elif env.endswith('_MODEL'):
            result['model_env'] = env
    return result


def _extract_js_provider_config_env_map(source: str) -> dict[str, dict[str, str]]:
    """Extract provider -> {secret_env, model_env} from providerConfig in JS."""
    func_body = _extract_js_function_body(source, 'providerConfig')

    result: dict[str, dict[str, str]] = {}

    hy3_if = re.search(r"if\s*\(\s*provider\s*===\s*'hy3'\s*\)\s*\{", func_body)
    assert hy3_if is not None, "Could not find if (provider === 'hy3') block"
    hy3_end = _find_js_matching_close(func_body, hy3_if.end() - 1, '{', '}')
    hy3_block = func_body[hy3_if.end():hy3_end]
    result['hy3'] = _classify_env_vars(re.findall(r"envText\(env,\s*'([^']*)'", hy3_block))

    gemini_section = func_body[hy3_end + 1:]
    result['gemini'] = _classify_env_vars(re.findall(r"envText\(env,\s*'([^']*)'", gemini_section))

    return result


def _extract_cf_freshness_states(source: str) -> list[str]:
    """Extract all freshness state literals from Cloudflare ask.js."""
    states: set[str] = set()
    for m in re.finditer(r"freshnessState\s*:\s*'([^']*)'", source):
        states.add(m.group(1))
    for m in re.finditer(r"freshness_state\s*:\s*'([^']*)'", source):
        states.add(m.group(1))
    for m in re.finditer(r"freshnessState\s*\|\|\s*'([^']*)'", source):
        states.add(m.group(1))
    return sorted(states)


def _extract_snapshot_route_ids(source: str) -> list[str]:
    """Extract route IDs from BUKGU_OFFICIAL_SNAPSHOTS (via route_id fields)."""
    return sorted(set(re.findall(r'"route_id"\s*:\s*"([^"]+)"', source)))


# ---------------------------------------------------------------------------
# Python AST source parsing helpers
# ---------------------------------------------------------------------------

def _py_value_node(source: str, var_name: str):
    """Find the value AST node for a module-level variable (Assign or AnnAssign)."""
    tree = ast.parse(source)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == var_name:
            return node.value
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == var_name:
            return node.value
    raise AssertionError(f"{var_name} not found in source")


def _extract_py_first_elements(source: str, var_name: str) -> list[str]:
    """Extract first element of each tuple in a Python tuple-of-tuples assignment."""
    value_node = _py_value_node(source, var_name)
    assert isinstance(value_node, (ast.Tuple, ast.List)), f"{var_name} is not a tuple/list"
    elements: list[str] = []
    for elt in value_node.elts:
        if isinstance(elt, (ast.Tuple, ast.List)):
            first = elt.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                elements.append(first.value)
    return elements


def _extract_py_enum_values(source: str, class_name: str) -> list[str]:
    """Extract enum member values from a Python Enum class definition."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            values: list[str] = []
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and isinstance(item.value, ast.Constant) \
                                and isinstance(item.value.value, str):
                            values.append(item.value.value)
            return values
    raise AssertionError(f"{class_name} not found in source")


def _extract_py_set_values(source: str, var_name: str) -> list[str]:
    """Extract string elements from a Python set literal assignment."""
    value_node = _py_value_node(source, var_name)
    assert isinstance(value_node, ast.Set), f"{var_name} is not a set literal"
    return [
        elt.value
        for elt in value_node.elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    ]


def _extract_py_dict_keys(source: str, var_name: str) -> list[str]:
    """Extract string keys from a Python dict literal assignment."""
    value_node = _py_value_node(source, var_name)
    assert isinstance(value_node, ast.Dict), f"{var_name} is not a dict literal"
    return [
        k.value
        for k in value_node.keys
        if isinstance(k, ast.Constant) and isinstance(k.value, str)
    ]


# ---------------------------------------------------------------------------
# Source loading fixtures
# ---------------------------------------------------------------------------

def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_sitespec() -> dict:
    return json.loads(SITESPEC_PATH.read_text(encoding="utf-8"))


def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _load_sitespec_yml() -> dict:
    return yaml.safe_load(SITESPEC_YML_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A. SiteSpec / registry
# ---------------------------------------------------------------------------

def test_manifest_inventory_only_and_not_runtime_wired():
    manifest = _load_manifest()
    assert manifest["inventory_only"] is True
    assert manifest["runtime_wired"] is False


def test_manifest_canonical_site_id_matches_sitespec():
    manifest = _load_manifest()
    sitespec = _load_sitespec()
    assert manifest["site_identity"]["canonical_site_id"] == sitespec["site_id"]
    assert sitespec["site_id"] == "bukgu_gwangju"


def test_manifest_legacy_ids_match_sitespec():
    manifest = _load_manifest()
    sitespec = _load_sitespec()
    assert sorted(manifest["site_identity"]["legacy_ids"]) == sorted(sitespec["legacy_ids"])
    assert "bukgu" in sitespec["legacy_ids"]


def test_manifest_python_runtime_profile_matches_sitespec():
    manifest = _load_manifest()
    sitespec = _load_sitespec()
    assert manifest["site_identity"]["python_runtime_profile"] == sitespec["runtime"]["python_profile"]
    assert sitespec["runtime"]["python_profile"] == "bukgu_gwangju"


def test_manifest_cloudflare_adapter_matches_sitespec():
    manifest = _load_manifest()
    sitespec = _load_sitespec()
    assert manifest["site_identity"]["cloudflare_adapter"] == sitespec["runtime"]["cloudflare_adapter"]
    assert sitespec["runtime"]["cloudflare_adapter"] == "bukgu"


def test_registry_bukgu_is_legacy_compatibility_id_not_canonical():
    manifest = _load_manifest()
    registry = _load_registry()
    sitespec = _load_sitespec()

    # The registry uses bukgu as the default/adapter ID — it is a legacy
    # compatibility ID, never the canonical site_id.
    assert registry["default_site_id"] == "bukgu"
    assert manifest["site_identity"]["registry_default_site_id"] == "bukgu"

    adapter_site_ids = [a["site_id"] for a in registry["adapters"]]
    assert "bukgu" in adapter_site_ids
    assert "bukgu" in sitespec["legacy_ids"]

    # bukgu must NOT be the canonical site_id.
    assert sitespec["site_id"] != "bukgu"
    assert manifest["site_identity"]["canonical_site_id"] != "bukgu"
    assert "bukgu" in manifest["site_identity"]["legacy_ids"]


def test_display_and_historical_names_are_not_site_ids():
    sitespec = _load_sitespec()

    canonical = sitespec["site_id"]
    legacy_ids = set(sitespec["legacy_ids"])

    # Display names are human labels, not site IDs.
    display_names = list(sitespec["display"]["locale_labels"].values())
    display_names.append(sitespec["display"]["default_label"])
    for label in display_names:
        assert label != canonical, f"Display label {label!r} must not equal canonical site_id"
        assert label not in legacy_ids, f"Display label {label!r} must not be a legacy ID"

    # Historical jurisdiction names are not site IDs.
    historical = [h["value"] for h in sitespec["jurisdiction"]["historical_aliases"]]
    for name in historical:
        assert name != canonical
        assert name not in legacy_ids


def test_sitespec_yml_site_id_matches_canonical():
    yml = _load_sitespec_yml()
    sitespec = _load_sitespec()
    assert yml["site_id"] == sitespec["site_id"] == "bukgu_gwangju"


# ---------------------------------------------------------------------------
# B. Actions
# ---------------------------------------------------------------------------

def test_python_journey_actions_exact_eight():
    routing_src = ROUTING_PY.read_text(encoding="utf-8")
    actions = _extract_py_first_elements(routing_src, "_JOURNEY_RULES")
    assert len(actions) == 8
    assert len(set(actions)) == 8, "duplicated action in _JOURNEY_RULES"
    expected = {
        "illegal_parking",
        "housing_department",
        "bulky_waste",
        "passport_guidance",
        "unmanned_kiosk",
        "streetlight_report",
        "litter_ai_assist",
        "mayor_message_assist",
    }
    assert set(actions) == expected


def test_manifest_journey_actions_parity_with_python():
    manifest = _load_manifest()
    routing_src = ROUTING_PY.read_text(encoding="utf-8")
    py_actions = _extract_py_first_elements(routing_src, "_JOURNEY_RULES")
    assert sorted(manifest["actions"]["journey_actions"]) == sorted(py_actions)


def test_cloudflare_journey_parity_with_python():
    ask_src = ASK_JS.read_text(encoding="utf-8")
    routing_src = ROUTING_PY.read_text(encoding="utf-8")
    cf_actions = _extract_js_action_rule_ids(ask_src)
    py_actions = _extract_py_first_elements(routing_src, "_JOURNEY_RULES")
    assert sorted(cf_actions) == sorted(py_actions)
    assert len(cf_actions) == 8


def test_cloudflare_valid_actions_has_eight_journeys_plus_none():
    ask_src = ASK_JS.read_text(encoding="utf-8")
    valid_actions = _extract_js_string_array(ask_src, "VALID_ACTIONS")
    journey = [a for a in valid_actions if a != "none"]
    assert len(journey) == 8
    assert "none" in valid_actions
    assert len(valid_actions) == 9
    assert len(set(valid_actions)) == 9, "duplicate in VALID_ACTIONS"


def test_none_sentinel_not_a_journey_action():
    manifest = _load_manifest()
    assert manifest["actions"]["no_action_sentinel"]["value"] == "none"
    assert manifest["actions"]["no_action_sentinel"]["is_journey_action"] is False
    assert "none" not in manifest["actions"]["journey_actions"]


def test_manifest_journey_actions_parity_with_cloudflare():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    cf_actions = _extract_js_action_rule_ids(ask_src)
    assert sorted(manifest["actions"]["journey_actions"]) == sorted(cf_actions)


def test_action_snapshot_routes_exact_mapping_parity():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    cf_routes = _extract_js_string_map(ask_src, "ACTION_SNAPSHOT_ROUTES")
    assert manifest["actions"]["action_snapshot_routes"] == cf_routes


def test_snapshot_route_values_exist_in_closed_route_vocabulary():
    ask_src = ASK_JS.read_text(encoding="utf-8")
    snapshots_src = SNAPSHOTS_JS.read_text(encoding="utf-8")
    routes = _extract_js_string_map(ask_src, "ACTION_SNAPSHOT_ROUTES").values()
    snapshot_ids = set(_extract_snapshot_route_ids(snapshots_src))
    for route in routes:
        assert route in snapshot_ids, f"route {route!r} not found in BUKGU_OFFICIAL_SNAPSHOTS"


def test_no_invented_snapshot_routes():
    manifest = _load_manifest()
    # Only the four actions with real snapshots should be present.
    expected_routes = {
        "housing_department",
        "bulky_waste",
        "passport_guidance",
        "unmanned_kiosk",
    }
    assert set(manifest["actions"]["action_snapshot_routes"].keys()) == expected_routes


# ---------------------------------------------------------------------------
# C. Locales
# ---------------------------------------------------------------------------

def test_manifest_locales_parity_with_cloudflare():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    cf_locales = _extract_js_string_array(ask_src, "SUPPORTED_LOCALES")
    assert manifest["locales"]["supported"] == cf_locales


def test_locales_exact_five_no_duplicates():
    ask_src = ASK_JS.read_text(encoding="utf-8")
    locales = _extract_js_string_array(ask_src, "SUPPORTED_LOCALES")
    assert len(locales) == 5
    assert len(set(locales)) == 5


# ---------------------------------------------------------------------------
# D. Evidence
# ---------------------------------------------------------------------------

def test_evidence_levels_parity():
    manifest = _load_manifest()
    evidence_src = EVIDENCE_POLICY_JS.read_text(encoding="utf-8")
    levels = _extract_js_string_array(evidence_src, "EVIDENCE_LEVELS")
    assert manifest["evidence"]["levels"] == levels


def test_verified_evidence_levels_subset_parity():
    manifest = _load_manifest()
    evidence_src = EVIDENCE_POLICY_JS.read_text(encoding="utf-8")
    verified = _extract_js_string_array(evidence_src, "VERIFIED_EVIDENCE_LEVELS")
    assert sorted(manifest["evidence"]["verified_levels"]) == sorted(verified)
    # verified must be a subset of all levels
    assert set(verified).issubset(set(manifest["evidence"]["levels"]))


def test_no_unknown_evidence_levels():
    manifest = _load_manifest()
    evidence_src = EVIDENCE_POLICY_JS.read_text(encoding="utf-8")
    levels = set(_extract_js_string_array(evidence_src, "EVIDENCE_LEVELS"))
    # No invented evidence level in the manifest
    assert set(manifest["evidence"]["levels"]) == levels
    # Every verified level must be a known evidence level
    assert set(manifest["evidence"]["verified_levels"]).issubset(levels)


# ---------------------------------------------------------------------------
# E. Freshness (Python and Cloudflare are separate namespaces)
# ---------------------------------------------------------------------------

def test_python_freshness_parity():
    manifest = _load_manifest()
    models_src = MODELS_PY.read_text(encoding="utf-8")
    py_freshness = _extract_py_enum_values(models_src, "FreshnessStatus")
    assert sorted(manifest["freshness"]["python"]["states"]) == sorted(py_freshness)
    assert len(py_freshness) == 6


def test_cloudflare_freshness_parity():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    cf_states = _extract_cf_freshness_states(ask_src)
    assert sorted(manifest["freshness"]["cloudflare"]["states"]) == sorted(cf_states)
    assert len(cf_states) == 4


def test_freshness_namespaces_not_forced_equal():
    """Python and Cloudflare freshness vocabularies are intentionally different.
    The contract must not assert equality between the two namespaces."""
    models_src = MODELS_PY.read_text(encoding="utf-8")
    ask_src = ASK_JS.read_text(encoding="utf-8")
    py_states = set(_extract_py_enum_values(models_src, "FreshnessStatus"))
    cf_states = set(_extract_cf_freshness_states(ask_src))
    # They are different vocabularies by design.
    assert py_states != cf_states, (
        "Python and Cloudflare freshness states should not be identical; "
        "if they are, the namespace split in the manifest is meaningless."
    )
    # No overlap is required, but we assert the split is real.
    assert "fresh" in py_states
    assert "official_snapshot" in cf_states


# ---------------------------------------------------------------------------
# F. Providers
# ---------------------------------------------------------------------------

def test_python_live_providers_parity():
    manifest = _load_manifest()
    runtime_src = RUNTIME_STATUS_PY.read_text(encoding="utf-8")
    live = _extract_py_set_values(runtime_src, "LIVE_PROVIDERS")
    assert sorted(manifest["providers"]["python"]["live_provider_ids"]) == sorted(live)
    assert len(live) == 9


def test_builtin_providers_identity_not_contradicted():
    manifest = _load_manifest()
    init_src = LLM_INIT_PY.read_text(encoding="utf-8")
    builtin = _extract_py_dict_keys(init_src, "BUILTIN_PROVIDERS")
    # BUILTIN_PROVIDERS keys must equal the manifest live provider inventory
    assert sorted(builtin) == sorted(manifest["providers"]["python"]["live_provider_ids"])
    # mock and stub must not appear in the live provider set
    assert "mock" not in builtin
    assert "stub" not in builtin


def test_python_test_providers_derivation():
    manifest = _load_manifest()
    runtime_src = RUNTIME_STATUS_PY.read_text(encoding="utf-8")
    no_api_keys = _extract_py_dict_keys(runtime_src, "_NO_API_STATUSES")
    live_set = set(_extract_py_set_values(runtime_src, "LIVE_PROVIDERS"))
    # Test providers = non-live _NO_API_STATUSES keys minus the snapshot mode
    test_providers = sorted(k for k in no_api_keys if k not in live_set and k != "snapshot")
    assert test_providers == ["mock", "stub"]
    assert sorted(manifest["providers"]["python"]["test_provider_ids"]) == test_providers


def test_cloudflare_default_provider_order_parity():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    order = _extract_js_string_array(ask_src, "DEFAULT_PROVIDER_ORDER")
    assert manifest["providers"]["cloudflare"]["default_order"] == order
    assert order == ["gemini", "hy3"]


def test_cloudflare_provider_ids_exact_gemini_hy3():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    defaults = _extract_js_provider_defaults(ask_src)
    assert sorted(manifest["providers"]["cloudflare"]["provider_ids"]) == sorted(defaults.keys())
    assert set(defaults.keys()) == {"gemini", "hy3"}


def test_cloudflare_provider_details_parity():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    defaults = _extract_js_provider_defaults(ask_src)
    env_map = _extract_js_provider_config_env_map(ask_src)
    for provider in defaults:
        m = manifest["providers"]["cloudflare"]["provider_details"][provider]
        assert m["default_model"] == defaults[provider]
        assert m["secret_env"] == env_map[provider]["secret_env"]
        assert m["model_env"] == env_map[provider]["model_env"]


def test_kilocode_api_key_contract_maintained():
    """KILOCODE_API_KEY must be used for hy3; HY3_API_KEY must not exist."""
    ask_src = ASK_JS.read_text(encoding="utf-8")
    assert "KILOCODE_API_KEY" in ask_src
    assert "HY3_API_KEY" not in ask_src
    manifest = _load_manifest()
    assert manifest["providers"]["cloudflare"]["provider_details"]["hy3"]["secret_env"] == "KILOCODE_API_KEY"


def test_python_and_cloudflare_provider_sets_not_equal():
    """Python and Cloudflare have different provider universes by design.
    The contract must not assert equality between the two sets."""
    runtime_src = RUNTIME_STATUS_PY.read_text(encoding="utf-8")
    ask_src = ASK_JS.read_text(encoding="utf-8")
    py_providers = set(_extract_py_set_values(runtime_src, "LIVE_PROVIDERS"))
    cf_defaults = _extract_js_provider_defaults(ask_src)
    cf_providers = set(cf_defaults.keys())
    assert py_providers != cf_providers


# ---------------------------------------------------------------------------
# G. API/runtime control vocabulary
# ---------------------------------------------------------------------------

def test_api_schema_version_parity():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    version = _extract_js_string_const(ask_src, "API_SCHEMA_VERSION")
    assert manifest["api_control"]["api_schema_version"] == version


def test_ai_runtime_modes_parity():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    modes = _extract_js_string_array(ask_src, "AI_RUNTIME_MODES")
    assert sorted(manifest["api_control"]["ai_runtime_modes"]) == sorted(modes)
    assert set(modes) == {"enabled", "snapshot_only", "disabled"}


def test_ai_mode_env_parity():
    manifest = _load_manifest()
    ask_src = ASK_JS.read_text(encoding="utf-8")
    env_name = _extract_js_string_const(ask_src, "AI_MODE_ENV")
    assert manifest["api_control"]["ai_mode_env"] == env_name
    assert env_name == "MVP_AI_MODE"
