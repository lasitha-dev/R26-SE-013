from components.geospatial_tracking.data_processing.dedup import build_duplicate_groups
from components.geospatial_tracking.data_processing.model_candidate import (
    build_conservative_rows,
    build_model_candidate_report,
    build_sri_lanka_adjudication,
)
from components.geospatial_tracking.data_processing.normalize import (
    assign_spatial_independence,
    normalize_raw_records,
)
from components.geospatial_tracking.data_processing.quality import compute_quality
from components.geospatial_tracking.schemas import (
    AvailabilityQuality,
    DedupStatus,
    GpsQuality,
    RawOutbreakRecord,
    SourceSystem,
)


def _csv(**overrides):
    fields = dict(
        source_file="events.csv",
        source_system=SourceSystem.FAO_EMPRESI_CSV.value,
        country="Sri Lanka",
        event_id="UNFAO-LEG-1",
        onset_date="2020-09-07",
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
        locality="Kopay",
        latitude=9.7151701,
        longitude=80.0668497,
        gps_quality=GpsQuality.EXACT.value,
        species="cattle (domestic)",
    )
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def _build(raw_records):
    normalized = normalize_raw_records(raw_records)
    assign_spatial_independence(normalized)
    groups = build_duplicate_groups(normalized)
    conservative_rows = build_conservative_rows(normalized, groups)
    return normalized, groups, conservative_rows


def _row_for(conservative_rows, source_record_id):
    for row in conservative_rows:
        if row["source_record_id"] == source_record_id:
            return row
    raise AssertionError(f"no conservative row for {source_record_id}")


class TestConfidenceTierPolicy:
    def test_high_group_auto_merges(self):
        _, _, rows = _build([_csv(), _wahis()])
        assert len(rows) == 1
        row = rows[0]
        assert row["dedup_status"] == DedupStatus.AUTO_MERGED_HIGH.value
        assert row["dedup_resolved"] is True
        assert row["review_required"] is False
        assert row["model_candidate"] is True
        assert row["model_exclusion_reason"] == ""

    def test_medium_group_is_not_silently_resolved(self):
        # species match, but only loose (not tight) coordinate proximity
        # and no locality match -> MEDIUM per dedup.py's documented tiers.
        raw = [
            _csv(locality="Northtown", latitude=9.0, longitude=80.0),
            _wahis(
                locality="Souththorpe",
                outbreak_start_date="2020/09/08",
                latitude=9.03,
                longitude=80.0,  # ~3.3km — inside LOOSE (5km) but outside TIGHT (2km)
            ),
        ]
        normalized, groups, rows = _build(raw)
        assert len(groups) == 1
        assert groups[0].dedup_confidence == "MEDIUM"
        assert len(rows) == 2  # NOT merged into one row
        for row in rows:
            assert row["dedup_status"] == DedupStatus.REVIEW_MEDIUM.value
            assert row["dedup_resolved"] is False
            assert row["review_required"] is True
            assert row["model_candidate"] is False
            assert "MEDIUM" in row["model_exclusion_reason"]
            # each unresolved row represents only its OWN raw record, not
            # the whole candidate group — member_count must not overcount.
            assert row["member_count"] == 1
            assert row["member_record_ids"] == row["source_record_id"]
            assert row["duplicate_group_id"] == groups[0].duplicate_group_id

    def test_low_group_remains_unresolved(self):
        raw = [
            _csv(locality="Nowhereville", latitude=9.0, longitude=80.0, species="cattle"),
            _wahis(
                locality="Elsewhereton",
                outbreak_start_date="2020/09/08",
                latitude=9.0,
                longitude=80.0,
                species="buffalo",  # species does NOT match -> LOW tier
            ),
        ]
        normalized, groups, rows = _build(raw)
        assert groups[0].dedup_confidence == "LOW"
        assert len(rows) == 2
        for row in rows:
            assert row["dedup_status"] == DedupStatus.REVIEW_LOW.value
            assert row["model_candidate"] is False
            assert row["dedup_resolved"] is False

    def test_unresolved_candidates_can_never_become_model_candidate(self):
        raw = [
            _csv(locality="Nowhereville", latitude=9.0, longitude=80.0, species="cattle"),
            _wahis(locality="Elsewhereton", outbreak_start_date="2020/09/08", latitude=9.0, longitude=80.0, species="buffalo"),
        ]
        _, _, rows = _build(raw)
        assert all(row["model_candidate"] is False for row in rows if row["dedup_status"].startswith("REVIEW"))

    def test_singleton_remains_eligible(self):
        raw = [_wahis(country="Vietnam", locality="Solo Village", outbreak_id="OB_9")]
        _, groups, rows = _build(raw)
        assert groups == []
        assert len(rows) == 1
        row = rows[0]
        assert row["dedup_status"] == DedupStatus.SINGLETON.value
        assert row["dedup_resolved"] is True
        assert row["model_candidate"] is True
        assert row["model_exclusion_reason"] == ""


