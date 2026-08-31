from components.geospatial_tracking.data_processing.dedup import (
    build_duplicate_groups,
    locality_matches,
    locality_matches_strict,
    match_pair,
    select_canonical,
)
from components.geospatial_tracking.data_processing.normalize import (
    assign_spatial_independence,
    normalize_raw_records,
)
from components.geospatial_tracking.schemas import DedupConfidence, GpsQuality, RawOutbreakRecord, SourceSystem


def _csv(**overrides):
    fields = dict(
        source_file="events.csv",
        source_system=SourceSystem.FAO_EMPRESI_CSV.value,
        country="Sri Lanka",
        event_id="UNFAO-LEG-1",
        onset_date="2020-09-07",
        report_date="2021-01-19",
        locality="Kopay",
        latitude=9.71517,
        longitude=80.066849,
        species="Domestic - Cattle",
    )
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def _wahis(**overrides):
    fields = dict(
        source_file="Event_3473.pdf",
        source_system=SourceSystem.WAHIS_PDF.value,
        country="Sri Lanka",
        outbreak_id="OB_80063",
        outbreak_start_date="2020/09/07",
        report_date="2023/07/28",
        locality="Kopay",
        latitude=9.7151701,
        longitude=80.0668497,
        gps_quality=GpsQuality.EXACT.value,
        species="cattle (domestic)",
    )
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def _normalize(raw_records):
    normalized = normalize_raw_records(raw_records)
    assign_spatial_independence(normalized)
    return normalized


class TestCrossSourceMatching:
    def test_high_confidence_cross_source_match(self):
        # Event_3473-style: CSV row and WAHIS outbreak, same locality/date/
        # species, essentially identical coordinates.
        norm = _normalize([_csv(), _wahis()])
        m = match_pair(norm[0], norm[1])
        assert m is not None
        assert m.tier == DedupConfidence.HIGH.value

    def test_typo_tolerant_locality_still_matches(self):
        # WAHIS "Vavuniya" vs CSV "Vavuniy" (source typo) — small edit
        # distance, both EXACT gps, still HIGH.
        norm = _normalize(
            [
                _csv(locality="Vavuniy", onset_date="2020-10-28", latitude=9.0621351, longitude=80.6608048),
                _wahis(
                    outbreak_id="OB_80095",
                    locality="Vavuniya",
                    outbreak_start_date="2020/10/28",
                    latitude=9.0621351,
                    longitude=80.6608048,
                ),
            ]
        )
        m = match_pair(norm[0], norm[1])
        assert m is not None
        assert m.tier == DedupConfidence.HIGH.value

    def test_three_way_group_merges_two_csv_rows_and_one_wahis_outbreak(self):
        # The real Kopay pattern from Checkpoint 1: two CSV rows (different
        # coordinate precision, same Event ID namespace) + one WAHIS
        # outbreak, all describing one real-world outbreak.
        norm = _normalize(
            [
                _csv(event_id="UNFAO-LEG-286588", latitude=9.71517, longitude=80.066849),
                _csv(event_id="UNFAO-LEG-286458", latitude=9.7151701, longitude=80.0668497),
                _wahis(),
            ]
        )
        groups = build_duplicate_groups(norm)
        assert len(groups) == 1
        g = groups[0]
        assert g.dedup_confidence == DedupConfidence.HIGH.value
        assert g.merged is True
        assert len(g.member_record_ids) == 3


