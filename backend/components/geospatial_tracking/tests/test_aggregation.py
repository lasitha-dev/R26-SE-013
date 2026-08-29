"""REPORT-01/02/03/04, DATE-PURITY-01..07, COUNT-01..06, TIME-02, AVAIL-01..04."""

import pytest

from components.geospatial_tracking.domain.enums import AnimalCountQuality, GroupingDateQuality, ReportStatus
from components.geospatial_tracking.domain.models import AnimalReport
from components.geospatial_tracking.schemas import AvailabilityQuality
from components.geospatial_tracking.services.aggregation import aggregate_reports_into_episodes


def _report(**overrides):
    fields = dict(
        report_id="R1",
        disease="LSD",
        farm_id="F1",
        animal_id="C001",
        latitude=9.0,
        longitude=80.0,
        onset_date="2026-01-01",
        status=ReportStatus.CONFIRMED.value,
        accepted_at="2026-01-02",
    )
    fields.update(overrides)
    return AnimalReport(**fields)


def test_report_01_same_animal_duplicate_does_not_double_count():
    reports = [
        _report(report_id="R1", animal_id="C001"),
        _report(report_id="R2", animal_id="C001"),  # same animal resubmitted
    ]
    episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
    assert len(episodes) == 1
    assert episodes[0].affected_animals == 1


def test_report_02_different_animals_increase_affected_count():
    reports = [
        _report(report_id="R1", animal_id="C001"),
        _report(report_id="R2", animal_id="C002"),
        _report(report_id="R3", animal_id="C003"),
    ]
    episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
    assert len(episodes) == 1
    assert episodes[0].affected_animals == 3


def test_report_03_same_farm_separate_episode_after_gap():
    reports = [
        _report(report_id="R1", animal_id="C001", onset_date="2026-01-01"),
        # 6 months later — well beyond any reasonable gap threshold
        _report(report_id="R2", animal_id="C002", onset_date="2026-07-01"),
    ]
    episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
    assert len(episodes) == 2
    assert episodes[0].outbreak_id != episodes[1].outbreak_id
    all_source_ids = {rid for ep in episodes for rid in ep.source_report_ids}
    assert all_source_ids == {"R1", "R2"}


def test_report_03_same_farm_within_gap_stays_one_episode():
    reports = [
        _report(report_id="R1", animal_id="C001", onset_date="2026-01-01"),
        _report(report_id="R2", animal_id="C002", onset_date="2026-01-15"),  # 14 days later
    ]
    episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
    assert len(episodes) == 1
    assert episodes[0].affected_animals == 2


def test_report_04_same_gps_alone_does_not_force_merge():
    # Different farm_id, identical GPS coordinates — must NOT merge.
    reports = [
        _report(report_id="R1", farm_id="F1", animal_id="C001", latitude=9.0, longitude=80.0),
        _report(report_id="R2", farm_id="F2", animal_id="C002", latitude=9.0, longitude=80.0),
    ]
    episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
    assert len(episodes) == 2
    farm_ids = {ep.farm_id for ep in episodes}
    assert farm_ids == {"F1", "F2"}


def test_report_04_missing_farm_id_never_merges_via_gps_alone():
    # No farm_id at all on either side — even identical GPS + disease +
    # same day must not be silently merged (conservative default).
    reports = [
        _report(report_id="R1", farm_id=None, animal_id="C001", latitude=9.0, longitude=80.0),
        _report(report_id="R2", farm_id=None, animal_id="C002", latitude=9.0, longitude=80.0),
    ]
    episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
    assert len(episodes) == 2


def test_episode_gap_days_must_be_passed_explicitly():
    # No implicit default — TypeError if omitted (keyword-only, no default).
    import inspect

    sig = inspect.signature(aggregate_reports_into_episodes)
    assert sig.parameters["episode_gap_days"].default is inspect.Parameter.empty


def test_different_disease_at_same_farm_does_not_merge():
    reports = [
        _report(report_id="R1", disease="LSD"),
        _report(report_id="R2", disease="FMD"),
    ]
    episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
    assert len(episodes) == 2


def test_operational_availability_derived_only_from_accepted_at_of_accepted_reports():
    reports = [
        _report(
            report_id="R1",
            status=ReportStatus.SUBMITTED.value,  # not yet accepted — no operational evidence from this one
            accepted_at=None,
            onset_date="2026-01-01",
        ),
        _report(
            report_id="R2",
            animal_id="C002",
            status=ReportStatus.CONFIRMED.value,
            accepted_at="2026-01-05",
            onset_date="2026-01-02",
        ),
    ]
    episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep.operational_availability_date == "2026-01-05"
    assert ep.operational_availability_quality == AvailabilityQuality.ACTUAL.value
    # biological date must stay separate — earliest onset, not accepted_at
    assert ep.onset_date == "2026-01-01"