class TestApproximateCoordinateProtection:
    def test_distinct_outbreaks_sharing_approximate_coordinate_stay_separate_and_unresolved(self):
        raw = [
            _wahis(
                outbreak_id="OB_A",
                locality="Village A",
                outbreak_start_date="2024/03/01",
                latitude=18.689547,
                longitude=98.994437,
                gps_quality=GpsQuality.APPROXIMATE.value,
                approximate_location=True,
                country="Thailand",
            ),
            _wahis(
                outbreak_id="OB_B",
                locality="Village B",
                outbreak_start_date="2024/03/02",
                latitude=18.689547,
                longitude=98.994437,
                gps_quality=GpsQuality.APPROXIMATE.value,
                approximate_location=True,
                country="Thailand",
            ),
        ]
        _, groups, rows = _build(raw)
        assert groups[0].dedup_confidence == "LOW"
        assert len(rows) == 2
        assert all(row["model_candidate"] is False for row in rows)
        assert all(row["dedup_status"] == DedupStatus.REVIEW_LOW.value for row in rows)
        # never merged into one record
        assert {row["outbreak_id"] for row in rows} == {"OB_A", "OB_B"}


class TestSriLankaChavakachcheriHandling:
    def _scenario(self):
        raw = [
            _csv(event_id="UNFAO-LEG-286588"),
            _csv(event_id="UNFAO-LEG-286458"),
            _wahis(outbreak_id="OB_80063", locality="Kopay"),
            _csv(
                event_id="UNFAO-LEG-286589",
                locality="Chavakachcheri",
                onset_date="2020-09-09",
                latitude=9.657901,
                longitude=80.164307,
            ),
            _csv(
                event_id="UNFAO-LEG-286459",
                locality="Chavakachcheri",
                onset_date="2020-09-17",  # 8 days off — the real source discrepancy
                latitude=9.6579014,
                longitude=80.1643076,
            ),
            _wahis(
                outbreak_id="OB_80064",
                locality="Chavakachcheri",
                outbreak_start_date="2020/09/09",
                latitude=9.6579014,
                longitude=80.1643076,
            ),
        ]
        return _build(raw)

    def test_well_matched_chavakachcheri_pair_still_auto_merges_high(self):
        normalized, groups, rows = self._scenario()
        good_csv_id = next(
            r.source_record_id for r in normalized if r.event_id == "UNFAO-LEG-286589"
        )
        # find the merged row containing the good CSV record
        merged_row = next(r for r in rows if good_csv_id in r["member_record_ids"].split(";"))
        assert merged_row["dedup_status"] == DedupStatus.AUTO_MERGED_HIGH.value
        assert merged_row["model_candidate"] is True

    def test_conflicting_chavakachcheri_row_is_preserved_and_flagged_not_model_candidate(self):
        normalized, groups, rows = self._scenario()
        bad_csv_id = next(
            r.source_record_id for r in normalized if r.event_id == "UNFAO-LEG-286459"
        )
        row = _row_for(rows, bad_csv_id)
        assert row["dedup_status"] == DedupStatus.REVIEW_LOW.value
        assert row["dedup_resolved"] is False
        assert row["review_required"] is True
        assert row["model_candidate"] is False
        assert "8 days" in row["model_exclusion_reason"]
        # provenance preserved verbatim, not fabricated or altered
        assert row["onset_date"] == "2020-09-17"
        assert row["locality"] == "Chavakachcheri"

    def test_conflict_does_not_downgrade_the_clean_high_group(self):
        # The critical guard: flagging the outlier record must never drag
        # the otherwise-clean WAHIS+CSV HIGH match down via transitivity.
        normalized, groups, rows = self._scenario()
        good_csv_id = next(
            r.source_record_id for r in normalized if r.event_id == "UNFAO-LEG-286589"
        )
        wahis_id = next(r.source_record_id for r in normalized if r.outbreak_id == "OB_80064")
        merged_row = next(r for r in rows if good_csv_id in r["member_record_ids"].split(";"))
        assert wahis_id in merged_row["member_record_ids"].split(";")
        assert merged_row["dedup_status"] == DedupStatus.AUTO_MERGED_HIGH.value
        assert merged_row["dedup_confidence"] == "HIGH"

    def test_six_real_episodes_all_traceable_in_conservative_view(self):
        normalized, groups, rows = self._scenario()
        localities_merged_high = {
            row["locality"] for row in rows if row["dedup_status"] == DedupStatus.AUTO_MERGED_HIGH.value
        }
        assert localities_merged_high == {"Kopay", "Chavakachcheri"}  # 2 of the 6 test localities used here

    def test_no_raw_record_is_deleted(self):
        normalized, groups, rows = self._scenario()
        all_raw_ids = {r.source_record_id for r in normalized}
        covered_ids = set()
        for row in rows:
            covered_ids.update(row["member_record_ids"].split(";"))
        assert covered_ids == all_raw_ids

    def test_sri_lanka_adjudication_table_shows_every_raw_record(self):
        normalized, groups, rows = self._scenario()
        sl_rows = build_sri_lanka_adjudication(normalized, groups, rows)
        assert len(sl_rows) == 6  # 4 CSV rows + 2 WAHIS outbreaks in this scenario
        bad_row = next(r for r in sl_rows if r["date"] == "2020-09-17")
        assert bad_row["match_status"] == DedupStatus.REVIEW_LOW.value
        assert bad_row["model_candidate"] is False
        good_rows = [r for r in sl_rows if r["locality"] == "Kopay"]
        assert all(r["model_candidate"] is True for r in good_rows)
        assert all(r["matched_wahis_outbreak_id"] == "OB_80063" for r in good_rows)


