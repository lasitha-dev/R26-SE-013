"""FMD-03C: FMD data-pipeline tests — disease-identity dedup gate, FMD
status/species/eligibility policy, canonical-id determinism, and FMD/LSD
output-path isolation.

Uses small synthetic fixtures (not the real 9,526-row corpus — that is
exercised separately, out-of-band, by running
`build_fmd_canonical.py` against `local_data/pistes_raw/fmd/` and comparing
run-to-run hashes; see FMD_DATA_AUDIT.md "Reproducibility"). Mirrors
`test_dedup.py`'s fixture style.
"""

from __future__ import annotations

from pathlib import Path

from datetime import date

from components.geospatial_tracking.data_processing.build_fmd_canonical import (
    FMD_CANONICAL_EXTRA_COLUMNS,
    build_conservative_and_candidate_rows,
    classify_event_date,
    compute_date_validation_stats,
    load_fmd_normalized_records,
)
from components.geospatial_tracking.data_processing.dedup import build_duplicate_groups, match_pair
from components.geospatial_tracking.data_processing.disease import disease_matches, normalize_disease
from components.geospatial_tracking.data_processing.fmd_eligibility import (
    DUPLICATE_UNRESOLVED,
    ELIGIBLE,
    EVENT_IDENTITY_UNRESOLVED,
    INVALID_COORDINATE,
    MISSING_EVENT_DATE,
    STATUS_NOT_CONFIRMED,
    evaluate_fmd_eligibility,
)
from components.geospatial_tracking.data_processing.fmd_identity import fmd_canonical_event_id
from components.geospatial_tracking.data_processing.fmd_species import (
    build_species_normalization_audit,
    normalize_species_category,
)
from components.geospatial_tracking.data_processing.fmd_status import (
    CONFIRMED,
    DENIED,
    SUSPECTED,
    UNKNOWN,
    classify_diagnosis_status,
    is_primary_positive_corpus_eligible,
)
from components.geospatial_tracking.data_processing.normalize import (
    assign_spatial_independence,
    normalize_raw_records,
)
from components.geospatial_tracking.schemas import DedupStatus, RawOutbreakRecord, SourceSystem


def _fmd(**overrides):
    fields = dict(
        source_file="fmd_events.csv",
        source_system=SourceSystem.FAO_EMPRESI_BIGQUERY_CSV.value,
        country="Sri Lanka",
        disease="Foot and mouth disease",
        event_id="EMP-1",
        onset_date="2024-03-01",
        report_date="2024-03-05",
        locality="Kopay",
        latitude=9.71517,
        longitude=80.066849,
        species="Domestic - Cattle",
        diagnostic_result="Confirmed",
    )
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def _lsd(**overrides):
    fields = dict(
        source_file="lsd_events.csv",
        source_system=SourceSystem.FAO_EMPRESI_CSV.value,
        country="Sri Lanka",
        disease="Lumpy skin disease",
        event_id="LSD-1",
        onset_date="2024-03-01",
        locality="Kopay",
        latitude=9.71517,
        longitude=80.066849,
        species="Domestic - Cattle",
    )
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def _normalize(raw_records):
    normalized = normalize_raw_records(raw_records)
    assign_spatial_independence(normalized)
    return normalized


# ---- 1. disease alias normalization -----------------------------------


class TestDiseaseNormalization:
    def test_fmd_aliases_normalize_to_the_same_token(self):
        aliases = ["Foot and mouth disease", "Foot-and-Mouth Disease", "FMD", "fmd", "FOOT AND MOUTH DISEASE"]
        tokens = {normalize_disease(a) for a in aliases}
        assert tokens == {"foot and mouth disease"}

    def test_fmd_and_lsd_never_match_as_the_same_disease(self):
        assert disease_matches("FMD", "Lumpy skin disease") is False
        assert disease_matches("Foot and mouth disease", "LSD") is False


# ---- 2. LSD/FMD cross-disease dedup gate --------------------------------


