"""Completeness and drift contracts for the canonical apartment-dept snapshot."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from src.bukgu_official_snapshot import (
    build_snapshot_answer,
    build_snapshot_result,
    canonical_snapshot_sha256,
    load_official_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "official_snapshots" / "bukgu_gwangju" / "apartment-dept.json"
BROWSER = ROOT / "src" / "web" / "static" / "bukgu-official-snapshots.js"
FUNCTION = ROOT / "functions" / "api" / "mvp" / "bukgu-official-snapshots.js"
CANVAS = ROOT / "src" / "web" / "static" / "citizen-action-demo-canvas.js"
CHOREOGRAPHY = ROOT / "src" / "web" / "static" / "citizen-first-choreography.js"
HTML = ROOT / "src" / "web" / "static" / "citizen-action-demo.html"
MANIFEST = ROOT / "tests" / "fixtures" / "official_site_clone_manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "mvp-contracts.yml"
HOUSING_E2E = ROOT / "tests" / "browser" / "verify_housing_quest_e2e.mjs"


EXPECTED_ROWS = [
    ("공동주택과", "", "과장", "062-410-6033", "공동주택과 업무전반"),
    ("공동주택과", "공동주택정책", "팀장", "062-410-6812", "공동주택정책팀 업무 전반"),
    ("공동주택과", "공동주택정책", "직원", "062-410-6841", "서무"),
    ("공동주택과", "공동주택정책", "직원", "062-410-6816", "주택건설사업, 지역주택조합"),
    ("공동주택과", "공동주택정책", "직원", "062-410-8277", "주택건설사업,지역주택조합"),
    ("공동주택과", "공동주택정책", "직원", "062-410-6834", "주택건설사업, 지역주택조합"),
    ("공동주택과", "재건축", "팀장", "062-410-8457", "재건축팀 업무 전반"),
    ("공동주택과", "재건축", "직원", "062-410-8458", "재건축, 소규모주택정비사업"),
    ("공동주택과", "재건축", "직원", "062-410-8459", "재건축, 소규모주택정비사업"),
    ("공동주택과", "재개발", "팀장", "062-410-6742", "재개발팀 업무 전반"),
    ("공동주택과", "재개발", "직원", "062-410-6755", "재개발 사업(누문, 풍향, 임동)"),
    ("공동주택과", "재개발", "직원", "062-410-6750", "재개발 사업(북동, 중흥, 우산, 임동2)"),
    ("공동주택과", "공동주택관리", "팀장", "062-410-6840", "공동주택관리팀 업무 전반"),
    ("공동주택과", "공동주택관리", "직원", "062-410-6809", "공동주택관리(오치,두암,용두,우산,동림,매곡), 주민편익시설개선사업 등"),
    ("공동주택과", "공동주택관리", "직원", "062-410-6842", "임대차계약(변경)신고, 주택(임대)관리업등록 등"),
    ("공동주택과", "공동주택관리", "직원", "062-410-6833", "공동주택관리(각화,운암,풍향,삼각,신안), 노후중소형아파트시설개선지원, 비정규직근무환경개선지원 등"),
    ("공동주택과", "공동주택관리", "직원", "062-410-8276", "공동주택관리(용봉,본촌,문흥,신용,일곡), 소규모공동주택안전점검지원사업 등"),
    ("공동주택과", "공동주택관리", "직원", "062-410-8278", "임대사업자등록및말소, 공동주택운영윤리교육, 방범소방교육 등"),
    ("공동주택과", "공동주택관리", "직원", "062-410-6828", "공동주택관리(중흥,유동,임동,양산,연제), 공동주택어린이놀이시설관리 등"),
]


def _canonical() -> dict:
    return json.loads(CANONICAL.read_text(encoding="utf-8"))


def _browser_payload() -> dict:
    text = BROWSER.read_text(encoding="utf-8")
    raw = text.split("root.__BUKGU_OFFICIAL_SNAPSHOTS__ = ", 1)[1]
    raw = raw.split(";\n})(typeof", 1)[0]
    return json.loads(raw)


def _function_payload() -> dict:
    text = FUNCTION.read_text(encoding="utf-8")
    raw = text.split("Object.freeze(", 1)[1].rsplit(");\n", 1)[0]
    return json.loads(raw)


def test_canonical_snapshot_preserves_complete_official_table_in_order():
    snapshot = load_official_snapshot("apartment-dept")
    page = snapshot["page"]
    assert snapshot["snapshot_id"] == "bukgu_gwangju.apartment-dept.2026-07-11"
    assert snapshot["page_id"] == "organization2-a10602012601-5820036"
    assert snapshot["source"] == {
        "url": "https://bukgu.gwangju.kr/organization2.es?mid=a10602012601&org_cd=5820036",
        "title": "조직 및 업무안내 | 공동주택과 | 행정조직 | 구청안내 | 북구소개 : 전남광주통합특별시 북구",
        "captured_at": "2026-07-11T23:08:02+09:00",
        "verified_at": "2026-07-11T23:08:02+09:00",
        "source_updated_at": "2026-06-01",
        "capture_method": "owner-approved read-only official-site validation",
    }
    assert snapshot["representative_contact_source"] == {
        "url": "https://bukgu.gwangju.kr/menu.es?mid=a10602060100",
        "title": "본청 | 부서 대표(전화번호, FAX) | 구청안내 | 북구소개 : 전남광주통합특별시 북구",
        "captured_at": "2026-07-11T23:08:02+09:00",
        "verified_at": "2026-07-11T23:08:02+09:00",
        "source_updated_at": "2026-06-01",
    }
    assert page["section_title"] == "행정조직"
    assert page["breadcrumbs"] == [
        {"label": "홈", "href": "/index.es?sid=a1"},
        {"label": "북구소개", "href": "/menu.es?mid=a10600000000"},
        {"label": "구청안내", "href": "/menu.es?mid=a10602000000"},
        {"label": "행정조직", "href": "/menu.es?mid=a10602010000"},
        {"label": "공동주택과", "href": "/menu.es?mid=a10602012600"},
        {"label": "조직 및 업무안내", "href": "/menu.es?mid=a10602012601", "active": True},
    ]
    assert page["page_tools"] == ["글자 크게", "글자 작게", "인쇄", "공유"]
    assert page["tabs"] == [
        {"label": "조직 및 업무안내", "href": "/menu.es?mid=a10602012601", "active": True},
        {"label": "자료실", "href": "/menu.es?mid=a10602012602", "active": False},
    ]
    assert page["content_heading"] == "조직 및 업무"
    assert page["row_count"] == 19
    assert page["count_label"] == "총 19명"
    assert page["table_accessible_name"] == "부서별 직원 목록"
    assert [column["label"] for column in page["columns"]] == [
        "부서명", "팀명", "직책", "전화번호", "담당업무"
    ]
    actual = [tuple(row[key] for key in ("department", "team", "position", "phone", "duty")) for row in page["rows"]]
    assert actual == EXPECTED_ROWS
    assert page["content_info"] == {
        "label": "콘텐츠 정보책임자",
        "department_label": "담당부서",
        "department": "데이터정보과",
        "contact_label": "연락처",
        "contact": "062-410-8298",
        "last_updated_label": "최근업데이트",
        "last_updated": "2026/06/01",
    }


def test_representative_contact_is_distinct_from_manager_row():
    snapshot = load_official_snapshot("apartment-dept")
    contact = snapshot["representative_contact"]
    assert contact == {
        "department": "공동주택과",
        "phone_display": "062)410-6841",
        "phone": "062-410-6841",
        "fax_display": "062)510-1486",
        "fax": "062-510-1486",
    }
    assert snapshot["page"]["rows"][0]["phone"] == "062-410-6033"
    answer = build_snapshot_answer("apartment-dept")
    assert "대표전화는 062-410-6841" in answer
    assert "전체 19명" in answer
    assert "062-410-6033" not in answer


def test_quest_result_is_composed_from_canonical_snapshot():
    result = build_snapshot_result("apartment-dept")
    assert result["service"] == "공동주택과 조직 및 업무안내"
    assert result["surface"] == "전체 19명 공식 업무 및 연락처"
    assert result["source_updated_at"] == "2026-06-01"
    assert result["source_url"].startswith("https://bukgu.gwangju.kr/")


def test_generated_browser_and_function_payloads_equal_canonical():
    canonical = _canonical()
    expected = copy.deepcopy(canonical)
    expected["canonical_sha256"] = canonical_snapshot_sha256(canonical)
    assert _browser_payload()["apartment-dept"] == expected
    assert _function_payload()["apartment-dept"] == expected


def test_generator_check_passes_without_writing():
    result = subprocess.run(
        [sys.executable, "scripts/generate_bukgu_official_snapshots.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_manifest_keeps_apartment_dept_exact_after_other_routes_are_promoted():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    exact = {entry["route_id"]: entry for entry in manifest["pages"]}
    pending = {entry["route_id"]: entry for entry in manifest["capture_required"]}
    assert "apartment-dept" in exact
    assert "apartment-dept" not in pending

    exact_entry = exact["apartment-dept"]
    assert exact_entry["fixture_path"] == "data/official_snapshots/bukgu_gwangju/apartment-dept.json"
    assert exact_entry["content_mode"] == "exact"
    assert exact_entry["canonical_sha256"] == canonical_snapshot_sha256(_canonical())
    assert exact_entry["quest_ids"] == ["housing_department_lookup"]

    apartment_info_entry = pending["apartment-info"]
    assert apartment_info_entry["status"] == "capture_required"
    assert "housing_department_lookup" not in apartment_info_entry["quest_ids"]
    assert apartment_info_entry["quest_ids"] == []
    assert "apartment-info" in pending


def test_browser_loads_snapshot_before_renderer_and_uses_data_driven_rows():
    html = HTML.read_text(encoding="utf-8")
    canvas = CANVAS.read_text(encoding="utf-8")
    choreography = CHOREOGRAPHY.read_text(encoding="utf-8")
    assert html.index("bukgu-official-snapshots.js") < html.index("citizen-action-demo-canvas.js")
    assert 'var snapshot = _getOfficialSnapshot("apartment-dept")' in canvas
    assert "page.rows.map" in canvas
    assert "062-410-6831" not in canvas
    assert "062-410-6832" not in canvas
    assert "062-410-6033" not in choreography
    assert 'data-representative-contact="true"' in choreography


def test_canonical_snapshot_has_no_runtime_network_dependency():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = next(item for item in manifest["pages"] if item["route_id"] == "apartment-dept")
    assert entry["network_required_at_runtime"] is False
    assert "fetch(" not in BROWSER.read_text(encoding="utf-8")


def test_housing_quest_routes_only_to_apartment_dept_snapshot():
    from src.agent.quest_registry import load_default_bukgu_registry

    quest = load_default_bukgu_registry().get("housing_department_lookup")
    assert quest is not None
    assert quest.official_snapshot_ref == "apartment-dept"

    open_routes = [
        action.route_id
        for action in quest.browser_actions
        if action.action_type == "OPEN_ALLOWLISTED_ROUTE"
    ]
    assert open_routes == ["apartment-dept"]

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    exact = {entry["route_id"]: entry for entry in manifest["pages"]}
    pending = {entry["route_id"]: entry for entry in manifest["capture_required"]}
    assert exact["apartment-dept"]["quest_ids"] == ["housing_department_lookup"]
    assert "housing_department_lookup" not in pending["apartment-info"]["quest_ids"]


def test_housing_e2e_registered_in_ci_workflow():
    assert HOUSING_E2E.exists(), "housing E2E verifier must exist"

    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "verify_housing_quest_e2e.mjs" in workflow, "workflow must run the housing E2E verifier"
    assert "build_cloudflare_pages.py --mode live" in workflow, "workflow must build live Pages"
    assert "127.0.0.1" in workflow, "workflow must bind the loopback server"

    for line in workflow.splitlines():
        stripped = line.strip()
        if "bukgu.gwangju.kr" in stripped and "verify_housing_quest_e2e.mjs" not in stripped:
            # harness URLs in the workflow are fine, but the E2E target must be loopback only
            pass
    assert "http://127.0.0.1:8768" in workflow, "workflow must point the verifier at the loopback server"

    # verifier failures must not be swallowed
    assert "verify_housing_quest_e2e.mjs" in workflow
    e2e_lines = [ln for ln in workflow.splitlines() if "verify_housing_quest_e2e.mjs" in ln]
    assert not any(ln.strip().endswith("|| true") for ln in e2e_lines), "verifier failures must not be ignored with || true"
