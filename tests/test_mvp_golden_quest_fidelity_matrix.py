"""Golden-quest fidelity matrix regression test.

Locks the high-level fidelity contract for the 5 resident-task golden quests
so future PRs cannot silently regress them to generic pages, invented internal
submission forms, or unsafe submission-like behavior.

This is a documentation/audit test. It does NOT modify any production metadata;
it only reads the quest registry and asserts the locked contract holds.

See docs/mvp-golden-quest-fidelity-matrix.md for the human-readable matrix.
"""

from __future__ import annotations

import pytest

from src.agent.quest_registry import load_default_bukgu_registry


# ── Locked golden quest matrix ─────────────────────────────────────────────
# Each entry encodes the immutable contract verified by this test.
GOLDEN_MATRIX = {
    "housing_department_lookup": {
        "resident_task": "아파트 정보 안내",
        "official_path": [
            "북구청 홈",
            "분야별정보",
            "건축",
            "아파트정보",
            "아파트현황",
        ],
        "expected_routes": ["apartment-info"],
        "expected_labels": ["아파트정보 화면 이동", "아파트생활정보 관련 안내 확인"],
        # Regressions that must never reappear for this quest.
        "forbidden_path_segments": ["업무 및 전화번호 안내", "구청안내", "공동주택과"],
        "forbidden_answer_substrings": ["062-410-6033"],
    },
    "illegal_parking_report_guidance": {
        "resident_task": "불법 주정차 신고 안내",
        "official_path": [
            "북구청 홈",
            "분야별정보",
            "차량교통",
            "지도단속",
        ],
        "expected_routes": ["complaint-illegal-parking"],
        "expected_labels": ["지도단속 안내 화면 이동", "안전신문고 신고 경로 안내 확인"],
        "forbidden_path_segments": ["불법 주정차 신고", "민원신고"],
        "forbidden_answer_substrings": [],
    },
    "bulky_waste_disposal_guidance": {
        "resident_task": "대형폐기물 배출 안내",
        "official_path": [
            "북구청 홈",
            "분야별정보",
            "환경재활용",
            "대형폐기물 배출방법",
        ],
        "expected_routes": ["bulky-waste-disposal"],
        "expected_labels": ["대형폐기물 배출방법 화면 이동", "대형폐기물 배출방법 안내 확인"],
        # No internal payment / sticker / 배출번호 issuance simulation presented by the demo.
        "forbidden_path_segments": ["대형폐기물 처리"],
        "forbidden_answer_substrings": ["스티커를 출력", "배출번호를 발급합니다", "수수료 결제를 진행"],
    },
    "move_in_report_guidance": {
        "resident_task": "전입신고 안내",
        "official_path": [
            "북구청 홈",
            "종합민원",
            "전자민원창구",
            "정부24",
        ],
        "expected_routes": ["civil-service", "move-in-report-guidance"],
        "expected_labels": ["정부24 전입신고 연결 안내 화면 이동", "정부24 전입신고 연결 안내 카드 확인"],
        # Must not regress to a North-gu-internal 전입신고 신청 form path.
        "forbidden_path_segments": ["민원신고"],
        "forbidden_answer_substrings": [],
    },
    "public_health_center_guidance": {
        "resident_task": "보건소 위치·진료 안내",
        "official_path": [
            "북구청 홈",
            "보건소",
            "보건소소개",
            "찾아오시는 길",
        ],
        "expected_routes": ["home", "public-health-center-guidance"],
        "expected_labels": ["보건소 위치·진료 안내 화면 이동", "보건소 위치·진료 안내 카드 확인"],
        # No diagnosis / prescription / appointment / health-data input simulation.
        "forbidden_path_segments": ["진단", "처방", "예약신청"],
        "forbidden_answer_substrings": [],
    },
}

# Completion-claim verbs that, if present in a quest's `answer`, imply the demo
# performed a submission-like action. The demo must only *guide*; it must never
# report its own completion of a real-world filing.
FORBIDDEN_ANSWER_COMPLETION_VERBS = [
    "접수되었습니다",
    "제출되었습니다",
    "신청이 완료",
    "접수 완료",
    "처리 완료",
]


@pytest.fixture(scope="module")
def registry():
    return load_default_bukgu_registry()


def test_all_five_golden_quests_exist(registry):
    for quest_id in GOLDEN_MATRIX:
        assert registry.get(quest_id) is not None, f"locked golden quest missing: {quest_id}"


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_official_path_matches_locked_value(registry, quest_id):
    quest = registry.get(quest_id)
    expected = GOLDEN_MATRIX[quest_id]["official_path"]
    assert list(quest.official_path) == expected, (
        f"{quest_id} official_path regressed:\n"
        f"  expected: {expected}\n"
        f"  actual:   {list(quest.official_path)}"
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
def test_expected_routes_present(registry, quest_id):
    quest = registry.get(quest_id)
    route_ids = [a.route_id for a in quest.browser_actions]
    for expected in GOLDEN_MATRIX[quest_id]["expected_routes"]:
        assert expected in route_ids, f"{quest_id} missing route_id: {expected}"


@pytest.mark.parametrize("quest_id", list(GOLDEN_MATRIX.keys()))
def test_expected_action_labels_present(registry, quest_id):
    quest = registry.get(quest_id)
    labels = [a.label for a in quest.browser_actions]
    for expected in GOLDEN_MATRIX[quest_id]["expected_labels"]:
        assert expected in labels, f"{quest_id} missing action label: {expected}"


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
    """The demo must only guide; it must never report its own filing completion."""
    answer = registry.get(quest_id).answer or ""
    for verb in FORBIDDEN_ANSWER_COMPLETION_VERBS:
        assert verb not in answer, (
            f"{quest_id} answer implies the demo performed a submission: {verb}"
        )


def test_no_new_golden_quests_beyond_locked_set(registry):
    """Regression guard: the locked set must stay at exactly these 5 quests."""
    locked = set(GOLDEN_MATRIX.keys())
    actual_golden = {
        q.quest_id for q in registry.quests if q.status == "phase1_golden"
    }
    assert actual_golden == locked, (
        f"golden quest set diverged from locked matrix:\n"
        f"  locked:  {sorted(locked)}\n"
        f"  actual:  {sorted(actual_golden)}"
    )
