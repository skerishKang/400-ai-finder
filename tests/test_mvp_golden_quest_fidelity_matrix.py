"""Golden-quest fidelity matrix regression test.

Locks the high-level fidelity contract for the 5 resident-task golden quests
so future PRs cannot silently regress them to generic pages, invented internal
submission forms, or unsafe submission-like behavior.

This is a documentation/audit test. It does NOT modify any production metadata;
it only reads the quest registry and asserts the locked contract holds.

See docs/mvp-golden-quest-fidelity-matrix.md for the human-readable matrix.
"""

from __future__ import annotations

import os

import pytest

from src.agent.quest_registry import load_default_bukgu_registry


# Locked golden quest matrix
GOLDEN_MATRIX = {
    "housing_department_lookup": {
        "quest_name": "공동주택과 안내",
        "official_path": (
            "북구청 홈",
            "북구소개",
            "구청안내",
            "업무 및 전화번호 안내",
            "도시관리국",
            "공동주택과",
        ),
        "expected_action_types": [
            "OPEN_ALLOWLISTED_ROUTE",
            "SHOW_ALLOWLISTED_RESULT",
            "STOP_FOR_USER_CONFIRMATION",
        ],
        "expected_route_ids": ["apartment-dept"],
        "expected_target_ids": ["apartment-dept-card"],
        "expected_labels": [
            "공동주택과 안내 화면 이동",
            "공동주택과 업무 및 연락처 확인",
            "사용자 확인 대기",
        ],
        "forbidden_path_segments": ["분야별정보", "건축", "아파트정보", "아파트현황"],
        "forbidden_answer_substrings": ["062-410-6033"],
        "required_answer_substrings": [],
    },
    "illegal_parking_report_guidance": {
        "quest_name": "불법 주정차 신고 안내",
        "official_path": (
            "북구청 홈",
            "분야별정보",
            "차량교통",
            "지도단속",
        ),
        "expected_action_types": [
            "OPEN_ALLOWLISTED_ROUTE",
            "SHOW_ALLOWLISTED_RESULT",
            "STOP_FOR_USER_CONFIRMATION",
        ],
        "expected_route_ids": ["complaint-illegal-parking"],
        "expected_target_ids": ["complaint-illegal-parking-report"],
        "expected_labels": [
            "지도단속 안내 화면 이동",
            "안전신문고 신고 경로 안내 확인",
            "사용자 확인 대기",
        ],
        "forbidden_path_segments": ["불법 주정차 신고", "민원신고"],
        "forbidden_answer_substrings": [],
        "required_answer_substrings": [],
    },
    "bulky_waste_disposal_guidance": {
        "quest_name": "대형폐기물 배출 안내",
        "official_path": (
            "북구청 홈",
            "분야별정보",
            "환경재활용",
            "대형폐기물 배출방법",
        ),
        "expected_action_types": [
            "OPEN_ALLOWLISTED_ROUTE",
            "SHOW_ALLOWLISTED_RESULT",
            "STOP_FOR_USER_CONFIRMATION",
        ],
        "expected_route_ids": ["bulky-waste-disposal"],
        "expected_target_ids": ["bulky-waste-guidance-card"],
        "expected_labels": [
            "대형폐기물 배출방법 화면 이동",
            "대형폐기물 배출방법 안내 확인",
            "사용자 확인 대기",
        ],
        "forbidden_path_segments": ["대형폐기물 처리"],
        "forbidden_answer_substrings": [
            "스티커를 출력",
            "배출번호를 발급합니다",
            "수수료 결제를 진행",
        ],
        "required_answer_substrings": [],
    },
    "passport_guidance": {
        "quest_name": "여권 발급 안내",
        "official_path": (
            "북구청 홈",
            "종합민원",
            "여권민원",
        ),
        "expected_action_types": [
            "OPEN_ALLOWLISTED_ROUTE",
            "OPEN_ALLOWLISTED_ROUTE",
            "SHOW_ALLOWLISTED_RESULT",
            "STOP_FOR_USER_CONFIRMATION",
        ],
        "expected_route_ids": ["civil-service", "passport-guidance"],
        "expected_target_ids": ["passport-guidance-card"],
        "expected_labels": [
            "종합민원 메뉴 확인",
            "여권민원 안내 화면 이동",
            "여권민원 안내 카드 확인",
            "사용자 확인 대기",
        ],
        "forbidden_path_segments": [],
        "forbidden_answer_substrings": [
            "발급되었습니다",
            "여권이 발급",
            "서류를 발급했습니다",
        ],
        "required_answer_substrings": [
            "여권 발급 경로",
            "여권민원",
            "실제 여권 신청",
            "사용자가",
            "직접 진행",
        ],
    },
    "unmanned_kiosk_guidance": {
        "quest_name": "무인민원발급기 안내",
        "official_path": (
            "북구청 홈",
            "종합민원",
            "무인민원발급기",
        ),
        "expected_action_types": [
            "OPEN_ALLOWLISTED_ROUTE",
            "OPEN_ALLOWLISTED_ROUTE",
            "SHOW_ALLOWLISTED_RESULT",
            "STOP_FOR_USER_CONFIRMATION",
        ],
        "expected_route_ids": ["civil-service", "unmanned-kiosk-guidance"],
        "expected_target_ids": ["unmanned-kiosk-card"],
        "expected_labels": [
            "종합민원 메뉴 확인",
            "무인민원발급기 안내 화면 이동",
            "무인민원발급기 안내 카드 확인",
            "사용자 확인 대기",
        ],
        "forbidden_path_segments": [],
        "forbidden_answer_substrings": [
            "발급되었습니다",
            "서류를 발급했습니다",
            "본인인증을 완료",
        ],
        "required_answer_substrings": [
            "무인민원발급기 이용 경로",
            "설치장소",
            "발급종류",
            "실제 서류 발급",
            "사용자가",
            "직접 진행",
        ],
    },
}

