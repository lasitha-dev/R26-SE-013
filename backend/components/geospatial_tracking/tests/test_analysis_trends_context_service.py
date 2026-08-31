"""GEO-ANALYSIS-01 Sections 30-34: `AnalysisTrendsService` tests against
`FakeScientificReadPort` -- no real SQLite/repository touched. Covers
explicit-disease requirements, historical double-counting protection,
selected-origin analytics, FMD partial availability, and the permanent
unavailable-evidence blocks (evaluation/model-run-comparison/confidence/
drivers).
"""

from __future__ import annotations

from components.geospatial_tracking.services.analysis_trends.context_service import AnalysisTrendsService
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import RuntimeAnalysisError10A
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin

from ._my_area_fakes import FakeScientificReadPort, make_geospatial_snapshot, make_historical_trigger_candidate, make_nominal_reach_days, make_runtime_cell, make_source_point


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Sri Lanka:2020-01-05", country="Sri Lanka", t0="2020-01-05", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["A"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


class TestExplicitDiseaseRequired:
    def test_explicit_lsd_accepted(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.status in ("OK", "PARTIAL")
        assert ctx.disease == "LSD"

    def test_explicit_fmd_accepted_independently(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate(disease="Foot and mouth disease")])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="fmd")
        assert ctx.disease == "FMD"

    def test_missing_disease_rejected(self):
        port = FakeScientificReadPort()
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease=None)
        assert ctx.status == "UNSUPPORTED_DISEASE"

    def test_blank_disease_rejected(self):
        port = FakeScientificReadPort()
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="   ")
        assert ctx.status == "UNSUPPORTED_DISEASE"

    def test_unknown_disease_rejected(self):
        port = FakeScientificReadPort()
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="rabies")
        assert ctx.status == "UNSUPPORTED_DISEASE"

    def test_unsupported_disease_never_reaches_the_scientific_port(self):
        port = FakeScientificReadPort()
        AnalysisTrendsService(port).get_analysis_trends(disease="rabies")
        assert port.historical_candidates_calls == []
        assert port.list_origins_calls == []


class TestHistoricalCountsNoDoubleCounting:
    def test_unique_historical_source_records_counted_once(self):
        candidates = [make_historical_trigger_candidate(source_id="A"), make_historical_trigger_candidate(source_id="B"), make_historical_trigger_candidate(source_id="C")]
        port = FakeScientificReadPort(historical_candidates=candidates, origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.historical_summary.historical_source_count == 3

    def test_forecast_origin_count_is_separate_from_source_record_count(self):
        candidates = [make_historical_trigger_candidate(source_id="A"), make_historical_trigger_candidate(source_id="B")]
        origins = [_origin(forecast_origin_id="ORIGIN:X:2020-01-01", t0="2020-01-01"), _origin(forecast_origin_id="ORIGIN:X:2020-01-02", t0="2020-01-02")]
        port = FakeScientificReadPort(historical_candidates=candidates, origins=origins)
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.historical_summary.historical_source_count == 2
        assert ctx.historical_summary.forecast_origin_count == 2

    def test_never_sums_per_origin_eligible_source_counts_as_the_historical_count(self):
        # The scientific port's own list_historical_trigger_candidates is
        # the ONLY thing that feeds historical_source_count -- the
        # service never calls get_origin_analysis (whose eligible_sources
        # could double-count a source across overlapping origin windows)
        # just to build the historical summary.
        candidates = [make_historical_trigger_candidate(source_id="A")]
        port = FakeScientificReadPort(historical_candidates=candidates, origins=[_origin()])
        AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id=None)
        assert port.analysis_calls == []

    def test_first_and_last_observed_dates_correct(self):
        candidates = [
            make_historical_trigger_candidate(source_id="A", effective_availability_date="2020-03-01"),
            make_historical_trigger_candidate(source_id="B", effective_availability_date="2019-06-15"),
            make_historical_trigger_candidate(source_id="C", effective_availability_date="2021-01-01"),
        ]
        port = FakeScientificReadPort(historical_candidates=candidates, origins=[])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.historical_summary.first_observed_date == "2019-06-15"
        assert ctx.historical_summary.last_observed_date == "2021-01-01"

    def test_zero_historical_records_returns_no_historical_data_status(self):
        port = FakeScientificReadPort(historical_candidates=[], origins=[])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.status == "NO_HISTORICAL_DATA"
        assert ctx.historical_summary.historical_source_count == 0
        assert ctx.historical_summary.first_observed_date is None

    def test_no_live_or_active_outbreak_terminology_in_historical_summary(self):
        candidates = [make_historical_trigger_candidate()]
        port = FakeScientificReadPort(historical_candidates=candidates, origins=[])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        for value in (ctx.historical_summary.status, ctx.historical_summary.count_basis):
            lowered = str(value).lower()
            assert "live" not in lowered
            assert "active" not in lowered