class TestCrossDiseaseGate:
    def test_identical_everything_except_disease_never_matches(self):
        # Same country/locality/date/coordinates/species — only disease differs.
        norm = _normalize([_fmd(), _lsd()])
        assert match_pair(norm[0], norm[1]) is None

    def test_cross_disease_gate_blocks_even_a_trusted_identifier_match(self):
        # Same source_system + same outbreak_id would normally be a Level-1
        # HIGH auto-match — must still be blocked by disease disagreement.
        norm = _normalize(
            [
                _fmd(outbreak_id="OB_1", source_file="a.csv"),
                _lsd(
                    outbreak_id="OB_1",
                    source_file="b.csv",
                    source_system=SourceSystem.FAO_EMPRESI_BIGQUERY_CSV.value,
                ),
            ]
        )
        assert match_pair(norm[0], norm[1]) is None


# ---- 3. distinct global_id values never merge on proximity alone -------


class TestEventIdentityNeverMergedOnProximityAlone:
    def test_two_distinct_global_ids_same_everything_still_get_evaluated_not_force_identical(self):
        """Two EMPRES-i rows with different global_id, identical country/date/
        coordinates/species DO produce a HIGH-confidence spatiotemporal
        match (this is the documented, legitimate LEVEL_2_FULL_EVIDENCE
        path — real repeated-coordinate outbreak reporting) — but they are
        never assumed identical merely because IDs are absent from the
        comparison. Distinctness is preserved unless the evidence bar is
        met; this test pins down that global_id equality/inequality itself
        is never consulted by Level 2/3 matching (only Level 1 uses IDs,
        and only within the same source_system + same identifier value)."""
        a = _fmd(event_id="EMP-100")
        b = _fmd(event_id="EMP-200")
        norm = _normalize([a, b])
        assert norm[0].event_id != norm[1].event_id
        m = match_pair(norm[0], norm[1])
        # Full spatiotemporal + locality + species agreement legitimately
        # produces a HIGH candidate group — but it is a REPORTED, AUDITABLE
        # candidate (see fmd_dedup_audit.csv), never a silent identity
        # collapse: the two distinct global_ids remain fully visible in
        # duplicate_group_id/member_record_ids.
        assert m is not None
        groups = build_duplicate_groups(norm)
        assert len(groups) == 1
        assert set(groups[0].member_record_ids) == {norm[0].source_record_id, norm[1].source_record_id}

    def test_distinct_global_ids_diverging_on_date_never_merge(self):
        a = _fmd(event_id="EMP-100", onset_date="2024-03-01")
        b = _fmd(event_id="EMP-200", onset_date="2024-04-01")
        norm = _normalize([a, b])
        assert match_pair(norm[0], norm[1]) is None

    def test_coordinate_equality_alone_without_locality_or_species_agreement_is_capped_at_low_never_merged(self):
        a = _fmd(event_id="EMP-1", locality="Village A", species="Domestic - Cattle")
        b = _fmd(event_id="EMP-2", locality="Village B far away name", species="Domestic - Swine")
        norm = _normalize([a, b])
        # Same coordinates, same date, same country, but neither locality
        # nor species agree: this is still reported as a LOW-confidence
        # candidate (coordinate equality alone is evidence of SOMETHING
        # worth a human's attention) — but "coordinate equality alone is
        # never a duplicate decision" means LOW, and LOW groups are never
        # auto-merged (see build_duplicate_groups: only HIGH/MEDIUM merge).
        m = match_pair(norm[0], norm[1])
        assert m is not None
        assert m.tier == "LOW"
        groups = build_duplicate_groups(norm)
        assert len(groups) == 1
        assert groups[0].merged is False


# ---- 4. cross-source consolidation requires strong evidence -------------