def test_no_accepted_report_leaves_operational_availability_unknown():
    reports = [_report(status=ReportStatus.SUBMITTED.value, accepted_at=None)]
    episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
    ep = episodes[0]
    assert ep.operational_availability_date is None
    assert ep.operational_availability_quality == AvailabilityQuality.UNKNOWN.value


class TestDatePurity:
    """DATE-PURITY-01..07: an operational/storage timestamp must NEVER
    silently become OutbreakEpisode.onset_date."""

    def test_date_purity_01_submitted_at_cannot_populate_onset_date(self):
        reports = [
            _report(
                report_id="R1", onset_date=None, submitted_at="2026-01-01",
                notification_date=None, confirmation_date=None, accepted_at=None,
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.onset_date is None
        # it DID get used for grouping, but only labeled as a proxy
        assert ep.episode_grouping_date == "2026-01-01"
        assert ep.episode_grouping_date_quality == GroupingDateQuality.OPERATIONAL_PROXY.value

    def test_date_purity_02_notification_date_cannot_populate_onset_date(self):
        reports = [
            _report(
                report_id="R1", onset_date=None, submitted_at=None,
                notification_date="2026-01-02", confirmation_date=None, accepted_at=None,
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.onset_date is None
        assert ep.episode_grouping_date == "2026-01-02"
        assert ep.episode_grouping_date_quality == GroupingDateQuality.OPERATIONAL_PROXY.value

    def test_date_purity_03_confirmation_date_cannot_populate_onset_date(self):
        reports = [
            _report(
                report_id="R1", onset_date=None, submitted_at=None, notification_date=None,
                confirmation_date="2026-01-03", accepted_at=None,
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.onset_date is None
        assert ep.episode_grouping_date == "2026-01-03"
        assert ep.episode_grouping_date_quality == GroupingDateQuality.OPERATIONAL_PROXY.value

    def test_date_purity_04_accepted_at_cannot_populate_onset_date(self):
        reports = [
            _report(
                report_id="R1", onset_date=None, submitted_at=None, notification_date=None,
                confirmation_date=None, accepted_at="2026-01-04",
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.onset_date is None
        assert ep.episode_grouping_date == "2026-01-04"
        assert ep.episode_grouping_date_quality == GroupingDateQuality.OPERATIONAL_PROXY.value

    def test_date_purity_05_real_onset_remains_biological_onset(self):
        reports = [
            _report(
                report_id="R1", onset_date="2026-01-01", submitted_at="2026-01-10",
                notification_date="2026-01-11", confirmation_date="2026-01-12", accepted_at="2026-01-13",
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.onset_date == "2026-01-01"
        assert ep.episode_grouping_date == "2026-01-01"
        assert ep.episode_grouping_date_quality == GroupingDateQuality.BIOLOGICAL_DATE.value

    def test_date_purity_06_operational_proxy_grouping_date_stays_separately_labeled(self):
        # Two reports, same farm, neither has onset_date but both have
        # submitted_at close together — must cluster (proxy grouping
        # works) but the episode's onset_date must stay None.
        reports = [
            _report(report_id="R1", animal_id="C001", onset_date=None, submitted_at="2026-01-01"),
            _report(report_id="R2", animal_id="C002", onset_date=None, submitted_at="2026-01-05"),
        ]
        episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
        assert len(episodes) == 1
        ep = episodes[0]
        assert ep.onset_date is None
        assert ep.episode_grouping_date == "2026-01-01"
        assert ep.episode_grouping_date_quality == GroupingDateQuality.OPERATIONAL_PROXY.value

    def test_date_purity_07_no_date_evidence_does_not_fabricate_grouping_chronology(self):
        reports = [
            _report(
                report_id="R1", animal_id="C001", onset_date=None, submitted_at=None,
                notification_date=None, confirmation_date=None, accepted_at=None,
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.onset_date is None
        assert ep.episode_grouping_date is None
        assert ep.episode_grouping_date_quality == GroupingDateQuality.UNKNOWN.value
        # farm-having but dateless -> flagged, per the documented fallback rule
        assert ep.aggregation_review_required is True


class TestAnimalCountUncertainty:
    """COUNT-01..06."""

    def test_count_01_same_known_animal_id_twice_is_exact_one(self):
        reports = [
            _report(report_id="R1", animal_id="C001"),
            _report(report_id="R2", animal_id="C001"),
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.affected_animals == 1
        assert ep.affected_animals_quality == AnimalCountQuality.EXACT.value
        assert ep.unidentified_report_count == 0

    def test_count_02_three_distinct_known_animal_ids_is_exact_three(self):
        reports = [
            _report(report_id="R1", animal_id="C001"),
            _report(report_id="R2", animal_id="C002"),
            _report(report_id="R3", animal_id="C003"),
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.affected_animals == 3
        assert ep.affected_animals_quality == AnimalCountQuality.EXACT.value

    def test_count_03_known_plus_one_unidentified_is_lower_bound(self):
        reports = [
            _report(report_id="R1", animal_id="C001"),
            _report(report_id="R2", animal_id=None),
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.affected_animals == 1
        assert ep.affected_animals_quality == AnimalCountQuality.LOWER_BOUND.value
        assert ep.unidentified_report_count == 1

    def test_count_04_two_unidentified_reports_never_claims_exact_two(self):
        reports = [
            _report(report_id="R1", animal_id=None),
            _report(report_id="R2", animal_id=None),
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.affected_animals != 2
        assert ep.affected_animals_quality != AnimalCountQuality.EXACT.value

    def test_count_05_no_identified_animals_is_null_unknown(self):
        reports = [
            _report(report_id="R1", animal_id=None),
            _report(report_id="R2", animal_id=None),
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.affected_animals is None
        assert ep.affected_animals_quality == AnimalCountQuality.UNKNOWN.value
        assert ep.unidentified_report_count == 2

    def test_count_06_same_report_id_twice_cannot_inflate_any_count(self):
        report = _report(report_id="R1", animal_id="C001")
        duplicate = _report(report_id="R1", animal_id="C001")  # identical resend
        episodes = aggregate_reports_into_episodes([report, duplicate], episode_gap_days=30)
        assert len(episodes) == 1
        ep = episodes[0]
        assert ep.affected_animals == 1
        assert ep.source_report_ids == ["R1"]

    def test_count_06_duplicate_report_id_with_different_animal_ids_keeps_first(self):
        # defensive: even if a resend somehow carries a different payload,
        # dedup-by-report_id keeps exactly one report — never two.
        first = _report(report_id="R1", animal_id="C001")
        resend = _report(report_id="R1", animal_id="C999")
        episodes = aggregate_reports_into_episodes([first, resend], episode_gap_days=30)
        assert len(episodes) == 1
        assert episodes[0].source_report_ids == ["R1"]
        assert episodes[0].affected_animals == 1


class TestOperationalAvailabilityHierarchy:
    """AVAIL-01..04."""

    def test_avail_01_biological_onset_never_becomes_operational_availability(self):
        reports = [
            _report(
                report_id="R1", onset_date="2026-01-01", status=ReportStatus.CONFIRMED.value,
                accepted_at=None, confirmation_date=None,
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.operational_availability_date != ep.onset_date
        assert ep.operational_availability_date is None
        assert ep.operational_availability_quality == AvailabilityQuality.UNKNOWN.value

    def test_avail_02_submitted_at_alone_cannot_create_actual_availability(self):
        reports = [
            _report(
                report_id="R1", status=ReportStatus.SUBMITTED.value, submitted_at="2026-01-01",
                accepted_at=None, confirmation_date=None,
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.operational_availability_quality == AvailabilityQuality.UNKNOWN.value
        assert ep.operational_availability_date is None

    def test_avail_03_accepted_at_on_confirmed_record_creates_actual_availability(self):
        reports = [
            _report(report_id="R1", status=ReportStatus.CONFIRMED.value, accepted_at="2026-01-05")
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.operational_availability_date == "2026-01-05"
        assert ep.operational_availability_quality == AvailabilityQuality.ACTUAL.value

    def test_avail_04_confirmation_date_fallback_for_confirmed_without_accepted_at(self):
        reports = [
            _report(
                report_id="R1", status=ReportStatus.CONFIRMED.value, accepted_at=None,
                confirmation_date="2026-01-06",
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.operational_availability_date == "2026-01-06"
        assert ep.operational_availability_quality == AvailabilityQuality.ACTUAL.value

    def test_avail_04_confirmation_date_ignored_for_non_confirmed_status(self):
        # confirmation_date only counts as evidence for CONFIRMED records —
        # an ACCEPTED-but-not-CONFIRMED report with a confirmation_date
        # (e.g. pre-filled/placeholder) must not create ACTUAL evidence.
        reports = [
            _report(
                report_id="R1", status=ReportStatus.ACCEPTED.value, accepted_at=None,
                confirmation_date="2026-01-06",
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.operational_availability_date is None
        assert ep.operational_availability_quality == AvailabilityQuality.UNKNOWN.value

    def test_accepted_at_takes_priority_over_confirmation_date_when_both_exist(self):
        reports = [
            _report(
                report_id="R1", status=ReportStatus.CONFIRMED.value,
                accepted_at="2026-01-05", confirmation_date="2026-01-06",
            )
        ]
        ep = aggregate_reports_into_episodes(reports, episode_gap_days=30)[0]
        assert ep.operational_availability_date == "2026-01-05"


class TestTimeParameterValidation:
    def test_time_02_negative_episode_gap_days_rejected(self):
        with pytest.raises(ValueError, match="episode_gap_days must be >= 0"):
            aggregate_reports_into_episodes([_report()], episode_gap_days=-1)

    def test_episode_gap_days_zero_is_deterministic_same_day_only(self):
        reports = [
            _report(report_id="R1", animal_id="C001", onset_date="2026-01-01"),
            _report(report_id="R2", animal_id="C002", onset_date="2026-01-01"),  # same day
            _report(report_id="R3", animal_id="C003", onset_date="2026-01-02"),  # next day
        ]
        episodes = aggregate_reports_into_episodes(reports, episode_gap_days=0)
        assert len(episodes) == 2
        same_day_ep = next(ep for ep in episodes if "R1" in ep.source_report_ids)
        assert set(same_day_ep.source_report_ids) == {"R1", "R2"}


class TestUndatedReportsWithSharedIdentity:
    def test_undated_reports_sharing_animal_id_still_merge_but_flagged(self):
        reports = [
            _report(
                report_id="R1", animal_id="C001", onset_date=None, submitted_at=None,
                notification_date=None, confirmation_date=None, accepted_at=None,
            ),
            _report(
                report_id="R2", animal_id="C001", onset_date=None, submitted_at=None,
                notification_date=None, confirmation_date=None, accepted_at=None,
            ),
        ]
        episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
        assert len(episodes) == 1
        ep = episodes[0]
        assert set(ep.source_report_ids) == {"R1", "R2"}
        assert ep.aggregation_review_required is True
        assert ep.affected_animals == 1

    def test_undated_report_can_attach_to_dated_cluster_via_shared_animal_id(self):
        reports = [
            _report(report_id="R1", animal_id="C001", onset_date="2026-01-01"),
            _report(
                report_id="R2", animal_id="C001", onset_date=None, submitted_at=None,
                notification_date=None, confirmation_date=None, accepted_at=None,
            ),
        ]
        episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
        assert len(episodes) == 1
        ep = episodes[0]
        assert set(ep.source_report_ids) == {"R1", "R2"}
        # attached via strong identity evidence, not review-flagged
        assert ep.aggregation_review_required is False
        assert ep.onset_date == "2026-01-01"


class TestDiseaseNormalizationInGrouping:
    """DOMAIN-01/02 (Checkpoint 4 Part 0A)."""

    def test_domain_01_lsd_aliases_aggregate_under_one_disease_identity(self):
        reports = [
            _report(report_id="R1", animal_id="C001", disease="LSD"),
            _report(report_id="R2", animal_id="C002", disease="Lumpy skin disease"),
            _report(report_id="R3", animal_id="C003", disease="Lumpy skin disease virus (Inf. with)"),
        ]
        episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
        assert len(episodes) == 1
        assert episodes[0].affected_animals == 3
        # raw text preserved for display/provenance, not overwritten with a normalized key
        assert episodes[0].disease in ("LSD", "Lumpy skin disease", "Lumpy skin disease virus (Inf. with)")

    def test_domain_02_different_diseases_remain_separate(self):
        reports = [
            _report(report_id="R1", animal_id="C001", disease="LSD"),
            _report(report_id="R2", animal_id="C002", disease="FMD"),
        ]
        episodes = aggregate_reports_into_episodes(reports, episode_gap_days=30)
        assert len(episodes) == 2
        diseases = {ep.disease for ep in episodes}
        assert diseases == {"LSD", "FMD"}
