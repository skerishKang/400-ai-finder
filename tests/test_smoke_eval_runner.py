from pathlib import Path

import pytest

from scripts.run_smoke_eval import (
    DEFAULT_MATRIX_PATH,
    LIVE_EVAL_ENV_VAR,
    LIVE_PREFLIGHT_CONFIG_NAMES,
    SmokeLiveEvalGuardError,
    SmokeResponseFixtureError,
    SmokeScenarioMatrixError,
    build_live_eval_preflight,
    build_response_eval_summary,
    build_summary,
    evaluate_response,
    evaluate_response_fixture,
    format_live_eval_preflight,
    is_live_eval_enabled,
    load_matrix,
    load_response_fixture,
    run_live_eval_guard,
    run_live_eval_preflight,
    run_response_eval,
    run_schema_eval,
    validate_matrix,
    validate_response_fixture,
)

RESPONSE_FIXTURE_PATH = Path("tests/fixtures/smoke_eval_responses.json")


def test_stage40_matrix_loads_and_validates() -> None:
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    scenarios = validate_matrix(matrix)

    assert len(scenarios) == 14


def test_stage40_matrix_summary_counts() -> None:
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    scenarios = validate_matrix(matrix)
    summary = build_summary(scenarios)

    assert summary["total"] == 14
    assert summary["sites"] == {
        "bukgu_gwangju": 7,
        "gwangju_go_kr": 7,
    }
    assert summary["categories"] == {
        "ambiguous_query": 2,
        "department_contact": 2,
        "document_lookup": 2,
        "fee_hour_location": 2,
        "low_confidence_fallback": 2,
        "service_navigation": 4,
    }


def test_schema_eval_report_is_human_readable() -> None:
    report = run_schema_eval(DEFAULT_MATRIX_PATH)

    assert "Smoke scenario matrix loaded" in report
    assert "Total scenarios: 14" in report
    assert "- bukgu_gwangju: 7" in report
    assert "- gwangju_go_kr: 7" in report
    assert "- service_navigation: 4" in report
    assert "Status: schema-only eval passed" in report