class TestCrossSourceConsolidation:
    def test_cross_source_high_confidence_match_requires_full_evidence(self):
        fao_ui = _fmd(
            source_system=SourceSystem.FAO_EMPRESI_CSV.value,
            source_file="latest_reported_events.csv",
            event_id="UNFAO-LEG-1",
        )
        fao_bq = _fmd(
            source_system=SourceSystem.FAO_EMPRESI_BIGQUERY_CSV.value,
            source_file="fmd_events.csv",
            event_id="EMP-1",
        )
        norm = _normalize([fao_ui, fao_bq])
        m = match_pair(norm[0], norm[1])
        assert m is not None
        assert m.tier == "HIGH"

    def test_cross_source_untrusted_identifier_lookalike_is_never_compared_directly(self):
        # Two different source_systems with numerically-similar-looking IDs
        # must never be treated as the same namespace (Level 1 requires
        # a.source_system == b.source_system).
        a = _fmd(source_system=SourceSystem.FAO_EMPRESI_CSV.value, outbreak_id="OB_1", source_file="x.csv")
        b = _fmd(
            source_system=SourceSystem.FAO_EMPRESI_BIGQUERY_CSV.value,
            outbreak_id="OB_1",
            source_file="y.csv",
            locality="Somewhere Else Entirely",
            latitude=1.0,
            longitude=1.0,
        )
        norm = _normalize([a, b])
        m = match_pair(norm[0], norm[1])
        # No shared country/date/spatial evidence -> no match at all, even
        # though outbreak_id strings are identical across sources.
        assert m is None


# ---- 5. coordinate equality alone is never sufficient -------------------


class TestCoordinateAloneNeverSufficient:
    def test_same_coordinates_different_country_never_matches(self):
        a = _fmd(country="Sri Lanka")
        b = _fmd(country="India")
        norm = _normalize([a, b])
        assert match_pair(norm[0], norm[1]) is None

    def test_same_coordinates_no_date_never_matches(self):
        a = _fmd(onset_date="2024-03-01")
        b = _fmd(onset_date=None)
        norm = _normalize([a, b])
        assert match_pair(norm[0], norm[1]) is None


# ---- 6/7/8/9/10. status policy -------------------------------------------


class TestStatusPolicy:
    def test_confirmed_classifies_and_is_positive_corpus_eligible(self):
        assert classify_diagnosis_status("Confirmed") == CONFIRMED
        assert is_primary_positive_corpus_eligible("Confirmed") is True

    def test_suspected_retained_but_not_positive_corpus_eligible(self):
        assert classify_diagnosis_status("Suspected") == SUSPECTED
        assert is_primary_positive_corpus_eligible("Suspected") is False

    def test_denied_retained_but_not_positive_corpus_eligible(self):
        assert classify_diagnosis_status("Denied") == DENIED
        assert is_primary_positive_corpus_eligible("Denied") is False

    def test_denied_is_not_classified_as_a_generic_ml_negative_label(self):
        # DENIED must classify to its own explicit status token, never to a
        # generic binary "negative"/"0" label — no such label exists in the
        # module's public surface at all.
        assert classify_diagnosis_status("Denied") == "DENIED"
        import components.geospatial_tracking.data_processing.fmd_status as fmd_status_module

        assert not hasattr(fmd_status_module, "NEGATIVE")
        assert "NEGATIVE" not in (fmd_status_module.__doc__ or "")

    def test_unknown_status_string_never_silently_becomes_confirmed(self):
        assert classify_diagnosis_status("") == UNKNOWN
        assert classify_diagnosis_status(None) == UNKNOWN
        assert classify_diagnosis_status("Pending") == UNKNOWN
        assert is_primary_positive_corpus_eligible("Pending") is False

    def test_status_classification_is_case_and_whitespace_tolerant(self):
        assert classify_diagnosis_status("  confirmed  ") == CONFIRMED
        assert classify_diagnosis_status("CONFIRMED") == CONFIRMED


# ---- eligibility reason codes -------------------------------------------