class TestSelectedOriginNoAutoSelection:
    def test_absent_origin_id_never_calls_get_origin_analysis(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id=None)
        assert ctx.selected_origin_analytics is None
        assert port.analysis_calls == []

    def test_real_origin_accepted(self):
        snapshot = make_geospatial_snapshot(
            forecast_origin_id="ORIGIN:Sri Lanka:2020-01-05", t0="2020-01-05",
            eligible_sources=(make_source_point(),), nominal_reach_by_day=make_nominal_reach_days(),
            cells=(make_runtime_cell(),), apparent_rate_context={"apparent_rate_km_day": 4.0},
        )
        port = FakeScientificReadPort(
            historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()],
            analyses_by_origin_id={"ORIGIN:Sri Lanka:2020-01-05": snapshot},
        )
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:Sri Lanka:2020-01-05")
        assert ctx.status == "OK"
        assert ctx.selected_origin_analytics.status == "AVAILABLE"
        assert ctx.selected_origin_analytics.t0 == "2020-01-05"

    def test_nonexistent_origin_rejected(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:GHOST:1999-01-01")
        assert ctx.status == "ORIGIN_NOT_FOUND"
        # historical evidence is still attached -- a bad origin id doesn't hide real historical data
        assert ctx.historical_summary is not None
        assert ctx.historical_summary.historical_source_count == 1

    def test_wrong_disease_origin_rejected_via_origin_not_found(self):
        port = FakeScientificReadPort(
            historical_candidates=[make_historical_trigger_candidate(disease="Lumpy skin disease")], origins=[_origin()],
            origin_errors={"ORIGIN:Other:2020-01-05": RuntimeAnalysisError10A("ORIGIN_NOT_FOUND", "wrong disease scope")},
        )
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="ORIGIN:Other:2020-01-05")
        assert ctx.status == "ORIGIN_NOT_FOUND"

    def test_t0_preserved_verbatim(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", t0="2022-07-14", eligible_sources=(make_source_point(),))
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        assert ctx.selected_origin_analytics.t0 == "2022-07-14"

    def test_apparent_rate_only_present_when_real_context_exists(self):
        snapshot_with = make_geospatial_snapshot(forecast_origin_id="O1", apparent_rate_context={"apparent_rate_km_day": 3.9})
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot_with})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        assert ctx.selected_origin_analytics.apparent_rate.status == "AVAILABLE"
        assert ctx.selected_origin_analytics.apparent_rate.apparent_rate_km_day == 3.9

        snapshot_without = make_geospatial_snapshot(forecast_origin_id="O2", apparent_rate_context={})
        port2 = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O2")], analyses_by_origin_id={"O2": snapshot_without})
        ctx2 = AnalysisTrendsService(port2).get_analysis_trends(disease="lsd", origin_id="O2")
        assert ctx2.selected_origin_analytics.apparent_rate.status == "UNAVAILABLE_RUNTIME_METRIC"
        assert ctx2.selected_origin_analytics.apparent_rate.apparent_rate_km_day is None

    def test_bearing_direction_never_fabricated_as_a_single_origin_scalar(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", cells=(make_runtime_cell(), make_runtime_cell(scientific_cell_id="CELL-2")))
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        assert ctx.selected_origin_analytics.direction_context.status == "UNAVAILABLE_RUNTIME_METRIC"

    def test_nominal_reach_real_values_only_and_disclaimer_exact(self):
        days = make_nominal_reach_days([1, 2, 3, 4, 5, 6, 7], km_per_day=4.0)
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", nominal_reach_by_day=days)
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        reach = ctx.selected_origin_analytics.nominal_reach
        assert reach.status == "AVAILABLE"
        assert reach.disclaimer == "Nominal reach — visualization only, not a disease boundary."
        assert [d.day for d in reach.days] == [1, 2, 3, 4, 5, 6, 7]
        assert reach.days[0].nominal_reach_km == 4.0

    def test_d0_never_fabricated_as_zero_km(self):
        # build_nominal_reach_by_day_9c only ever produces D1-D7 -- D0
        # never appears as a fabricated 0km entry.
        days = make_nominal_reach_days([1, 2, 3, 4, 5, 6, 7])
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", nominal_reach_by_day=days)
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        assert all(d.day != 0 for d in ctx.selected_origin_analytics.nominal_reach.days)


class TestFmdPartialAvailability:
    def test_fmd_historical_trend_available_while_model_not_ready(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate(disease="Foot and mouth disease")], origins=[])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="fmd")
        assert ctx.historical_summary.status == "AVAILABLE"
        assert ctx.historical_trend.status == "AVAILABLE"
        assert ctx.model_evaluation.status == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"

    def test_fmd_selected_origin_analytics_honestly_model_not_ready(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate(disease="Foot and mouth disease")], origins=[])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="fmd", origin_id="ORIGIN:X:2020-01-01")
        assert ctx.status == "PARTIAL"
        assert ctx.selected_origin_analytics.status == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"
        # never silently reuses LSD's frozen values
        assert ctx.selected_origin_analytics.apparent_rate is None
        assert ctx.selected_origin_analytics.nominal_reach is None
        # get_origin_analysis is never even called once the model-readiness gate fails
        assert port.analysis_calls == []

    def test_fmd_area_score_availability_still_honest_limitation(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate(disease="Foot and mouth disease")], origins=[])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="fmd", origin_id="ORIGIN:X:2020-01-01")
        assert ctx.selected_origin_analytics.area_score_availability == "SCORE_UNAVAILABLE_CELL_GEOMETRY_NOT_EXPOSED_FOR_CONTAINMENT"