FORBIDDEN_ANSWER_COMPLETION_VERBS = [
    "접수되었습니다",
    "제출되었습니다",
    "신청이 완료",
    "접수 완료",
    "처리 완료",
    "발급되었습니다",
    "발급 완료",
    "여권이 발급",
    "서류를 발급했습니다",
    "본인인증을 완료",
]

REMOVED_QUEST_IDS = {
    "move_in_report_guidance",
    "public_health_center_guidance",
}


@pytest.fixture(scope="module")
def registry():
    return load_default_bukgu_registry()


def test_all_five_golden_quests_exist(registry):
    for quest_id in GOLDEN_MATRIX:
        assert registry.get(quest_id) is not None, (
            f"locked golden quest missing: {quest_id}"
        )


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_quest_name_matches_locked_value(registry, quest_id):
    quest = registry.get(quest_id)
    expected = GOLDEN_MATRIX[quest_id]["quest_name"]
    assert quest.quest_name == expected, (
        f"{quest_id} quest_name regressed:\n"
        f"  expected: {expected}\n"
        f"  actual:   {quest.quest_name}"
    )


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_official_path_matches_locked_value(registry, quest_id):
    quest = registry.get(quest_id)
    expected = list(GOLDEN_MATRIX[quest_id]["official_path"])
    actual = list(quest.official_path)
    assert actual == expected, (
        f"{quest_id} official_path regressed:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_source_mode_is_local_static(registry, quest_id):
    assert registry.get(quest_id).source_mode == "local_static"


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_ai_can_prefill_false(registry, quest_id):
    assert registry.get(quest_id).ai_can_prefill is False


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_ai_can_submit_false(registry, quest_id):
    assert registry.get(quest_id).ai_can_submit is False


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_stop_condition_is_user_confirmation(registry, quest_id):
    assert registry.get(quest_id).stop_condition == "STOP_FOR_USER_CONFIRMATION"


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_action_types_exact_ordered(registry, quest_id):
    quest = registry.get(quest_id)
    actual = [a.action_type for a in quest.browser_actions]
    expected = GOLDEN_MATRIX[quest_id]["expected_action_types"]
    assert actual == expected, (
        f"{quest_id} action types regressed:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_route_ids_exact_ordered(registry, quest_id):
    quest = registry.get(quest_id)
    actual = [a.route_id for a in quest.browser_actions if a.route_id is not None]
    expected = GOLDEN_MATRIX[quest_id]["expected_route_ids"]
    assert actual == expected, (
        f"{quest_id} route_ids regressed:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_target_ids_exact_ordered(registry, quest_id):
    quest = registry.get(quest_id)
    actual = [a.target_id for a in quest.browser_actions if a.target_id is not None]
    expected = GOLDEN_MATRIX[quest_id]["expected_target_ids"]
    assert actual == expected, (
        f"{quest_id} target_ids regressed:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_labels_exact_ordered(registry, quest_id):
    quest = registry.get(quest_id)
    actual = [a.label for a in quest.browser_actions]
    expected = GOLDEN_MATRIX[quest_id]["expected_labels"]
    assert actual == expected, (
        f"{quest_id} labels regressed:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_no_forbidden_path_segments(registry, quest_id):
    quest = registry.get(quest_id)
    path = list(quest.official_path)
    for forbidden in GOLDEN_MATRIX[quest_id]["forbidden_path_segments"]:
        assert forbidden not in path, (
            f"{quest_id} regressed to forbidden path segment: {forbidden}"
        )


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_no_forbidden_answer_substrings(registry, quest_id):
    quest = registry.get(quest_id)
    answer = quest.answer or ""
    for forbidden in GOLDEN_MATRIX[quest_id]["forbidden_answer_substrings"]:
        assert forbidden not in answer, (
            f"{quest_id} answer contains forbidden substring: {forbidden}"
        )


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_answer_never_claims_submission_completion(registry, quest_id):
    answer = registry.get(quest_id).answer or ""
    for verb in FORBIDDEN_ANSWER_COMPLETION_VERBS:
        assert verb not in answer, (
            f"{quest_id} answer implies the demo performed a submission: {verb}"
        )


def test_matrix_matches_canonical_phase1_golden_registry(registry):
    locked = set(GOLDEN_MATRIX.keys())
    actual_golden = {
        q.quest_id for q in registry.quests if q.status == "phase1_golden"
    }
    assert actual_golden == locked, (
        f"golden quest set diverged from locked matrix:\n"
        f"  locked:  {sorted(locked)}\n"
        f"  actual:  {sorted(actual_golden)}"
    )


def test_removed_quest_ids_not_in_registry(registry):
    ids_in_registry = {q.quest_id for q in registry.quests}
    present = REMOVED_QUEST_IDS & ids_in_registry
    assert not present, f"removed quests still present in registry: {present}"


def test_removed_quest_ids_not_in_matrix():
    present = REMOVED_QUEST_IDS & set(GOLDEN_MATRIX.keys())
    assert not present, f"removed quests still present in GOLDEN_MATRIX: {present}"


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_required_answer_substrings_present(registry, quest_id):
    """Check that essential semantic content is preserved in the answer."""
    required = GOLDEN_MATRIX[quest_id].get("required_answer_substrings", [])
    if not required:
        pytest.skip(f"{quest_id} has no required answer substrings configured")
    answer = registry.get(quest_id).answer or ""
    for substring in required:
        assert substring in answer, (
            f"{quest_id} answer missing required content: {substring}"
        )


ACTIVE_CONTRACT_DOCS = [
    "docs/mvp-golden-quest-fidelity-matrix.md",
    "docs/mvp-demo-operator-runbook.md",
    "docs/mvp-demo-milestone-snapshot.md",
]

REMOVED_VERIFIER_FILES = [
    "tests/browser/verify_move_in_quest_e2e.mjs",
    "tests/browser/verify_public_health_center_quest_e2e.mjs",
]

CURRENT_VERIFIER_FILES = [
    "tests/browser/verify_passport_quest_e2e.mjs",
    "tests/browser/verify_unmanned_kiosk_quest_e2e.mjs",
]


@pytest.mark.parametrize("doc_path", ACTIVE_CONTRACT_DOCS)
def test_active_contract_docs_have_no_removed_quest_ids(doc_path):
    """Active contract docs must not reference removed quest IDs as current quests."""
    try:
        with open(doc_path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        pytest.skip(f"{doc_path} not found — may be outside worktree scope")
    for removed_id in REMOVED_QUEST_IDS:
        assert removed_id not in content, (
            f"{doc_path} contains removed quest ID: {removed_id}"
        )


@pytest.mark.parametrize("filepath", REMOVED_VERIFIER_FILES)
def test_removed_verifier_files_absent(filepath):
    """Removed verifier files must not exist."""
    assert not os.path.exists(filepath), (
        f"removed verifier file still exists: {filepath}"
    )


@pytest.mark.parametrize("filepath", CURRENT_VERIFIER_FILES)
def test_current_verifier_files_present(filepath):
    """Current verifier files must exist."""
    assert os.path.exists(filepath), (
        f"current verifier file missing: {filepath}"
    )