class TestNoDataDeletion:
    def test_raw_records_never_deleted_general_case(self):
        raw = [
            _csv(event_id="A"),
            _csv(event_id="B"),
            _wahis(outbreak_id="OB_1"),
        ]
        normalized, groups, rows = _build(raw)
        all_raw_ids = {r.source_record_id for r in normalized}
        covered_ids = set()
        for row in rows:
            covered_ids.update(row["member_record_ids"].split(";"))
        assert covered_ids == all_raw_ids
        assert len(normalized) == 3  # nothing removed from the normalized list itself

    def test_member_count_sums_to_raw_record_count_including_medium_and_low(self):
        # Regression guard: an unresolved MEDIUM/LOW row must report
        # member_count=1 for itself, not the whole candidate group's size —
        # otherwise every raw record gets double/triple counted.
        raw = [
            _csv(),
            _wahis(),  # HIGH pair -> 1 merged row, member_count=2
            _csv(locality="Northtown", latitude=9.0, longitude=80.0, event_id="M1"),
            _wahis(
                locality="Souththorpe",
                outbreak_start_date="2020/09/08",
                latitude=9.03,
                longitude=80.0,
                outbreak_id="OB_M1",
            ),  # MEDIUM pair -> 2 unresolved rows, member_count=1 each
            _wahis(country="Vietnam", locality="Solo", outbreak_id="OB_SOLO"),  # singleton
        ]
        normalized, groups, rows = _build(raw)
        assert sum(row["member_count"] for row in rows) == len(normalized) == 5


class TestDqsNeverOverridesDedupStatus:
    def test_high_dqs_does_not_make_an_unresolved_record_a_model_candidate(self):
        # Build a MEDIUM-confidence record that is otherwise very complete
        # (would score a high DQS) and confirm model_candidate is still
        # False — DQS is never consulted by the conservative-view builder.
        raw = [
            _csv(locality="Northtown", latitude=9.0, longitude=80.0),
            _wahis(
                locality="Souththorpe",
                outbreak_start_date="2020/09/08",
                latitude=9.03,
                longitude=80.0,
                diagnostic_method="Clinical, Diagnostic test",
                diagnostic_result="Confirmed",
                susceptible=100,
                cases=10,
                deaths=2,
                vaccinated=0,
                event_status="Stable",
            ),
        ]
        normalized, groups, rows = _build(raw)
        wahis_record = next(r for r in normalized if r.source_system == SourceSystem.WAHIS_PDF.value)
        quality = compute_quality(wahis_record)
        assert quality.dqs >= 0.7  # genuinely high DQS
        row = _row_for(rows, wahis_record.source_record_id)
        assert row["dedup_status"] == DedupStatus.REVIEW_MEDIUM.value
        assert row["model_candidate"] is False  # DQS did not override this


class TestAvailabilitySemanticsUnchanged:
    def test_operational_and_proxy_availability_pass_through_unchanged(self):
        raw = [
            _wahis(
                country="Vietnam",
                locality="Solo Village",
                outbreak_id="OB_9",
                proxy_availability_date="2020/09/07",
                proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
            )
        ]
        _, _, rows = _build(raw)
        row = rows[0]
        assert row["operational_availability_date"] is None
        assert row["operational_availability_quality"] == AvailabilityQuality.UNKNOWN.value
        assert row["proxy_availability_date"] == "2020/09/07"
        assert row["proxy_availability_quality"] == AvailabilityQuality.EVENT_DATE_PROXY.value
        assert row["proxy_availability_source_field"] == "outbreak_start_date"

    def test_proxy_can_never_appear_as_actual_in_conservative_view(self):
        # Enforced structurally by RawOutbreakRecord.__post_init__ already
        # (see test_schemas.py) — confirm it still holds through the full
        # normalize -> dedup -> conservative pipeline.
        raw = [_wahis(country="Vietnam", locality="Solo Village", outbreak_id="OB_9")]
        _, _, rows = _build(raw)
        assert rows[0]["proxy_availability_quality"] != AvailabilityQuality.ACTUAL.value
        assert rows[0]["operational_availability_quality"] != AvailabilityQuality.ACTUAL.value


class TestModelCandidateReport:
    def test_report_projects_expected_columns(self):
        _, _, rows = _build([_csv(), _wahis()])
        report = build_model_candidate_report(rows)
        assert len(report) == 1
        for key in (
            "source_record_id",
            "dedup_status",
            "dedup_resolved",
            "model_candidate",
            "model_exclusion_reason",
        ):
            assert key in report[0]