class TestEvaluationNeverFabricated:
    def test_only_real_metric_names_exposed_none_this_checkpoint(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.model_evaluation.metrics == []

    def test_missing_metric_never_becomes_numeric_zero(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.model_evaluation.metrics == []
        assert ctx.model_evaluation.status != "0"
        assert ctx.model_evaluation.status == "EVALUATION_METRICS_NOT_AVAILABLE"

    def test_no_accuracy_precision_recall_f1_auc_field_anywhere(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        import json

        blob = json.dumps(ctx.as_dict()).lower()
        for forbidden in ("accuracy", "precision", "recall", "\"f1\"", "\"auc\""):
            assert forbidden not in blob

    def test_evaluation_provenance_never_fabricated_for_model_ready_disease(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.model_evaluation.status == "EVALUATION_METRICS_NOT_AVAILABLE"

    def test_fewer_than_two_comparable_runs_marks_comparison_unavailable(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.model_run_comparison.status == "MODEL_RUN_COMPARISON_UNAVAILABLE"

    def test_no_run_a_run_b_or_improvement_percentage_ever_appears(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        import json

        blob = json.dumps(ctx.as_dict()).lower()
        assert "run a" not in blob
        assert "run b" not in blob
        assert "improved by" not in blob


class TestConfidenceNeverFabricated:
    def test_no_explicit_confidence_field_marks_not_available(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.confidence.status == "CONFIDENCE_NOT_AVAILABLE"

    def test_confidence_not_derived_from_historical_source_count(self):
        few = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        many = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate(source_id=str(i)) for i in range(50)])
        ctx_few = AnalysisTrendsService(few).get_analysis_trends(disease="lsd")
        ctx_many = AnalysisTrendsService(many).get_analysis_trends(disease="lsd")
        assert ctx_few.confidence.status == ctx_many.confidence.status == "CONFIDENCE_NOT_AVAILABLE"

    def test_confidence_not_derived_from_relative_spatial_score(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", cells=(make_runtime_cell(risk=make_runtime_cell().risk),))
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        assert ctx.confidence.status == "CONFIDENCE_NOT_AVAILABLE"


class TestDriversNeverFabricated:
    def test_no_driver_decomposition_marks_not_available(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.drivers.status == "DRIVER_DECOMPOSITION_NOT_AVAILABLE"

    def test_no_fake_rainfall_humidity_wind_contribution_percentage(self):
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()])
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        import json

        blob = json.dumps(ctx.as_dict()).lower()
        for forbidden in ("rainfall", "humidity", "wind 2", "wind 3"):
            assert forbidden not in blob


class TestRelativeSpatialScoreSemantics:
    def test_label_preserved_and_never_a_percentage(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", cells=(make_runtime_cell(risk=make_runtime_cell().risk),))
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        dist = ctx.selected_origin_analytics.relative_spatial_score_distribution
        assert dist.label == "Relative Spatial Score"
        assert isinstance(dist.min_score, float)

    def test_static_frozen_temporal_basis_preserved(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", cells=(make_runtime_cell(),))
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        assert ctx.selected_origin_analytics.relative_spatial_score_distribution.temporal_basis == "STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT"

    def test_farm_point_score_remains_explicitly_unavailable(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", cells=(make_runtime_cell(),))
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        assert ctx.selected_origin_analytics.area_score_availability == "SCORE_UNAVAILABLE_CELL_GEOMETRY_NOT_EXPOSED_FOR_CONTAINMENT"

    def test_cross_snapshot_comparison_disabled(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", cells=(make_runtime_cell(),))
        port = FakeScientificReadPort(historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        assert ctx.selected_origin_analytics.relative_spatial_score_distribution.cross_snapshot_comparison_status == "CROSS_SNAPSHOT_SCORE_COMPARISON_NOT_SUPPORTED"


class TestInternalErrorNeverSilentlyOk:
    def test_historical_read_failure_maps_to_internal_error(self):
        port = FakeScientificReadPort(raise_on_historical_candidates=RuntimeError("db exploded"))
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd")
        assert ctx.status == "ANALYSIS_INTERNAL_ERROR"

    def test_unexpected_runtime_analysis_error_status_maps_to_internal_error(self):
        port = FakeScientificReadPort(
            historical_candidates=[make_historical_trigger_candidate()], origins=[_origin(forecast_origin_id="O1")],
            origin_errors={"O1": RuntimeAnalysisError10A("ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE", "no sources")},
        )
        ctx = AnalysisTrendsService(port).get_analysis_trends(disease="lsd", origin_id="O1")
        assert ctx.status == "ANALYSIS_INTERNAL_ERROR"
