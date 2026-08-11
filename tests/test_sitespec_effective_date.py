"""Contract tests for the effective-date jurisdiction resolver (#1225-E).

Pure stdlib + pytest only. No network, no provider, no Firecrawl, no live
provider calls.

``resolve_jurisdiction_at(spec, as_of)`` selects the jurisdiction name that
was legally effective on a given calendar date (``as_of``), using the canonical
SiteSpec ``jurisdiction`` block. It is a **date-aware name resolver**, not a
site-ID resolver: historical jurisdiction aliases are legal-identity snapshots
and are never promoted to runtime site identifiers.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.site_profiles.sitespec import (
    JurisdictionResolutionError,
    SiteSpecResolver,
    resolve_jurisdiction_at,
    resolve_site_id,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SITES_DIR = REPO_ROOT / "configs" / "sites"
INSTANCE_PATH = SITES_DIR / "bukgu_gwangju.sitespec.json"

CANONICAL_ID = "bukgu_gwangju"
LEGACY_ID = "bukgu"

CANONICAL_NAME = "전남광주통합특별시 북구"
HISTORICAL_NAME = "광주광역시 북구"

CANONICAL_EFFECTIVE_FROM = "2026-07-01"
HISTORICAL_EFFECTIVE_UNTIL = "2026-06-30"


def _load_sitespec() -> dict:
    with open(INSTANCE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_sitespec(
    tmp_path: Path,
    *,
    site_id: str = "sample_site",
    legacy_ids: list[str] | None = None,
    canonical_name: str = "Canonical Sample",
    effective_from: str = "2026-07-01",
    historical_aliases: list[dict] | None = None,
    canonical: bool = True,
) -> dict:
    """Write a generic SiteSpec fixture to ``tmp_path`` and return the dict."""
    if legacy_ids is None:
        legacy_ids = []
    if historical_aliases is None:
        historical_aliases = []
    doc = {
        "$schema": "configs/sitespec.schema.json",
        "schema_version": "1.0.0",
        "site_id": site_id,
        "legacy_ids": legacy_ids,
        "jurisdiction": {
            "canonical_name": canonical_name,
            "short_name": "Sample",
            "effective_from": effective_from,
            "historical_aliases": historical_aliases,
        },
        "display": {
            "default_label": f"Sample {site_id}",
            "locale_labels": {
                "ko": f"Sample {site_id}",
                "en": f"Sample {site_id}",
            },
        },
        "domains": {"public": [f"{site_id}.example.kr"]},
        "runtime": {"python_profile": site_id, "cloudflare_adapter": site_id},
        "clone": {
            "golden_commit": "0" * 40,
            "golden_commit_subject": "sample",
        },
    }
    path = tmp_path / f"{site_id}.sitespec.json"
    path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return doc


# ---------------------------------------------------------------------------
# A. Buk-gu boundary
# ---------------------------------------------------------------------------

class TestBukguBoundary:
    """The canonical/historical date boundary for Buk-gu must be exact."""

    def test_day_before_canonical_is_historical(self):
        spec = _load_sitespec()
        result = resolve_jurisdiction_at(spec, HISTORICAL_EFFECTIVE_UNTIL)
        assert result["canonical_site_id"] == CANONICAL_ID
        assert result["as_of"] == HISTORICAL_EFFECTIVE_UNTIL
        assert result["name"] == HISTORICAL_NAME
        assert result["resolution_kind"] == "historical_alias"
        assert result["effective_until"] == HISTORICAL_EFFECTIVE_UNTIL
        assert "effective_from" not in result

    def test_canonical_effective_date_is_canonical(self):
        spec = _load_sitespec()
        result = resolve_jurisdiction_at(spec, CANONICAL_EFFECTIVE_FROM)
        assert result["canonical_site_id"] == CANONICAL_ID
        assert result["as_of"] == CANONICAL_EFFECTIVE_FROM
        assert result["name"] == CANONICAL_NAME
        assert result["resolution_kind"] == "canonical"
        assert result["effective_from"] == CANONICAL_EFFECTIVE_FROM
        assert "effective_until" not in result

    @pytest.mark.parametrize("as_of", [
        "2026-07-02",
        "2026-07-15",
        "2026-12-31",
        "2027-01-01",
        "2030-06-15",
    ])
    def test_post_canonical_dates_are_canonical(self, as_of):
        spec = _load_sitespec()
        result = resolve_jurisdiction_at(spec, as_of)
        assert result["resolution_kind"] == "canonical"
        assert result["name"] == CANONICAL_NAME
        assert result["effective_from"] == CANONICAL_EFFECTIVE_FROM

    def test_representative_prior_date_is_historical(self):
        """A representative pre-canonical date resolves to the historical alias."""
        spec = _load_sitespec()
        result = resolve_jurisdiction_at(spec, "2026-06-15")
        assert result["resolution_kind"] == "historical_alias"
        assert result["name"] == HISTORICAL_NAME
        assert result["effective_until"] == HISTORICAL_EFFECTIVE_UNTIL

    def test_canonical_name_is_not_historical_alias(self):
        """The canonical name itself is the canonical identity, not an alias."""
        spec = _load_sitespec()
        result = resolve_jurisdiction_at(spec, "2026-05-01")
        assert result["name"] == HISTORICAL_NAME
        assert result["name"] != CANONICAL_NAME


# ---------------------------------------------------------------------------
# B. Site identity separation
# ---------------------------------------------------------------------------

class TestSiteIdentitySeparation:
    """Canonical and legacy IDs resolve to the same SiteSpec, then share the
    same date-aware jurisdiction selection. But a historical alias value is
    not a site ID."""

    def test_canonical_id_resolves_then_date_selects(self):
        spec = resolve_site_id(CANONICAL_ID)
        result = resolve_jurisdiction_at(spec, "2026-06-30")
        assert result["canonical_site_id"] == CANONICAL_ID
        assert result["name"] == HISTORICAL_NAME
        assert result["resolution_kind"] == "historical_alias"

    def test_legacy_id_resolves_to_same_spec_then_date_selects(self):
        canonical_spec = resolve_site_id(CANONICAL_ID)
        legacy_spec = resolve_site_id(LEGACY_ID)
        assert canonical_spec == legacy_spec
        result_canonical = resolve_jurisdiction_at(canonical_spec, "2026-07-01")
        result_legacy = resolve_jurisdiction_at(legacy_spec, "2026-06-30")
        assert result_canonical["name"] == CANONICAL_NAME
        assert result_legacy["name"] == HISTORICAL_NAME
        # Both share the same canonical_site_id regardless of entry path.
        assert result_canonical["canonical_site_id"] == CANONICAL_ID
        assert result_legacy["canonical_site_id"] == CANONICAL_ID

    def test_resolver_method_same_result(self):
        """Using SiteSpecResolver.resolve() then resolve_jurisdiction_at()."""
        resolver = SiteSpecResolver()
        for identifier in (CANONICAL_ID, LEGACY_ID):
            spec = resolver.resolve(identifier)
            result = resolve_jurisdiction_at(spec, "2026-07-01")
            assert result["canonical_site_id"] == CANONICAL_ID
            assert result["name"] == CANONICAL_NAME

    def test_historical_alias_string_is_not_a_site_id(self):
        """The historical alias value must not resolve as a site identifier."""
        from src.site_profiles.sitespec import SiteSpecNotFoundError

        with pytest.raises(SiteSpecNotFoundError):
            resolve_site_id(HISTORICAL_NAME)

    def test_historical_alias_value_is_jurisdiction_name_not_site(self):
        """resolve_jurisdiction_at returns the alias as a *name*, not a redirect."""
        spec = _load_sitespec()
        result = resolve_jurisdiction_at(spec, "2026-06-30")
        assert result["name"] == HISTORICAL_NAME
        # resolution_kind distinguishes jurisdiction name selection from
        # site-ID alias resolution.
        assert result["resolution_kind"] == "historical_alias"


# ---------------------------------------------------------------------------
# C. Invalid input
# ---------------------------------------------------------------------------

class TestInvalidInput:
    """All malformed inputs fail-closed."""

    @pytest.mark.parametrize("bad_as_of", [
        "",
        "   ",
        "not-a-date",
        "2026/07/01",
        "2026-7-1",
        "26-07-01",
        "20261301",
        "abcd-ef-gh",
    ])
    def test_malformed_as_of_fail_closed(self, bad_as_of):
        spec = _load_sitespec()
        with pytest.raises(JurisdictionResolutionError):
            resolve_jurisdiction_at(spec, bad_as_of)

    def test_non_string_as_of_fail_closed(self):
        spec = _load_sitespec()
        with pytest.raises(JurisdictionResolutionError):
            resolve_jurisdiction_at(spec, 20260701)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad_date", [
        "2026-02-30",
        "2026-02-31",
        "2026-13-01",
        "2026-00-01",
        "2026-04-31",
        "2026-11-31",
        "0000-00-00",
        "2026-02-29",
    ])
    def test_impossible_calendar_date_fail_closed(self, bad_date):
        """date.fromisoformat rejects these; the resolver must too."""
        spec = _load_sitespec()
        with pytest.raises(JurisdictionResolutionError):
            resolve_jurisdiction_at(spec, bad_date)

    def test_malformed_canonical_effective_from_fail_closed(self, tmp_path):
        doc = _write_sitespec(
            tmp_path,
            site_id="bad_effective_from",
            legacy_ids=[],
            effective_from="2026-02-30",
            historical_aliases=[
                {"value": "Old Name", "effective_until": "2026-02-28"},
            ],
        )
        with pytest.raises(JurisdictionResolutionError):
            resolve_jurisdiction_at(doc, "2026-01-01")

    def test_malformed_canonical_effective_from_format_fail_closed(self, tmp_path):
        doc = _write_sitespec(
            tmp_path,
            site_id="bad_format_from",
            legacy_ids=[],
            effective_from="July 1 2026",
        )
        with pytest.raises(JurisdictionResolutionError):
            resolve_jurisdiction_at(doc, "2026-06-30")

    def test_malformed_historical_effective_until_fail_closed(self, tmp_path):
        doc = _write_sitespec(
            tmp_path,
            site_id="bad_alias",
            legacy_ids=[],
            effective_from="2026-07-01",
            historical_aliases=[
                {"value": "Old Name", "effective_until": "2026-02-30"},
            ],
        )
        with pytest.raises(JurisdictionResolutionError):
            resolve_jurisdiction_at(doc, "2026-06-30")

    def test_missing_jurisdiction_block_fail_closed(self, tmp_path):
        doc = {
            "site_id": "no_jurisdiction",
            "legacy_ids": [],
            "jurisdiction": None,
        }
        with pytest.raises(JurisdictionResolutionError):
            resolve_jurisdiction_at(doc, "2026-07-01")

    def test_missing_canonical_name_fail_closed(self, tmp_path):
        doc = _write_sitespec(
            tmp_path,
            site_id="no_name",
            legacy_ids=[],
            canonical_name="",
        )
        with pytest.raises(JurisdictionResolutionError):
            resolve_jurisdiction_at(doc, "2026-07-01")

    def test_missing_site_id_fail_closed(self, tmp_path):
        doc = {
            "site_id": "",
            "legacy_ids": [],
            "jurisdiction": {
                "canonical_name": "Test",
                "short_name": "T",
                "effective_from": "2026-07-01",
                "historical_aliases": [],
            },
        }
        with pytest.raises(JurisdictionResolutionError):
            resolve_jurisdiction_at(doc, "2026-07-01")


# ---------------------------------------------------------------------------
# D. Incomplete / ambiguous timeline
# ------------------------------------------------------------------

class TestIncompleteAndAmbiguousTimeline:
    """Gap, ambiguity, and overlap cases all fail-closed."""

    def test_no_historical_candidate_for_pre_canonical_date_fail_closed(self, tmp_path):
        """Pre-canonical date with zero matching historical aliases → gap."""
        doc = _write_sitespec(
            tmp_path,
            site_id="no_candidate",
            legacy_ids=[],
            effective_from="2026-07-01",
            historical_aliases=[
                {"value": "Old A", "effective_until": "2026-06-15"},
            ],
        )
        # 2026-06-20 is before canonical and past the only alias's effective_until.
        with pytest.raises(JurisdictionResolutionError, match="unrepresented historical gap"):
            resolve_jurisdiction_at(doc, "2026-06-20")

    def test_two_historical_candidates_ambiguous_fail_closed(self, tmp_path):
        """Two aliases covering the same as_of date → ambiguous timeline."""
        doc = _write_sitespec(
            tmp_path,
            site_id="ambiguous",
            legacy_ids=[],
            effective_from="2026-07-01",
            historical_aliases=[
                {"value": "Old A", "effective_until": "2026-06-30"},
                {"value": "Old B", "effective_until": "2026-06-30"},
            ],
        )
        with pytest.raises(JurisdictionResolutionError, match="ambiguous timeline"):
            resolve_jurisdiction_at(doc, "2026-06-15")

    def test_historical_canonical_overlap_fail_closed(self, tmp_path):
        """A historical effective_until == canonical effective_from is overlap."""
        doc = _write_sitespec(
            tmp_path,
            site_id="overlap_equal",
            legacy_ids=[],
            effective_from=CANONICAL_EFFECTIVE_FROM,
            historical_aliases=[
                {"value": "Old", "effective_until": CANONICAL_EFFECTIVE_FROM},
            ],
        )
        with pytest.raises(JurisdictionResolutionError, match="overlap"):
            resolve_jurisdiction_at(doc, "2026-06-15")

    def test_historical_after_canonical_overlap_fail_closed(self, tmp_path):
        """A historical effective_until > canonical effective_from is overlap."""
        doc = _write_sitespec(
            tmp_path,
            site_id="overlap_after",
            legacy_ids=[],
            effective_from=CANONICAL_EFFECTIVE_FROM,
            historical_aliases=[
                {"value": "Old", "effective_until": "2026-07-15"},
            ],
        )
        with pytest.raises(JurisdictionResolutionError, match="overlap"):
            resolve_jurisdiction_at(doc, "2026-06-15")

    def test_historical_effective_until_on_canonical_date_not_overlap(self, tmp_path):
        """effective_until == day before canonical_from is fine, not overlap."""
        doc = _write_sitespec(
            tmp_path,
            site_id="clean_boundary",
            legacy_ids=[],
            effective_from="2026-07-01",
            historical_aliases=[
                {"value": "Old", "effective_until": "2026-06-30"},
            ],
        )
        result = resolve_jurisdiction_at(doc, "2026-06-30")
        assert result["resolution_kind"] == "historical_alias"
        assert result["name"] == "Old"

    def test_alias_order_reversal_does_not_change_outcome(self, tmp_path):
        """Reversing historical alias array order must not change the result.

        Uses a date (2026-06-20) where exactly one alias is a candidate:
        Old B ended 2026-05-15 (excluded), Old A ended 2026-06-30 (included).
        Ambiguity and order-independence are verified on the non-overlapping
        case; the ambiguous case is covered by
        ``test_reversed_ambiguous_still_fail_closed``.
        """
        doc = _write_sitespec(
            tmp_path,
            site_id="order_test",
            legacy_ids=[],
            effective_from="2026-08-01",
            historical_aliases=[
                {"value": "Old A", "effective_until": "2026-06-30"},
                {"value": "Old B", "effective_until": "2026-05-15"},
            ],
        )
        doc_reversed = copy.deepcopy(doc)
        doc_reversed["jurisdiction"]["historical_aliases"].reverse()

        result_a = resolve_jurisdiction_at(doc, "2026-06-20")
        result_b = resolve_jurisdiction_at(doc_reversed, "2026-06-20")
        assert result_a == result_b
        assert result_a["name"] == "Old A"
        assert result_a["resolution_kind"] == "historical_alias"

    def test_reversed_ambiguous_still_fail_closed(self, tmp_path):
        """Two candidates that are identical in coverage still fail ambiguous
        regardless of array order."""
        doc = _write_sitespec(
            tmp_path,
            site_id="ambiguous_rev",
            legacy_ids=[],
            effective_from="2026-07-01",
            historical_aliases=[
                {"value": "Old A", "effective_until": "2026-06-30"},
                {"value": "Old B", "effective_until": "2026-06-30"},
            ],
        )
        doc_reversed = copy.deepcopy(doc)
        doc_reversed["jurisdiction"]["historical_aliases"].reverse()
        with pytest.raises(JurisdictionResolutionError, match="ambiguous timeline"):
            resolve_jurisdiction_at(doc_reversed, "2026-06-15")

    def test_reversed_overlap_still_fail_closed(self, tmp_path):
        """Overlap is order-independent: reversing still fails."""
        doc = _write_sitespec(
            tmp_path,
            site_id="overlap_rev",
            legacy_ids=[],
            effective_from="2026-07-01",
            historical_aliases=[
                {"value": "Old A", "effective_until": "2026-07-05"},
                {"value": "Old B", "effective_until": "2026-06-30"},
            ],
        )
        doc_reversed = copy.deepcopy(doc)
        doc_reversed["jurisdiction"]["historical_aliases"].reverse()
        with pytest.raises(JurisdictionResolutionError, match="overlap"):
            resolve_jurisdiction_at(doc_reversed, "2026-06-15")

    def test_reversed_gap_still_fail_closed(self, tmp_path):
        """A gap is order-independent: reversing still fails."""
        doc = _write_sitespec(
            tmp_path,
            site_id="gap_rev",
            legacy_ids=[],
            effective_from="2026-07-01",
            historical_aliases=[
                {"value": "Old A", "effective_until": "2026-05-15"},
                {"value": "Old B", "effective_until": "2026-03-10"},
            ],
        )
        doc_reversed = copy.deepcopy(doc)
        doc_reversed["jurisdiction"]["historical_aliases"].reverse()
        with pytest.raises(JurisdictionResolutionError, match="unrepresented historical gap"):
            resolve_jurisdiction_at(doc_reversed, "2026-06-20")


# ---------------------------------------------------------------------------
# E. Mutation isolation
# ---------------------------------------------------------------------------

class TestMutationIsolation:
    """The resolver must not mutate the input SiteSpec object."""

    def test_input_spec_not_mutated_canonical(self):
        spec = _load_sitespec()
        snapshot = copy.deepcopy(spec)
        resolve_jurisdiction_at(spec, "2026-07-01")
        resolve_jurisdiction_at(spec, "2026-06-30")
        resolve_jurisdiction_at(spec, "2026-12-31")
        assert spec == snapshot

    def test_input_spec_not_mutated_historical(self):
        spec = _load_sitespec()
        snapshot = copy.deepcopy(spec)
        resolve_jurisdiction_at(spec, "2026-06-30")
        assert spec == snapshot

    def test_historical_alias_list_not_reordered(self):
        spec = _load_sitespec()
        original_order = [
            a["value"] for a in spec["jurisdiction"]["historical_aliases"]
        ]
        resolve_jurisdiction_at(spec, "2026-06-30")
        after_order = [
            a["value"] for a in spec["jurisdiction"]["historical_aliases"]
        ]
        assert original_order == after_order

    def test_deep_copied_spec_still_works(self):
        spec = copy.deepcopy(_load_sitespec())
        result = resolve_jurisdiction_at(spec, "2026-07-01")
        assert result["resolution_kind"] == "canonical"
        assert result["name"] == CANONICAL_NAME


# ---------------------------------------------------------------------------
# F. Genericity (pytest temp fixtures, no second real site)
# ---------------------------------------------------------------------------

class TestGenericity:
    """The resolver is generic: it works on any properly-formed SiteSpec
    without hardcoding Buk-gu specifics."""

    def test_generic_canonical_resolution(self, tmp_path):
        doc = _write_sitespec(
            tmp_path,
            site_id="generic_city",
            legacy_ids=["legacy_city"],
            canonical_name="Generic City",
            effective_from="2026-05-15",
            historical_aliases=[],
        )
        result = resolve_jurisdiction_at(doc, "2026-06-01")
        assert result["canonical_site_id"] == "generic_city"
        assert result["name"] == "Generic City"
        assert result["resolution_kind"] == "canonical"
        assert result["effective_from"] == "2026-05-15"

    def test_generic_historical_resolution(self, tmp_path):
        doc = _write_sitespec(
            tmp_path,
            site_id="generic_city",
            legacy_ids=["legacy_city"],
            canonical_name="New Generic City",
            effective_from="2026-05-15",
            historical_aliases=[
                {"value": "Old Generic City", "effective_until": "2026-05-14"},
            ],
        )
        result = resolve_jurisdiction_at(doc, "2026-05-10")
        assert result["canonical_site_id"] == "generic_city"
        assert result["name"] == "Old Generic City"
        assert result["resolution_kind"] == "historical_alias"
        assert result["effective_until"] == "2026-05-14"

    def test_generic_boundary_exact(self, tmp_path):
        doc = _write_sitespec(
            tmp_path,
            site_id="boundary_site",
            legacy_ids=[],
            canonical_name="New Name",
            effective_from="2026-05-15",
            historical_aliases=[
                {"value": "Old Name", "effective_until": "2026-05-14"},
            ],
        )
        result_before = resolve_jurisdiction_at(doc, "2026-05-14")
        result_at = resolve_jurisdiction_at(doc, "2026-05-15")
        assert result_before["name"] == "Old Name"
        assert result_before["resolution_kind"] == "historical_alias"
        assert result_at["name"] == "New Name"
        assert result_at["resolution_kind"] == "canonical"

    def test_generic_no_historical_aliases_then_pre_canonical_gaps(self, tmp_path):
        """With no historical aliases, any pre-canonical date is a gap."""
        doc = _write_sitespec(
            tmp_path,
            site_id="no_aliases",
            legacy_ids=[],
            canonical_name="Present",
            effective_from="2026-10-01",
            historical_aliases=[],
        )
        result = resolve_jurisdiction_at(doc, "2026-10-01")
        assert result["resolution_kind"] == "canonical"
        result_future = resolve_jurisdiction_at(doc, "2027-01-01")
        assert result_future["resolution_kind"] == "canonical"
        with pytest.raises(JurisdictionResolutionError, match="unrepresented historical gap"):
            resolve_jurisdiction_at(doc, "2026-09-15")

    def test_generic_second_site_through_real_resolver(self, tmp_path):
        """A second generic site on a temp resolver also works end-to-end."""
        _write_sitespec(
            tmp_path,
            site_id="generic_city",
            legacy_ids=["legacy_city"],
            canonical_name="Generic City",
            effective_from="2026-05-15",
            historical_aliases=[
                {"value": "Old Generic", "effective_until": "2026-05-14"},
            ],
        )
        resolver = SiteSpecResolver(tmp_path)
        spec_canonical = resolver.resolve("generic_city")
        spec_legacy = resolver.resolve("legacy_city")
        assert spec_canonical == spec_legacy
        result = resolve_jurisdiction_at(spec_legacy, "2026-05-10")
        assert result["name"] == "Old Generic"
        assert result["resolution_kind"] == "historical_alias"
        result2 = resolve_jurisdiction_at(spec_canonical, "2026-06-01")
        assert result2["name"] == "Generic City"
        assert result2["resolution_kind"] == "canonical"

    def test_generic_multiple_historical_aliases_selects_correct(self, tmp_path):
        """With multiple non-overlapping-coverage aliases, only the relevant one
        is selected for a given date. Dates where two aliases both cover the
        point are ambiguous and fail-closed (see
        ``test_multi_alias_overlapping_coverage_ambiguous``)."""
        doc = _write_sitespec(
            tmp_path,
            site_id="multi_hist",
            legacy_ids=[],
            canonical_name="Current Multi",
            effective_from="2026-07-01",
            historical_aliases=[
                {"value": "Early Era", "effective_until": "2026-02-28"},
                {"value": "Mid Era", "effective_until": "2026-06-30"},
            ],
        )
        # 2026-06-20: only Mid Era matches (Early Era ended 2026-02-28).
        result_mid = resolve_jurisdiction_at(doc, "2026-06-20")
        assert result_mid["name"] == "Mid Era"
        assert result_mid["resolution_kind"] == "historical_alias"
        assert result_mid["effective_until"] == "2026-06-30"

        # 2026-06-30: only Mid Era matches (boundary date).
        result_boundary = resolve_jurisdiction_at(doc, "2026-06-30")
        assert result_boundary["name"] == "Mid Era"
        assert result_boundary["resolution_kind"] == "historical_alias"

        # 2026-07-01: canonical.
        result_canonical = resolve_jurisdiction_at(doc, "2026-07-01")
        assert result_canonical["name"] == "Current Multi"
        assert result_canonical["resolution_kind"] == "canonical"

        # 2026-02-15: both Early (ended 2026-02-28) and Mid cover this date
        # → ambiguous → fail.
        with pytest.raises(JurisdictionResolutionError, match="ambiguous"):
            resolve_jurisdiction_at(doc, "2026-02-15")