class TestEligibility:
    def _record(self, **overrides):
        return _normalize([_fmd(**overrides)])[0]

    def test_confirmed_with_all_fields_valid_is_eligible(self):
        r = self._record()
        result = evaluate_fmd_eligibility(
            r, raw_diagnosis_status="Confirmed", dedup_status=DedupStatus.SINGLETON.value
        )
        assert result.modelling_eligible is True
        assert result.eligibility_reason == ELIGIBLE

    def test_suspected_excluded_with_status_not_confirmed_reason(self):
        r = self._record(diagnostic_result="Suspected")
        result = evaluate_fmd_eligibility(
            r, raw_diagnosis_status="Suspected", dedup_status=DedupStatus.SINGLETON.value
        )
        assert result.modelling_eligible is False
        assert result.eligibility_reason == STATUS_NOT_CONFIRMED

    def test_missing_event_id_is_event_identity_unresolved(self):
        r = self._record(event_id=None)
        result = evaluate_fmd_eligibility(
            r, raw_diagnosis_status="Confirmed", dedup_status=DedupStatus.SINGLETON.value
        )
        assert result.eligibility_reason == EVENT_IDENTITY_UNRESOLVED

    def test_missing_event_date_is_missing_event_date(self):
        r = self._record(onset_date=None)
        result = evaluate_fmd_eligibility(
            r, raw_diagnosis_status="Confirmed", dedup_status=DedupStatus.SINGLETON.value
        )
        assert result.eligibility_reason == MISSING_EVENT_DATE

    def test_out_of_range_coordinate_is_invalid_coordinate(self):
        r = self._record(latitude=200.0)
        result = evaluate_fmd_eligibility(
            r, raw_diagnosis_status="Confirmed", dedup_status=DedupStatus.SINGLETON.value
        )
        assert result.eligibility_reason == INVALID_COORDINATE

    def test_unresolved_medium_duplicate_is_duplicate_unresolved(self):
        r = self._record()
        result = evaluate_fmd_eligibility(
            r, raw_diagnosis_status="Confirmed", dedup_status=DedupStatus.REVIEW_MEDIUM.value
        )
        assert result.eligibility_reason == DUPLICATE_UNRESOLVED

    def test_unknown_coordinate_precision_alone_does_not_block_eligibility(self):
        # gps_quality is UNKNOWN for every FMD record from this source — a
        # VALID coordinate with unknown precision must still be eligible.
        r = self._record()
        assert r.gps_quality == "UNKNOWN"
        result = evaluate_fmd_eligibility(
            r, raw_diagnosis_status="Confirmed", dedup_status=DedupStatus.SINGLETON.value
        )
        assert result.modelling_eligible is True


# ---- serotype: never inferred --------------------------------------------


class TestNoSerotypeInference:
    def test_species_module_never_produces_a_serotype_field(self):
        result = normalize_species_category("Domestic - Cattle")
        assert not hasattr(result, "serotype")

    def test_event_metadata_serotype_is_always_unknown_and_never_inferred_from_locality(self):
        from components.geospatial_tracking.data_processing.build_fmd_canonical import build_event_metadata_rows

        # A locality string containing an apparent serotype-looking token
        # ("SAT1") must never cause serotype_known/serotype_value to be
        # populated — no such inference path exists.
        raw = _fmd(locality="SAT1 Farm Road")
        norm = _normalize([raw])
        rows = build_event_metadata_rows(norm, {norm[0].source_record_id: raw})
        assert rows[0]["serotype_known"] is False
        assert rows[0]["serotype_value"] == ""


# ---- species normalization -----------------------------------------------