class TestNonDuplicateProtection:
    def test_same_coordinates_but_different_dates_do_not_match(self):
        # Never merge solely because coordinates are equal — a large date
        # gap must block the match even with identical coordinates.
        norm = _normalize(
            [
                _csv(onset_date="2020-01-01"),
                _wahis(outbreak_start_date="2020/08/15"),
            ]
        )
        m = match_pair(norm[0], norm[1])
        assert m is None

    def test_different_country_never_matches(self):
        norm = _normalize(
            [
                _csv(country="Thailand", locality="Sameville", latitude=9.0, longitude=80.0),
                _wahis(country="Sri Lanka", locality="Sameville", latitude=9.0, longitude=80.0),
            ]
        )
        m = match_pair(norm[0], norm[1])
        assert m is None

    def test_approximate_coordinate_protection(self):
        # WAHIS's documented Event_5868 case: three distinct outbreak IDs,
        # different localities, sharing one APPROXIMATE coordinate. Must
        # never auto-merge, even though species and country agree and
        # dates are close.
        raw = [
            _wahis(
                outbreak_id="OB_139551",
                locality="Village A",
                outbreak_start_date="2024/03/01",
                latitude=18.689547,
                longitude=98.994437,
                gps_quality=GpsQuality.APPROXIMATE.value,
                approximate_location=True,
            ),
            _wahis(
                outbreak_id="OB_139549",
                locality="Village B",
                outbreak_start_date="2024/03/02",
                latitude=18.689547,
                longitude=98.994437,
                gps_quality=GpsQuality.APPROXIMATE.value,
                approximate_location=True,
            ),
            _wahis(
                outbreak_id="OB_139550",
                locality="Village C",
                outbreak_start_date="2024/03/03",
                latitude=18.689547,
                longitude=98.994437,
                gps_quality=GpsQuality.APPROXIMATE.value,
                approximate_location=True,
            ),
        ]
        norm = _normalize(raw)
        groups = build_duplicate_groups(norm)
        assert len(groups) == 1
        g = groups[0]
        assert g.dedup_confidence == DedupConfidence.LOW.value
        assert g.merged is False
        assert g.review_required is True
        assert len(g.member_record_ids) == 3

    def test_approximate_coordinate_with_matching_locality_can_still_be_high(self):
        # The protection only blocks bare coordinate-only evidence — an
        # approximate coordinate WITH a strict locality match is still
        # legitimate HIGH evidence.
        norm = _normalize(
            [
                _wahis(
                    outbreak_id="OB_1",
                    locality="Ban Dong",
                    outbreak_start_date="2024/03/01",
                    latitude=18.689547,
                    longitude=98.994437,
                    gps_quality=GpsQuality.APPROXIMATE.value,
                    approximate_location=True,
                ),
                _csv(
                    locality="Ban Dong",
                    onset_date="2024-03-01",
                    latitude=18.689547,
                    longitude=98.994437,
                    country="Thailand",
                    species="cattle (domestic)",
                ),
            ]
        )
        # fix country to Thailand on the wahis side too
        norm[0].country = "Thailand"
        m = match_pair(norm[0], norm[1])
        assert m is not None
        assert m.tier == DedupConfidence.HIGH.value


class TestDateTolerance:
    def test_date_diff_within_tolerance_is_a_candidate(self):
        norm = _normalize(
            [
                _csv(onset_date="2020-09-07"),
                _wahis(outbreak_start_date="2020/09/10"),  # exactly DATE_TOLERANCE_DAYS=3 apart
            ]
        )
        m = match_pair(norm[0], norm[1])
        assert m is not None

    def test_date_diff_just_beyond_tolerance_is_not_a_candidate(self):
        norm = _normalize(
            [
                _csv(onset_date="2020-09-07"),
                _wahis(outbreak_start_date="2020/09/11"),  # DATE_TOLERANCE_DAYS + 1
            ]
        )
        m = match_pair(norm[0], norm[1])
        assert m is None

    def test_missing_date_on_either_side_is_not_a_candidate(self):
        # Even with identical coordinates/locality/species, no usable date
        # on one side means no temporal evidence — never merge.
        norm = _normalize(
            [
                _csv(onset_date=None),
                _wahis(),
            ]
        )
        m = match_pair(norm[0], norm[1])
        assert m is None


class TestLocalityMatching:
    def test_strict_rejects_small_edit_distance(self):
        assert locality_matches_strict("Village A", "Village B") is False

    def test_fuzzy_accepts_small_edit_distance_on_long_names(self):
        assert locality_matches("Vavuniya", "Vavuniy") is True

    def test_fuzzy_rejects_short_names_even_with_distance_one(self):
        assert locality_matches("Ao", "Bo") is False

    def test_missing_locality_never_matches(self):
        assert locality_matches(None, "Kopay") is False
        assert locality_matches_strict(None, "Kopay") is False


class TestCanonicalSelection:
    def test_canonical_selection_prefers_wahis_over_csv_when_tied_completeness(self):
        norm = _normalize([_csv(), _wahis()])
        chosen = select_canonical(norm)
        assert chosen == norm[1].source_record_id  # the WAHIS record

    def test_canonical_selection_is_deterministic_regardless_of_input_order(self):
        norm = _normalize([_csv(), _wahis()])
        chosen_forward = select_canonical([norm[0], norm[1]])
        chosen_reversed = select_canonical([norm[1], norm[0]])
        assert chosen_forward == chosen_reversed

    def test_canonical_record_id_matches_a_real_member_id(self):
        norm = _normalize([_csv(), _wahis()])
        groups = build_duplicate_groups(norm)
        g = groups[0]
        assert g.canonical_record_id in g.member_record_ids