def test_validate_matrix_rejects_missing_required_scenario_key() -> None:
    invalid_matrix = {
        "scenarios": [
            {
                "id": "invalid-01",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": [],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="missing required keys"):
        validate_matrix(invalid_matrix)


def test_validate_matrix_rejects_duplicate_ids() -> None:
    scenario = {
        "id": "duplicate-01",
        "site_id": "bukgu_gwangju",
        "category": "service_navigation",
        "question": "민원서식 어디서 받아?",
        "expected_domain": "bukgu.gwangju.kr",
        "expected_keywords": [],
        "pass_criteria": {
            "site_id_match": True,
            "min_sources": 1,
            "no_cross_site_urls": True,
        },
    }

    with pytest.raises(SmokeScenarioMatrixError, match="Duplicate scenario id"):
        validate_matrix({"scenarios": [scenario, dict(scenario)]})


def test_stage261_validate_matrix_rejects_non_string_truthy_source_domain() -> None:
    """Reject truthy non-string pass_criteria.source_domain values."""
    for source_domain in (True, 123):
        invalid_matrix = {
            "scenarios": [
                {
                    "id": f"invalid-source-domain-{source_domain}",
                    "site_id": "bukgu_gwangju",
                    "category": "service_navigation",
                    "question": "민원서식은 어디에서 확인하나요?",
                    "expected_domain": "bukgu.gwangju.kr",
                    "expected_keywords": ["민원서식"],
                    "pass_criteria": {
                        "site_id_match": True,
                        "min_sources": 1,
                        "source_domain": source_domain,
                        "no_cross_site_urls": True,
                    },
                }
            ]
        }

        with pytest.raises(SmokeScenarioMatrixError, match="source_domain"):
            validate_matrix(invalid_matrix)


def test_stage263_validate_matrix_rejects_bool_min_sources() -> None:
    """Reject bool pass_criteria.min_sources values in matrix validation."""
    for min_sources in (True, False):
        invalid_matrix = {
            "scenarios": [
                {
                    "id": f"invalid-min-sources-{min_sources}",
                    "site_id": "bukgu_gwangju",
                    "category": "service_navigation",
                    "question": "민원서식은 어디에서 확인하나요?",
                    "expected_domain": "bukgu.gwangju.kr",
                    "expected_keywords": ["민원서식"],
                    "pass_criteria": {
                        "site_id_match": True,
                        "min_sources": min_sources,
                        "no_cross_site_urls": True,
                    },
                }
            ]
        }

        with pytest.raises(SmokeScenarioMatrixError, match="min_sources"):
            validate_matrix(invalid_matrix)


def test_stage265_validate_matrix_rejects_invalid_min_sources_values() -> None:
    """Reject non-integer and negative pass_criteria.min_sources values."""
    for min_sources in (-1, 1.0, "1"):
        invalid_matrix = {
            "scenarios": [
                {
                    "id": f"invalid-min-sources-{min_sources}",
                    "site_id": "bukgu_gwangju",
                    "category": "service_navigation",
                    "question": "민원서식은 어디에서 확인하나요?",
                    "expected_domain": "bukgu.gwangju.kr",
                    "expected_keywords": ["민원서식"],
                    "pass_criteria": {
                        "site_id_match": True,
                        "min_sources": min_sources,
                        "no_cross_site_urls": True,
                    },
                }
            ]
        }

        with pytest.raises(SmokeScenarioMatrixError, match="min_sources"):
            validate_matrix(invalid_matrix)


def test_stage265_validate_matrix_preserves_zero_and_one_min_sources() -> None:
    """Preserve non-negative integer pass_criteria.min_sources values."""
    for min_sources in (0, 1):
        valid_matrix = {
            "scenarios": [
                {
                    "id": f"valid-min-sources-{min_sources}",
                    "site_id": "bukgu_gwangju",
                    "category": "service_navigation",
                    "question": "민원서식은 어디에서 확인하나요?",
                    "expected_domain": "bukgu.gwangju.kr",
                    "expected_keywords": ["민원서식"],
                    "pass_criteria": {
                        "site_id_match": True,
                        "min_sources": min_sources,
                        "no_cross_site_urls": True,
                    },
                }
            ]
        }

        scenarios = validate_matrix(valid_matrix)

        assert scenarios[0]["pass_criteria"]["min_sources"] == min_sources


def test_validate_matrix_rejects_non_bool_site_id_match() -> None:
    """Reject truthy int site_id_match in matrix validation."""
    invalid_matrix = {
        "scenarios": [
            {
                "id": "invalid-site-id-match",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": 1,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="site_id_match"):
        validate_matrix(invalid_matrix)


def test_validate_matrix_rejects_non_bool_no_cross_site_urls() -> None:
    """Reject truthy int no_cross_site_urls in matrix validation."""
    invalid_matrix = {
        "scenarios": [
            {
                "id": "invalid-no-cross-site-urls",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": 1,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="no_cross_site_urls"):
        validate_matrix(invalid_matrix)


def test_validate_matrix_preserves_bool_site_id_match_values() -> None:
    """Preserve True and False for site_id_match."""
    for value in (True, False):
        matrix = {
            "scenarios": [
                {
                    "id": f"valid-site-id-match-{value}",
                    "site_id": "bukgu_gwangju",
                    "category": "service_navigation",
                    "question": "민원서식은 어디에서 확인하나요?",
                    "expected_domain": "bukgu.gwangju.kr",
                    "expected_keywords": ["민원서식"],
                    "pass_criteria": {
                        "site_id_match": value,
                        "min_sources": 1,
                        "no_cross_site_urls": True,
                    },
                }
            ]
        }

        scenarios = validate_matrix(matrix)
        assert scenarios[0]["pass_criteria"]["site_id_match"] is value


def test_validate_matrix_preserves_bool_no_cross_site_urls_values() -> None:
    """Preserve True and False for no_cross_site_urls."""
    for value in (True, False):
        matrix = {
            "scenarios": [
                {
                    "id": f"valid-no-cross-site-urls-{value}",
                    "site_id": "bukgu_gwangju",
                    "category": "service_navigation",
                    "question": "민원서식은 어디에서 확인하나요?",
                    "expected_domain": "bukgu.gwangju.kr",
                    "expected_keywords": ["민원서식"],
                    "pass_criteria": {
                        "site_id_match": True,
                        "min_sources": 1,
                        "no_cross_site_urls": value,
                    },
                }
            ]
        }

        scenarios = validate_matrix(matrix)
        assert scenarios[0]["pass_criteria"]["no_cross_site_urls"] is value


def test_validate_matrix_rejects_non_bool_optional_answer_not_empty() -> None:
    """Reject int answer_not_empty in matrix validation."""
    invalid_matrix = {
        "scenarios": [
            {
                "id": "invalid-answer-not-empty",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "answer_not_empty": 1,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="answer_not_empty"):
        validate_matrix(invalid_matrix)


def test_validate_matrix_rejects_non_bool_optional_fallback_required() -> None:
    """Reject int fallback_required in matrix validation."""
    invalid_matrix = {
        "scenarios": [
            {
                "id": "invalid-fallback-required",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "fallback_required": 1,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="fallback_required"):
        validate_matrix(invalid_matrix)


def test_validate_matrix_rejects_non_bool_optional_fallback_when_no_source() -> None:
    """Reject int fallback_when_no_source in matrix validation."""
    invalid_matrix = {
        "scenarios": [
            {
                "id": "invalid-fallback-when-no-source",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "fallback_when_no_source": 1,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="fallback_when_no_source"):
        validate_matrix(invalid_matrix)


def test_validate_matrix_preserves_optional_boolean_answer_not_empty_values() -> None:
    """Preserve True and False for answer_not_empty."""
    for value in (True, False):
        matrix = {
            "scenarios": [
                {
                    "id": f"valid-answer-not-empty-{value}",
                    "site_id": "bukgu_gwangju",
                    "category": "service_navigation",
                    "question": "민원서식은 어디에서 확인하나요?",
                    "expected_domain": "bukgu.gwangju.kr",
                    "expected_keywords": ["민원서식"],
                    "pass_criteria": {
                        "site_id_match": True,
                        "min_sources": 1,
                        "no_cross_site_urls": True,
                        "answer_not_empty": value,
                    },
                }
            ]
        }

        scenarios = validate_matrix(matrix)
        assert scenarios[0]["pass_criteria"]["answer_not_empty"] is value


def test_validate_matrix_preserves_optional_boolean_fallback_required_values() -> None:
    """Preserve True and False for fallback_required."""
    for value in (True, False):
        matrix = {
            "scenarios": [
                {
                    "id": f"valid-fallback-required-{value}",
                    "site_id": "bukgu_gwangju",
                    "category": "service_navigation",
                    "question": "민원서식은 어디에서 확인하나요?",
                    "expected_domain": "bukgu.gwangju.kr",
                    "expected_keywords": ["민원서식"],
                    "pass_criteria": {
                        "site_id_match": True,
                        "min_sources": 1,
                        "no_cross_site_urls": True,
                        "fallback_required": value,
                    },
                }
            ]
        }

        scenarios = validate_matrix(matrix)
        assert scenarios[0]["pass_criteria"]["fallback_required"] is value


def test_validate_matrix_preserves_optional_boolean_fallback_when_no_source_values() -> None:
    """Preserve True and False for fallback_when_no_source."""
    for value in (True, False):
        matrix = {
            "scenarios": [
                {
                    "id": f"valid-fallback-when-no-source-{value}",
                    "site_id": "bukgu_gwangju",
                    "category": "service_navigation",
                    "question": "민원서식은 어디에서 확인하나요?",
                    "expected_domain": "bukgu.gwangju.kr",
                    "expected_keywords": ["민원서식"],
                    "pass_criteria": {
                        "site_id_match": True,
                        "min_sources": 1,
                        "no_cross_site_urls": True,
                        "fallback_when_no_source": value,
                    },
                }
            ]
        }

        scenarios = validate_matrix(matrix)
        assert scenarios[0]["pass_criteria"]["fallback_when_no_source"] is value


def test_validate_matrix_allows_missing_optional_boolean_pass_criteria() -> None:
    """Allow missing optional boolean keys."""
    matrix = {
        "scenarios": [
            {
                "id": "no-optional-bools",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                },
            }
        ]
    }

    scenarios = validate_matrix(matrix)
    assert "answer_not_empty" not in scenarios[0]["pass_criteria"]
    assert "fallback_required" not in scenarios[0]["pass_criteria"]
    assert "fallback_when_no_source" not in scenarios[0]["pass_criteria"]


@pytest.mark.parametrize(
    "invalid_value",
    [
        "foo",
        ("foo",),
        None,
        1,
        True,
        {},
    ],
)
def test_validate_matrix_rejects_non_list_answer_contains_any_values(
    invalid_value: object,
) -> None:
    """Reject non-list answer_contains_any values in matrix validation."""
    invalid_matrix = {
        "scenarios": [
            {
                "id": "invalid-answer-contains-any",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "answer_contains_any": invalid_value,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="answer_contains_any"):
        validate_matrix(invalid_matrix)


def test_validate_matrix_preserves_missing_answer_contains_any() -> None:
    """Allow missing answer_contains_any."""
    matrix = {
        "scenarios": [
            {
                "id": "no-answer-contains-any",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                },
            }
        ]
    }

    scenarios = validate_matrix(matrix)
    assert "answer_contains_any" not in scenarios[0]["pass_criteria"]


@pytest.mark.parametrize(
    "valid_value",
    [
        [],
        ["foo"],
    ],
)
def test_validate_matrix_preserves_list_answer_contains_any_values(
    valid_value: list[str],
) -> None:
    """Preserve list answer_contains_any values."""
    matrix = {
        "scenarios": [
            {
                "id": "valid-answer-contains-any",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "answer_contains_any": valid_value,
                },
            }
        ]
    }

    scenarios = validate_matrix(matrix)
    assert scenarios[0]["pass_criteria"]["answer_contains_any"] == valid_value


@pytest.mark.parametrize(
    "invalid_items",
    [
        ["foo", 1],
        ["foo", True],
        ["foo", None],
        ["foo", {}],
        ["foo", []],
    ],
)
def test_validate_matrix_rejects_non_string_answer_contains_any_items(
    invalid_items: list[object],
) -> None:
    """Reject non-string items inside answer_contains_any lists."""
    invalid_matrix = {
        "scenarios": [
            {
                "id": "invalid-items",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "answer_contains_any": invalid_items,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="answer_contains_any"):
        validate_matrix(invalid_matrix)


@pytest.mark.parametrize(
    "valid_items",
    [
        [],
        ["foo"],
        ["foo", "bar"],
    ],
)
def test_validate_matrix_preserves_string_answer_contains_any_items(
    valid_items: list[str],
) -> None:
    """Preserve string-only answer_contains_any lists."""
    matrix = {
        "scenarios": [
            {
                "id": "valid-items",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "answer_contains_any": valid_items,
                },
            }
        ]
    }

    scenarios = validate_matrix(matrix)
    assert scenarios[0]["pass_criteria"]["answer_contains_any"] == valid_items


@pytest.mark.parametrize(
    "blank_items",
    [
        [""],
        ["   "],
        ["\n"],
        ["\t"],
        ["foo", ""],
        ["foo", "   "],
    ],
)
def test_validate_matrix_rejects_blank_answer_contains_any_items(
    blank_items: list[str],
) -> None:
    """Reject blank items inside answer_contains_any lists."""
    invalid_matrix = {
        "scenarios": [
            {
                "id": "blank-items",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "answer_contains_any": blank_items,
                },
            }
        ]
    }

    with pytest.raises(SmokeScenarioMatrixError, match="must not be blank"):
        validate_matrix(invalid_matrix)


@pytest.mark.parametrize(
    "valid_items",
    [
        [],
        ["foo"],
        ["foo", "bar"],
        [" foo "],
    ],
)
def test_validate_matrix_preserves_non_blank_answer_contains_any_items(
    valid_items: list[str],
) -> None:
    """Preserve non-blank answer_contains_any lists."""
    matrix = {
        "scenarios": [
            {
                "id": "valid-blank",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "answer_contains_any": valid_items,
                },
            }
        ]
    }

    scenarios = validate_matrix(matrix)
    assert scenarios[0]["pass_criteria"]["answer_contains_any"] == valid_items


@pytest.mark.parametrize(
    "duplicate_items",
    [
        ["foo", "foo"],
        ["foo", "bar", "foo"],
    ],
)
def test_validate_matrix_rejects_duplicate_answer_contains_any_items(
    duplicate_items: list[str],
) -> None:
    """Reject duplicate items inside answer_contains_any lists."""
    invalid_matrix = {
        "scenarios": [
            {
                "id": "duplicate-items",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "answer_contains_any": duplicate_items,
                },
            }
        ]
    }

    with pytest.raises(
        SmokeScenarioMatrixError, match="answer_contains_any items must be unique"
    ):
        validate_matrix(invalid_matrix)


@pytest.mark.parametrize(
    "distinct_items",
    [
        pytest.param(["foo"], id="single-item"),
        pytest.param(["foo", "bar"], id="distinct-items"),
        pytest.param(["foo", "Foo"], id="case-distinct-items"),
        pytest.param(["foo", " foo "], id="whitespace-distinct-items"),
    ],
)
def test_validate_matrix_preserves_distinct_answer_contains_any_items(
    distinct_items: list[str],
) -> None:
    """Preserve distinct answer_contains_any lists."""
    matrix = {
        "scenarios": [
            {
                "id": "distinct-items",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    "answer_contains_any": distinct_items,
                },
            }
        ]
    }

    scenarios = validate_matrix(matrix)
    assert (
        scenarios[0]["pass_criteria"]["answer_contains_any"]
        == distinct_items
    )


@pytest.mark.parametrize(
    "unknown_key",
    [
        pytest.param("unknown_key", id="unknown-key"),
        pytest.param("answer_contain_any", id="typo-answer-contains-any"),
        pytest.param("minimum_sources", id="typo-min-sources"),
    ],
)
def test_validate_matrix_rejects_unknown_pass_criteria_keys(
    unknown_key: str,
) -> None:
    """Reject unknown pass_criteria keys."""
    matrix = {
        "scenarios": [
            {
                "id": "unknown-key",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "no_cross_site_urls": True,
                    unknown_key: "some_value",
                },
            }
        ]
    }

    with pytest.raises(
        SmokeScenarioMatrixError, match="contains unknown keys"
    ):
        validate_matrix(matrix)


def test_validate_matrix_preserves_known_pass_criteria_keys() -> None:
    """Preserve all known pass_criteria keys with valid values."""
    matrix = {
        "scenarios": [
            {
                "id": "all-known-keys",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "source_domain": "bukgu.gwangju.kr",
                    "no_cross_site_urls": True,
                    "answer_contains_any": ["foo"],
                    "answer_not_empty": True,
                    "fallback_required": False,
                    "fallback_when_no_source": True,
                },
            }
        ]
    }

    scenarios = validate_matrix(matrix)
    assert scenarios[0]["id"] == "all-known-keys"


def test_validate_matrix_allows_missing_optional_pass_criteria_keys() -> None:
    """Allow missing optional pass_criteria keys."""
    matrix = {
        "scenarios": [
            {
                "id": "required-only",
                "site_id": "bukgu_gwangju",
                "category": "service_navigation",
                "question": "민원서식은 어디에서 확인하나요?",
                "expected_domain": "bukgu.gwangju.kr",
                "expected_keywords": ["민원서식"],
                "pass_criteria": {
                    "site_id_match": True,
                    "min_sources": 1,
                    "source_domain": "bukgu.gwangju.kr",
                    "no_cross_site_urls": True,
                },
            }
        ]
    }

    scenarios = validate_matrix(matrix)
    assert scenarios[0]["id"] == "required-only"


def test_load_matrix_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"

    with pytest.raises(SmokeScenarioMatrixError, match="Matrix file not found"):
        load_matrix(missing_path)


def _scenario_by_id(scenario_id: str) -> dict:
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    scenarios = validate_matrix(matrix)
    return next(scenario for scenario in scenarios if scenario["id"] == scenario_id)


def _scenario_list() -> list[dict]:
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    return validate_matrix(matrix)


def test_evaluate_response_passes_grounded_pipeline_shaped_response() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"] == {
        "site_id_match": True,
        "min_sources": True,
        "source_domain": True,
        "no_cross_site_urls": True,
        "answer_contains_any": True,
    }


def test_stage243_evaluate_response_treats_boolean_true_min_sources_as_one() -> None:
    """Treat boolean True min_sources as integer one under current contract."""
    scenario = _scenario_by_id("bukgu-01")
    scenario = {
        **scenario,
        "pass_criteria": {
            **scenario["pass_criteria"],
            "min_sources": True,
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["answer_contains_any"] is True


def test_stage245_evaluate_response_ignores_non_string_answer_keywords_when_one_string_matches() -> None:
    """Ignore non-string answer keywords when at least one string keyword matches."""
    scenario = _scenario_by_id("bukgu-01")
    scenario = {
        **scenario,
        "pass_criteria": {
            **scenario["pass_criteria"],
            "answer_contains_any": ["민원서식", "외계", True, {}, []],
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["answer_contains_any"] is True


def test_stage246_evaluate_response_fails_non_string_only_answer_keywords() -> None:
    """Fail answer_contains_any when all configured keywords are non-string values."""
    scenario = _scenario_by_id("bukgu-01")
    scenario = {
        **scenario,
        "pass_criteria": {
            **scenario["pass_criteria"],
            "answer_contains_any": [123, None],
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["failures"] == ["answer_contains_any"]
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["answer_contains_any"] is False


def test_stage247_evaluate_response_omits_empty_answer_keyword_list() -> None:
    """Omit answer_contains_any when the configured keyword list is empty."""
    scenario = _scenario_by_id("bukgu-01")
    scenario = {
        **scenario,
        "pass_criteria": {
            **scenario["pass_criteria"],
            "answer_contains_any": [],
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "북구청 종합민원 메뉴에서 관련 자료를 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert "answer_contains_any" not in result["checks"]


def test_stage248_evaluate_response_falls_back_to_expected_domain_when_source_domain_falsey() -> None:
    """Fall back to expected_domain when pass_criteria.source_domain is falsey."""
    scenario = _scenario_by_id("bukgu-01")
    scenario = {
        **scenario,
        "pass_criteria": {
            **scenario["pass_criteria"],
            "source_domain": "",
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["answer_contains_any"] is True


def test_stage251_evaluate_response_passes_answer_not_empty_for_non_empty_answer() -> None:
    """Pass answer_not_empty when the response answer is a non-empty string."""
    scenario = _scenario_by_id("bukgu-01")
    scenario = {
        **scenario,
        "pass_criteria": {
            **scenario["pass_criteria"],
            "answer_not_empty": True,
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["answer_contains_any"] is True
    assert result["checks"]["answer_not_empty"] is True


def test_stage252_evaluate_response_fails_answer_not_empty_for_whitespace_only_answer() -> None:
    """Fail answer_not_empty when the response answer contains only whitespace."""
    scenario = _scenario_by_id("bukgu-01")
    scenario = {
        **scenario,
        "pass_criteria": {
            **scenario["pass_criteria"],
            "answer_contains_any": [],
            "answer_not_empty": True,
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "   \n\t  ",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["failures"] == ["answer_not_empty"]
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert "answer_contains_any" not in result["checks"]
    assert result["checks"]["answer_not_empty"] is False


def test_stage253_evaluate_response_passes_fallback_required_with_explicit_fallback() -> None:
    """Pass fallback_required when the response explicitly sets fallback=True."""
    scenario = _scenario_by_id("bukgu-03")
    scenario = {
        **scenario,
        "pass_criteria": {
            "fallback_required": True,
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "요청하신 내용은 현재 제공된 근거 안에서 확정하기 어렵습니다.",
        "sources": [],
        "fallback": True,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"] == {
        "fallback_required": True,
    }


def test_stage254_evaluate_response_fails_fallback_required_without_fallback_flag_or_marker() -> None:
    """Fail fallback_required when the response has no fallback flag and no fallback marker."""
    scenario = _scenario_by_id("bukgu-03")
    scenario = {
        **scenario,
        "pass_criteria": {
            "fallback_required": True,
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "일반적인 안내 문구입니다.",
        "sources": [],
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["failures"] == ["fallback_required"]
    assert result["checks"] == {
        "fallback_required": False,
    }


def test_stage255_evaluate_response_passes_fallback_required_with_fallback_marker_only() -> None:
    """Pass fallback_required when the response has a fallback marker but no fallback flag."""
    scenario = _scenario_by_id("bukgu-03")
    scenario = {
        **scenario,
        "pass_criteria": {
            "fallback_required": True,
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "해당 내용은 홈페이지에서 직접 확인해 주세요.",
        "sources": [],
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"] == {
        "fallback_required": True,
    }


def test_stage256_evaluate_response_passes_fallback_when_no_source_with_valid_sources() -> None:
    """Pass fallback_when_no_source when the response has valid sources."""
    scenario = _scenario_by_id("bukgu-01")
    scenario = {
        **scenario,
        "pass_criteria": {
            "fallback_when_no_source": True,
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"]["fallback_when_no_source"] is True


def test_stage257_evaluate_response_passes_fallback_when_no_source_with_fallback_flag_when_sources_empty() -> None:
    """Pass fallback_when_no_source when sources are empty but fallback flag is set."""
    scenario = _scenario_by_id("bukgu-03")
    scenario = {
        **scenario,
        "pass_criteria": {
            "fallback_when_no_source": True,
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "요청하신 내용은 현재 제공된 근거 안에서 확정하기 어렵습니다.",
        "sources": [],
        "fallback": True,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"]["fallback_when_no_source"] is True


def test_stage258_evaluate_response_fails_fallback_when_no_source_with_empty_sources_and_no_fallback() -> None:
    """Fail fallback_when_no_source when sources are empty and response is not fallback."""
    scenario = _scenario_by_id("bukgu-03")
    scenario = {
        **scenario,
        "pass_criteria": {
            "fallback_when_no_source": True,
        },
    }
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "일반 안내 문장입니다.",
        "sources": [],
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["failures"] == ["fallback_when_no_source"]
    assert result["checks"] == {
        "fallback_when_no_source": False,
    }


def test_stage228_evaluate_response_ignores_non_dict_source_entries() -> None:
    """Ignore non-dict source entries while preserving valid dict sources."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            "ignored-source",
            123,
            None,
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            },
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["failures"] == []
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["answer_contains_any"] is True


def test_stage230_evaluate_response_treats_non_dict_only_sources_as_empty() -> None:
    """Treat a sources list with only non-dict entries as empty filtered sources."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            "ignored-source",
            123,
            None,
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is False
    assert "source_domain" not in result["checks"]
    assert "no_cross_site_urls" not in result["checks"]
    assert "min_sources" in result["failures"]


def test_stage232_evaluate_response_treats_missing_sources_as_empty() -> None:
    """Treat a missing sources field as empty filtered sources."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is False
    assert "source_domain" not in result["checks"]
    assert "no_cross_site_urls" not in result["checks"]
    assert "min_sources" in result["failures"]


def test_stage233_evaluate_response_treats_non_list_sources_as_empty() -> None:
    """Treat non-list sources as empty filtered sources."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": {
            "title": "민원서식",
            "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
        },
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is False
    assert "source_domain" not in result["checks"]
    assert "no_cross_site_urls" not in result["checks"]
    assert "min_sources" in result["failures"]


def test_evaluate_response_fails_cross_site_source_url() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://gwangju.go.kr/example",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert "source_domain" in result["failures"]
    assert "no_cross_site_urls" in result["failures"]


def test_stage203_evaluate_response_requires_source_title_for_source_domain() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is False
    assert result["checks"]["no_cross_site_urls"] is True
    assert "source_domain" in result["failures"]
    assert "no_cross_site_urls" not in result["failures"]


def test_stage205_evaluate_response_accepts_href_source_url_alias() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "href": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True


def test_stage206_evaluate_response_accepts_link_source_url_alias() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "link": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True


def test_stage208_evaluate_response_prefers_url_over_href_and_link_aliases() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://gwangju.go.kr/example",
                "href": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
                "link": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["source_domain"] is False
    assert result["checks"]["no_cross_site_urls"] is False
    assert "source_domain" in result["failures"]
    assert "no_cross_site_urls" in result["failures"]


def test_stage210_evaluate_response_accepts_name_source_title_alias() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "name": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True


def test_stage212_evaluate_response_falls_back_to_name_when_title_is_blank() -> None:
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "",
                "name": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True


def test_evaluate_response_fails_when_min_sources_not_met() -> None:
    scenario = _scenario_by_id("gwangju-01")
    response = {
        "site_id": "gwangju_go_kr",
        "answer": "고시공고는 광주시청 홈페이지에서 확인할 수 있습니다.",
        "sources": [],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["min_sources"] is False
    assert "min_sources" in result["failures"]


def test_evaluate_response_fails_when_answer_keyword_missing() -> None:
    scenario = _scenario_by_id("gwangju-02")
    response = {
        "site_id": "gwangju_go_kr",
        "answer": "해당 내용은 광주시청 홈페이지에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "정보공개",
                "url": "https://www.gwangju.go.kr/example",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["answer_contains_any"] is False
    assert "answer_contains_any" in result["failures"]


def test_stage237_evaluate_response_treats_missing_answer_as_empty_for_keyword_check() -> None:
    """Treat missing answer as empty for answer_contains_any."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["answer_contains_any"] is False
    assert result["failures"] == ["answer_contains_any"]


def test_stage238_evaluate_response_treats_non_string_answer_as_empty_for_keyword_check() -> None:
    """Treat non-string answer as empty for answer_contains_any."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": 123,
        "sources": [
            {
                "title": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["answer_contains_any"] is False
    assert result["failures"] == ["answer_contains_any"]


def test_stage241_evaluate_response_rejects_non_string_answer_fallback_marker_without_flag() -> None:
    """Reject marker-based fallback when answer is non-string and fallback flag is absent."""
    scenario = _scenario_by_id("bukgu-03")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": 123,
        "sources": [],
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["answer_contains_any"] is False
    assert result["checks"]["fallback_when_no_source"] is False
    assert "source_domain" not in result["checks"]
    assert "no_cross_site_urls" not in result["checks"]
    assert "answer_contains_any" in result["failures"]
    assert "fallback_when_no_source" in result["failures"]


def test_evaluate_response_accepts_fallback_when_sources_are_empty() -> None:
    scenario = _scenario_by_id("bukgu-03")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "주민등록등본 발급 관련 출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
        "sources": [],
        "fallback": True,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["fallback_when_no_source"] is True


def test_stage201_evaluate_response_accepts_fallback_marker_without_flag() -> None:
    scenario = _scenario_by_id("bukgu-03")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "주민등록등본 발급 관련 출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
        "sources": [],
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["fallback_when_no_source"] is True


def test_stage234_evaluate_response_accepts_fallback_marker_when_sources_missing() -> None:
    """Accept fallback marker text when the sources field is missing."""
    scenario = _scenario_by_id("bukgu-03")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "주민등록등본 발급 관련 출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert "source_domain" not in result["checks"]
    assert "no_cross_site_urls" not in result["checks"]
    assert result["checks"]["answer_contains_any"] is True
    assert result["checks"]["fallback_when_no_source"] is True


def test_stage235_evaluate_response_accepts_fallback_marker_when_sources_is_non_list() -> None:
    """Accept fallback marker text when sources is present but not a list."""
    scenario = _scenario_by_id("bukgu-03")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "주민등록등본 발급 관련 출처가 부족하므로 홈페이지에서 직접 확인해 주세요.",
        "sources": {
            "title": "주민등록등본",
            "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
        },
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert "source_domain" not in result["checks"]
    assert "no_cross_site_urls" not in result["checks"]
    assert result["checks"]["answer_contains_any"] is True
    assert result["checks"]["fallback_when_no_source"] is True


def test_evaluate_response_requires_fallback_for_low_confidence_case() -> None:
    scenario = _scenario_by_id("gwangju-07")
    response = {
        "site_id": "gwangju_go_kr",
        "answer": "외계인 등록증은 광주시청에서 신청할 수 있습니다.",
        "sources": [],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["fallback_required"] is False
    assert "fallback_required" in result["failures"]


def test_stage240_evaluate_response_keeps_answer_not_empty_failing_when_fallback_flag_is_true() -> None:
    """Allow fallback flag while keeping missing answer_not_empty failure."""
    scenario = _scenario_by_id("gwangju-07")
    response = {
        "site_id": "gwangju_go_kr",
        "sources": [],
        "fallback": True,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["answer_not_empty"] is False
    assert result["checks"]["fallback_required"] is True
    assert "source_domain" not in result["checks"]
    assert "no_cross_site_urls" not in result["checks"]
    assert result["failures"] == ["answer_not_empty"]


def test_evaluate_response_detects_site_id_mismatch() -> None:
    scenario = _scenario_by_id("bukgu-06")
    response = {
        "site_id": "gwangju_go_kr",
        "answer": "지원금 관련 정보는 홈페이지에서 직접 확인해 주세요.",
        "sources": [],
        "fallback": True,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is False
    assert "site_id_match" in result["failures"]


def test_stage239_evaluate_response_rejects_whitespace_only_answer_for_answer_not_empty() -> None:
    """Reject whitespace-only answers for answer_not_empty and no-source fallback."""
    scenario = _scenario_by_id("bukgu-06")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "   ",
        "sources": [],
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["answer_not_empty"] is False
    assert result["checks"]["fallback_when_no_source"] is False
    assert "source_domain" not in result["checks"]
    assert "no_cross_site_urls" not in result["checks"]
    assert "answer_not_empty" in result["failures"]
    assert "fallback_when_no_source" in result["failures"]


def test_response_fixture_loads_and_passes_all_scenarios() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    responses_by_id = validate_response_fixture(fixture, scenarios)
    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)

    assert len(responses_by_id) == 14
    assert summary["total"] == 14
    assert summary["passed"] == 14
    assert summary["failed"] == 0
    assert summary["failed_results"] == []


def test_run_response_eval_returns_passed_report() -> None:
    report, passed = run_response_eval(DEFAULT_MATRIX_PATH, RESPONSE_FIXTURE_PATH)

    assert passed is True
    assert "Smoke response eval loaded" in report
    assert "Evaluated responses: 14" in report
    assert "Passed: 14" in report
    assert "Failed: 0" in report
    assert "Status: response eval passed" in report


def test_response_eval_reports_failed_scenario() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    responses_by_id = validate_response_fixture(fixture, scenarios)
    responses_by_id["bukgu-01"] = {
        "scenario_id": "bukgu-01",
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청에서 확인할 수 있습니다.",
        "sources": [{"title": "민원서식", "url": "https://gwangju.go.kr/example"}],
        "fallback": False,
    }

    results = evaluate_response_fixture(scenarios, responses_by_id)
    summary = build_response_eval_summary(results)

    assert summary["passed"] == 13
    assert summary["failed"] == 1
    assert summary["failed_results"][0]["scenario_id"] == "bukgu-01"
    assert "source_domain" in summary["failed_results"][0]["failures"]
    assert "no_cross_site_urls" in summary["failed_results"][0]["failures"]


def test_validate_response_fixture_rejects_duplicate_scenario_id() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    duplicate = dict(fixture["responses"][0])
    fixture["responses"].append(duplicate)

    with pytest.raises(SmokeResponseFixtureError, match="Duplicate response scenario_id"):
        validate_response_fixture(fixture, scenarios)


def test_validate_response_fixture_rejects_unknown_scenario_id() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    fixture["responses"][0] = dict(fixture["responses"][0], scenario_id="unknown-01")

    with pytest.raises(SmokeResponseFixtureError, match="Unknown response scenario_id"):
        validate_response_fixture(fixture, scenarios)


def test_validate_response_fixture_rejects_missing_scenario_id() -> None:
    scenarios = _scenario_list()
    fixture = load_response_fixture(RESPONSE_FIXTURE_PATH)
    fixture["responses"] = fixture["responses"][:-1]

    with pytest.raises(SmokeResponseFixtureError, match="missing scenario_id values"):
        validate_response_fixture(fixture, scenarios)


def test_stage64_live_opt_in_defaults_to_disabled() -> None:
    env = {}

    assert is_live_eval_enabled(env) is False

    with pytest.raises(SmokeLiveEvalGuardError, match=LIVE_EVAL_ENV_VAR):
        run_live_eval_guard(env)


def test_stage64_live_guard_remains_non_executing_even_when_enabled() -> None:
    env = {LIVE_EVAL_ENV_VAR: "true"}

    report = run_live_eval_guard(env)

    assert "explicitly enabled" in report
    assert "not implemented" in report
    assert "No live provider, fetch, or pipeline calls were made." in report


def test_stage64_preflight_reports_missing_config_without_values() -> None:
    summary = build_live_eval_preflight({})
    report = format_live_eval_preflight(summary)

    assert summary["live_enabled"] is False
    assert summary["missing"] == list(LIVE_PREFLIGHT_CONFIG_NAMES)
    assert "Live opt-in: disabled" in report
    for name in LIVE_PREFLIGHT_CONFIG_NAMES:
        assert f"- {name}: missing" in report
    assert "No live provider, fetch, network, or pipeline calls were made." in report


def test_stage64_preflight_reports_set_missing_only_and_redacts_values() -> None:
    env = {
        LIVE_EVAL_ENV_VAR: "true",
        "AI_FINDER_LIVE_PROVIDER": "secret-provider-token-123",
        "AI_FINDER_LIVE_FETCH_PROVIDER": "secret-fetch-token-456",
    }

    summary = build_live_eval_preflight(env)
    report = run_live_eval_preflight(env)

    assert summary["live_enabled"] is True
    assert summary["missing"] == []
    for name in LIVE_PREFLIGHT_CONFIG_NAMES:
        assert f"- {name}: set" in report
    assert "secret-provider-token-123" not in report
    assert "secret-fetch-token-456" not in report
    assert "Status: preflight completed" in report
    assert "No live provider, fetch, network, or pipeline calls were made." in report


def test_stage64_preflight_does_not_treat_non_true_opt_in_as_enabled() -> None:
    env = {
        LIVE_EVAL_ENV_VAR: "1",
        "AI_FINDER_LIVE_PROVIDER": "provider-name-should-not-print",
        "AI_FINDER_LIVE_FETCH_PROVIDER": "fetch-name-should-not-print",
    }

    summary = build_live_eval_preflight(env)
    report = format_live_eval_preflight(summary)

    assert summary["live_enabled"] is False
    assert summary["missing"] == []
    assert "Live opt-in: disabled" in report
    assert "provider-name-should-not-print" not in report
    assert "fetch-name-should-not-print" not in report


def test_stage214_evaluate_response_rejects_truthy_non_string_source_title() -> None:
    """Reject truthy non-string title before falling back to name."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": 123,
                "name": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["source_domain"] is False
    assert "source_domain" in result["failures"]
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
    assert result["checks"]["no_cross_site_urls"] is True


def test_stage226_evaluate_response_falls_back_to_name_when_title_is_falsey() -> None:
    """Fall back to name when title is falsey non-string."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": 0,
                "name": "민원서식",
                "url": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True


def test_stage216_evaluate_response_rejects_truthy_non_string_source_url() -> None:
    """Reject truthy non-string url before falling back to href/link."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": 123,
                "href": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["source_domain"] is False
    assert result["checks"]["no_cross_site_urls"] is False
    assert "source_domain" in result["failures"]
    assert "no_cross_site_urls" in result["failures"]
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True


def test_stage218_evaluate_response_falls_back_to_href_when_url_is_falsey() -> None:
    """Fall back to href when url is falsey non-string (e.g. integer 0)."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": 0,
                "href": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True


def test_stage220_evaluate_response_rejects_truthy_non_string_href_before_link() -> None:
    """Reject truthy non-string href before falling back to link."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "",
                "href": 123,
                "link": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["source_domain"] is False
    assert result["checks"]["no_cross_site_urls"] is False
    assert "source_domain" in result["failures"]
    assert "no_cross_site_urls" in result["failures"]
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True


def test_stage222_evaluate_response_falls_back_to_link_when_href_is_falsey() -> None:
    """Fall back to link when url and href are both falsey."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "",
                "href": 0,
                "link": "https://bukgu.gwangju.kr/menu.es?mid=a10102000000",
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is True
    assert result["checks"]["source_domain"] is True
    assert result["checks"]["no_cross_site_urls"] is True
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True


def test_stage224_evaluate_response_rejects_terminal_non_string_link() -> None:
    """Reject terminal non-string link after url and href fall through."""
    scenario = _scenario_by_id("bukgu-01")
    response = {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청 종합민원 민원서식 메뉴에서 확인할 수 있습니다.",
        "sources": [
            {
                "title": "민원서식",
                "url": "",
                "href": 0,
                "link": 123,
            }
        ],
        "fallback": False,
    }

    result = evaluate_response(scenario, response)

    assert result["passed"] is False
    assert result["checks"]["source_domain"] is False
    assert result["checks"]["no_cross_site_urls"] is False
    assert "source_domain" in result["failures"]
    assert "no_cross_site_urls" in result["failures"]
    assert result["checks"]["site_id_match"] is True
    assert result["checks"]["min_sources"] is True