class TestSpeciesNormalization:
    def test_multi_species_token_set_is_preserved_not_collapsed_to_first(self):
        result = normalize_species_category("Domestic - Cattle | Domestic - Sheep")
        assert result.species_tokens_normalized == "cattle+sheep"
        assert result.species_normalized_category == "mixed"

    def test_sheep_goat_combination_aggregates_to_small_ruminant_without_losing_tokens(self):
        result = normalize_species_category("Domestic - Goats | Domestic - Sheep")
        assert result.species_normalized_category == "small_ruminant"
        assert result.species_tokens_normalized == "goat+sheep"

    def test_normalization_is_deterministic_regardless_of_token_order(self):
        a = normalize_species_category("Domestic - Cattle | Domestic - Sheep")
        b = normalize_species_category("Domestic - Sheep | Domestic - Cattle")
        assert a.species_normalized_category == b.species_normalized_category
        assert a.species_tokens_normalized == b.species_tokens_normalized

    def test_host_context_is_tracked_separately_from_species_category(self):
        result = normalize_species_category("Wild - Buffaloe")
        assert result.species_normalized_category == "buffalo"
        assert result.wild_context_present is True
        assert result.domestic_context_present is False

    def test_species_audit_row_counts_sum_to_input_row_count(self):
        values = [
            "Domestic - Cattle",
            "Domestic - Cattle",
            "Domestic - Sheep",
            "Domestic - Goats | Domestic - Sheep",
            None,
        ]
        rows = build_species_normalization_audit(values)
        assert sum(r["row_count"] for r in rows) == len(values)


# ---- canonical ID determinism ---------------------------------------------


class TestCanonicalIdDeterminism:
    def test_same_global_id_always_produces_the_same_canonical_id(self):
        assert fmd_canonical_event_id("UNFAO-LEG-1") == fmd_canonical_event_id("UNFAO-LEG-1")

    def test_canonical_id_is_namespaced_by_source_not_a_row_position(self):
        cid = fmd_canonical_event_id("UNFAO-LEG-1")
        assert cid == "FAO_EMPRESI_BIGQUERY_CSV:UNFAO-LEG-1"

    def test_missing_global_id_produces_no_canonical_id(self):
        assert fmd_canonical_event_id(None) is None
        assert fmd_canonical_event_id("") is None


# ---- FMD-03D: event-date validation (missing vs malformed vs impossible) --


class TestEventDateValidation:
    _REF_TODAY = date(2026, 8, 23)

    def test_missing_date_classifies_as_missing(self):
        assert classify_event_date(None, today=self._REF_TODAY) == "MISSING"
        assert classify_event_date("", today=self._REF_TODAY) == "MISSING"
        assert classify_event_date("   ", today=self._REF_TODAY) == "MISSING"

    def test_unparseable_string_classifies_as_malformed_not_missing(self):
        # A non-empty, non-blank string that doesn't match either accepted
        # date format (%Y-%m-%d / %Y/%m/%d) must be distinguished from an
        # honestly-absent date, per FMD-03D Step 6 — never silently folded
        # into the same "missing" bucket.
        assert classify_event_date("not-a-date", today=self._REF_TODAY) == "MALFORMED"
        assert classify_event_date("2024-13-45", today=self._REF_TODAY) == "MALFORMED"
        assert classify_event_date("08/23/2026", today=self._REF_TODAY) == "MALFORMED"

    def test_future_date_beyond_today_is_impossible_future(self):
        assert classify_event_date("2099-01-01", today=self._REF_TODAY) == "IMPOSSIBLE_FUTURE"

    def test_date_before_sanity_floor_is_impossible_too_old(self):
        assert classify_event_date("1850-01-01", today=self._REF_TODAY) == "IMPOSSIBLE_TOO_OLD"

    def test_ordinary_valid_date_classifies_as_valid(self):
        assert classify_event_date("2024-03-01", today=self._REF_TODAY) == "VALID"
        assert classify_event_date("2024/03/01", today=self._REF_TODAY) == "VALID"

    def test_today_itself_is_valid_not_future(self):
        assert classify_event_date("2026-08-23", today=self._REF_TODAY) == "VALID"

    def test_malformed_date_still_excluded_via_missing_event_date_eligibility_reason(self):
        # classify_event_date is audit-only — it must never change
        # eligibility behavior. A malformed onset_date still yields
        # MISSING_EVENT_DATE from evaluate_fmd_eligibility (dedup.parse_date
        # returns None for it too), same as a truly absent date.
        r = _normalize([_fmd(onset_date="not-a-date")])[0]
        result = evaluate_fmd_eligibility(
            r, raw_diagnosis_status="Confirmed", dedup_status=DedupStatus.SINGLETON.value
        )
        assert result.eligibility_reason == MISSING_EVENT_DATE

    def test_compute_date_validation_stats_counts_every_record_exactly_once(self):
        records = _normalize(
            [
                _fmd(event_id="EMP-1", onset_date="2024-03-01"),
                _fmd(event_id="EMP-2", onset_date=None),
                _fmd(event_id="EMP-3", onset_date="not-a-date"),
            ]
        )
        stats = compute_date_validation_stats(records)
        assert sum(stats.values()) == len(records)
        assert stats["valid"] == 1
        assert stats["missing"] == 1
        assert stats["malformed"] == 1


# ---- FMD/LSD output-path isolation + provenance survival ------------------


class TestOutputIsolationAndProvenance:
    def test_fmd_raw_loader_never_reads_the_sibling_lsd_raw_directory(self, tmp_path: Path):
        fmd_dir = tmp_path / "pistes_raw" / "fmd"
        fmd_dir.mkdir(parents=True)
        lsd_dir = tmp_path / "pistes_raw"

        # An LSD-shaped CSV placed one directory UP from fmd_dir (mirroring
        # the real repo layout: local_data/pistes_raw/*.csv is LSD,
        # local_data/pistes_raw/fmd/*.csv is FMD).
        (lsd_dir / "Latest Reported Events (3).csv").write_text(
            "Event ID,Disease,Serotype,latitude,longitude,Locality,Country,Region,"
            "observation date,report date,Species,Diagnosis Source,Humans Affected,"
            "Human Deaths,Diagnosis Status\n"
            "UNFAO-LEG-9,Lumpy skin disease,,9.0,80.0,X,Sri Lanka,Asia,2024-01-01,,"
            "Domestic - Cattle,,,,Confirmed\n",
            encoding="utf-8",
        )
        (fmd_dir / "fmd_events.csv").write_text(
            "global_id,lat,lon,locality,region,location,observation_date,report_date,"
            "display_date,species_overview_list,humans_affected,humans_deaths,"
            "diagnosis_source,diagnosis_status,animal_type_list,disease,country\n"
            "EMP-1,9.0,80.0,X,Asia,X,2024-01-01,,,Domestic - Cattle,,,,Confirmed,,"
            "Foot and mouth disease,Sri Lanka\n",
            encoding="utf-8",
        )

        normalized, csv_paths = load_fmd_normalized_records(fmd_dir)
        assert len(normalized) == 1
        assert normalized[0].event_id == "EMP-1"
        assert [p.name for p in csv_paths] == ["fmd_events.csv"]

    def test_fmd_canonical_columns_include_no_lsd_output_path_reference(self):
        assert "duplicate_group_id" in FMD_CANONICAL_EXTRA_COLUMNS
        # sanity: the FMD extra-columns list is its own independent constant,
        # not shared/mutated with build_canonical.py's CANONICAL_EXTRA_COLUMNS.
        from components.geospatial_tracking.data_processing.build_canonical import CANONICAL_EXTRA_COLUMNS

        assert FMD_CANONICAL_EXTRA_COLUMNS is not CANONICAL_EXTRA_COLUMNS

    def test_source_provenance_fields_survive_into_conservative_rows(self):
        raw = [_fmd(event_id="EMP-1")]
        norm = _normalize(raw)
        conservative_rows, candidate_rows, groups = build_conservative_and_candidate_rows(norm)
        assert len(conservative_rows) == 1
        row = conservative_rows[0]
        assert row["source_system"] == SourceSystem.FAO_EMPRESI_BIGQUERY_CSV.value
        assert row["source_file"] == "fmd_events.csv"
        assert row["event_id"] == "EMP-1"
        assert row["fmd_canonical_event_id"] == "FAO_EMPRESI_BIGQUERY_CSV:EMP-1"


# ---- FMD-03D: same-source authoritative-event-identity guard --------------
#
# FMD-03D superseded FMD-03C's assumption that a HIGH-confidence
# spatiotemporal match between two SAME-SOURCE, DIFFERENT-`global_id`
# records should auto-merge into one canonical row. That assumption was
# demonstrated wrong against the real corpus: `outbreak_id` (Level 1's
# trusted identifier) is never populated by the FMD BigQuery adapter, so
# every one of the real export's 264 HIGH-confidence groups was a Level-2
# fuzzy spatiotemporal match, not a genuine same-event alias — auto-merging
# them collapsed 344 distinct, authoritatively-identified EMPRES-i events
# into their siblings with zero explicit alias evidence. The single
# original test encoding "same-source HIGH match -> one merged row" below
# has been REPLACED (not silently deleted) by
# `TestSameSourceAuthoritativeIdentityGuard`, which pins down the corrected
# rule: distinct non-empty `global_id` values from the same source_system
# are preserved as distinct canonical events regardless of confidence tier.
# `TestStatusAwareCanonicalSelectionStillAppliesToGenuineMerges` proves the
# FMD-03C canonical-selection correction (§ prefer a CONFIRMED member over a
# more "complete" non-CONFIRMED sibling) is still exercised on the merge
# paths that remain genuine under FMD-03D (same authoritative identifier,
# or cross-source with strong evidence).


class TestSameSourceAuthoritativeIdentityGuard:
    def test_distinct_global_ids_same_source_never_merge_regardless_of_status(self):
        # Same country/locality/date/coordinates/species -> HIGH match by
        # dedup.py's generic (unmodified, shared) evidence rules — but same
        # source_system + distinct non-empty global_id must NEVER collapse
        # into one canonical row under the FMD-03D identity guard.
        confirmed = _fmd(event_id="EMP-1", diagnostic_result="Confirmed")
        suspected = _fmd(event_id="EMP-2", diagnostic_result="Suspected")
        norm = _normalize([confirmed, suspected])
        conservative_rows, candidate_rows, groups = build_conservative_and_candidate_rows(norm)

        assert len(conservative_rows) == 2
        assert {r["dedup_status"] for r in conservative_rows} == {"DISTINCT_AUTHORITATIVE_EVENT"}
        assert all(r["dedup_status"] != DedupStatus.AUTO_MERGED_HIGH.value for r in conservative_rows)

        by_event_id = {r["event_id"]: r for r in conservative_rows}
        assert by_event_id["EMP-1"]["diagnosis_status"] == CONFIRMED
        assert by_event_id["EMP-1"]["modelling_eligible"] is True
        assert by_event_id["EMP-1"]["eligibility_reason"] == ELIGIBLE
        assert by_event_id["EMP-2"]["diagnosis_status"] == SUSPECTED
        assert by_event_id["EMP-2"]["modelling_eligible"] is False
        assert by_event_id["EMP-2"]["eligibility_reason"] == STATUS_NOT_CONFIRMED

    def test_possible_related_event_relationship_is_recorded_not_a_merge(self):
        a = _fmd(event_id="EMP-1")
        b = _fmd(event_id="EMP-2")
        norm = _normalize([a, b])
        conservative_rows, candidate_rows, groups = build_conservative_and_candidate_rows(norm)
        assert len(groups) == 1
        group_id = groups[0].duplicate_group_id
        for row in conservative_rows:
            assert row["duplicate_group_id"] == ""  # never reported as a literal merge group
            assert row["member_record_ids"] == row["source_record_id"]  # only itself
            assert row["member_count"] == 1
            assert row["possible_related_event_group_id"] == group_id
            assert row["source_record_id"] in row["possible_related_event_member_ids"]

    def test_two_confirmed_same_source_distinct_ids_are_both_individually_eligible(self):
        a = _fmd(event_id="EMP-1")
        b = _fmd(event_id="EMP-2")
        norm = _normalize([a, b])
        conservative_rows, candidate_rows, groups = build_conservative_and_candidate_rows(norm)
        assert len(conservative_rows) == 2
        assert all(r["modelling_eligible"] is True for r in conservative_rows)
        assert all(r["eligibility_reason"] == ELIGIBLE for r in conservative_rows)
        # never DUPLICATE_UNRESOLVED just because a distinct-ID sibling is nearby
        assert all(r["dedup_status"] != "DUPLICATE_UNRESOLVED" for r in conservative_rows)

    def test_coordinate_and_date_equality_alone_between_distinct_ids_never_merges(self):
        a = _fmd(event_id="EMP-1", locality="Village A", species="Domestic - Cattle")
        b = _fmd(event_id="EMP-2", locality="Village B far away name", species="Domestic - Swine")
        norm = _normalize([a, b])
        conservative_rows, candidate_rows, groups = build_conservative_and_candidate_rows(norm)
        assert len(conservative_rows) == 2
        assert {r["event_id"] for r in conservative_rows} == {"EMP-1", "EMP-2"}


class TestStatusAwareCanonicalSelectionStillAppliesToGenuineMerges:
    def test_confirmed_sibling_preferred_over_more_complete_suspected_sibling_on_trusted_identifier_merge(self):
        # Genuine Case A: SAME source_system + SAME authoritative
        # outbreak_id (Level 1 trusted-identifier match) -> a real merge,
        # not blocked by the FMD-03D identity guard (only fires for
        # DIFFERENT ids). The SUSPECTED member is deliberately given more
        # populated fields so dedup.py's generic, status-agnostic
        # `select_canonical` would otherwise prefer it.
        confirmed = _fmd(event_id="EMP-1", outbreak_id="OB_SHARED", diagnostic_result="Confirmed", source_file="a.csv")
        suspected = _fmd(
            event_id="EMP-1",
            outbreak_id="OB_SHARED",
            diagnostic_result="Suspected",
            source_file="b.csv",
            admin1="ExtraField",
            admin2="ExtraField2",
            source_notes="extra completeness",
        )
        norm = _normalize([confirmed, suspected])
        conservative_rows, candidate_rows, groups = build_conservative_and_candidate_rows(norm)
        merged = [r for r in conservative_rows if r["dedup_status"] == DedupStatus.AUTO_MERGED_HIGH.value]
        assert len(merged) == 1
        assert merged[0]["diagnosis_status"] == CONFIRMED
        assert merged[0]["modelling_eligible"] is True

    def test_confirmed_sibling_preferred_over_more_complete_suspected_sibling_cross_source(self):
        # Case D: cross-source HIGH-confidence spatiotemporal match — the
        # existing, unmodified LSD Checkpoint-2.5 policy still applies (not
        # gated by the FMD-03D same-source identity guard, since the two
        # records are NOT from the same source_system).
        confirmed = _fmd(
            event_id="EMP-1",
            diagnostic_result="Confirmed",
            source_system=SourceSystem.FAO_EMPRESI_CSV.value,
            source_file="a.csv",
        )
        suspected = _fmd(
            event_id="EMP-2",
            diagnostic_result="Suspected",
            source_system=SourceSystem.FAO_EMPRESI_BIGQUERY_CSV.value,
            source_file="b.csv",
            admin1="ExtraField",
            admin2="ExtraField2",
            source_notes="extra completeness",
        )
        norm = _normalize([confirmed, suspected])
        conservative_rows, candidate_rows, groups = build_conservative_and_candidate_rows(norm)
        merged = [r for r in conservative_rows if r["dedup_status"] == DedupStatus.AUTO_MERGED_HIGH.value]
        assert len(merged) == 1
        assert merged[0]["diagnosis_status"] == CONFIRMED
        assert merged[0]["modelling_eligible"] is True
