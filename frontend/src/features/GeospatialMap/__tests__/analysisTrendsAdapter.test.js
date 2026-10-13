import { describe, expect, it } from 'vitest'

import { normalizeAnalysisTrendsContext } from '../adapters/analysisTrendsAdapter'

const REAL_LSD_RESPONSE = {
  status: 'OK',
  disease: 'LSD',
  scope_country: 'Sri Lanka',
  historical_summary: {
    status: 'AVAILABLE',
    historical_source_count: 6,
    forecast_origin_count: 5,
    first_observed_date: '2020-09-07',
    last_observed_date: '2020-10-28',
    count_basis: 'HISTORICAL_SOURCE_RECORDS',
  },
  historical_trend: {
    status: 'AVAILABLE',
    period_basis: 'WEEK',
    points: [
      { period: '2020-W36', count: 0, count_basis: 'HISTORICAL_SOURCE_RECORDS' },
      { period: '2020-W37', count: 2, count_basis: 'HISTORICAL_SOURCE_RECORDS' },
    ],
  },
  selected_origin_analytics: {
    status: 'AVAILABLE',
    origin_id: 'ORIGIN:Sri Lanka:2020-09-07',
    disease: 'LSD',
    t0: '2020-09-07',
    scientific_mode: 'RETROSPECTIVE_PROXY',
    eligible_source_count: 3,
    apparent_rate: { status: 'AVAILABLE', apparent_rate_km_day: 3.946421443154751, context: { rate_status: 'FROZEN_DEVELOPMENT_HISTORICAL_APPARENT_RATE' } },
    direction_context: { status: 'UNAVAILABLE_RUNTIME_METRIC', reason: 'per-cell only' },
    nominal_reach: {
      status: 'AVAILABLE',
      disclaimer: 'Nominal reach — visualization only, not a disease boundary.',
      days: [
        { day: 1, nominal_reach_km: 3.9, derived_interval_lower_km: 3.5, derived_interval_upper_km: 4.3 },
        { day: 2, nominal_reach_km: 7.9, derived_interval_lower_km: 7.1, derived_interval_upper_km: 8.7 },
      ],
    },
    relative_spatial_score_distribution: {
      status: 'AVAILABLE',
      label: 'Relative Spatial Score',
      temporal_basis: 'STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT',
      min_score: 0.357,
      median_score: 0.48,
      max_score: 0.868,
      n_cells_scored: 88,
      cross_snapshot_comparison_status: 'CROSS_SNAPSHOT_SCORE_COMPARISON_NOT_SUPPORTED',
    },
    area_score_availability: 'SCORE_UNAVAILABLE_CELL_GEOMETRY_NOT_EXPOSED_FOR_CONTAINMENT',
  },
  model_evaluation: { status: 'EVALUATION_METRICS_NOT_AVAILABLE' },
  model_run_comparison: { status: 'MODEL_RUN_COMPARISON_UNAVAILABLE' },
  confidence: { status: 'CONFIDENCE_NOT_AVAILABLE' },
  drivers: { status: 'DRIVER_DECOMPOSITION_NOT_AVAILABLE' },
  generated_at: '2026-08-28T00:00:00+00:00',
}

describe('GEO-ANALYSIS-02-ADAPTER-01: top-level fields preserved', () => {
  it('scope_country preserved', () => {
    expect(normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).scopeCountry).toBe('Sri Lanka')
  })

  it('historical_source_count preserved', () => {
    expect(normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).historicalSummary.historicalSourceCount).toBe(6)
  })

  it('forecast_origin_count preserved separately from source count', () => {
    const summary = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).historicalSummary
    expect(summary.forecastOriginCount).toBe(5)
    expect(summary.forecastOriginCount).not.toBe(summary.historicalSourceCount)
  })

  it('first observed date preserved', () => {
    expect(normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).historicalSummary.firstObservedDate).toBe('2020-09-07')
  })

  it('last observed date preserved', () => {
    expect(normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).historicalSummary.lastObservedDate).toBe('2020-10-28')
  })

  it('trend period basis preserved', () => {
    expect(normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).historicalTrend.periodBasis).toBe('WEEK')
  })

  it('real zero trend points preserved, not stripped', () => {
    const points = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).historicalTrend.points
    expect(points).toHaveLength(2)
    expect(points[0]).toEqual({ period: '2020-W36', count: 0, countBasis: 'HISTORICAL_SOURCE_RECORDS' })
  })
})

describe('GEO-ANALYSIS-02-ADAPTER-02: defensive numeric validation', () => {
  it('negative historical_source_count rejected -> null, never coerced', () => {
    const raw = { ...REAL_LSD_RESPONSE, historical_summary: { ...REAL_LSD_RESPONSE.historical_summary, historical_source_count: -1 } }
    expect(normalizeAnalysisTrendsContext(raw).historicalSummary.historicalSourceCount).toBeNull()
  })

  it('NaN count rejected', () => {
    const raw = { ...REAL_LSD_RESPONSE, historical_summary: { ...REAL_LSD_RESPONSE.historical_summary, historical_source_count: NaN } }
    expect(normalizeAnalysisTrendsContext(raw).historicalSummary.historicalSourceCount).toBeNull()
  })

  it('Infinity count rejected', () => {
    const raw = { ...REAL_LSD_RESPONSE, historical_summary: { ...REAL_LSD_RESPONSE.historical_summary, forecast_origin_count: Infinity } }
    expect(normalizeAnalysisTrendsContext(raw).historicalSummary.forecastOriginCount).toBeNull()
  })

  it('malformed trend point (negative count) rejected and dropped from the list', () => {
    const raw = {
      ...REAL_LSD_RESPONSE,
      historical_trend: { ...REAL_LSD_RESPONSE.historical_trend, points: [{ period: '2020-W01', count: -5 }, { period: '2020-W02', count: 3 }] },
    }
    const points = normalizeAnalysisTrendsContext(raw).historicalTrend.points
    expect(points).toHaveLength(1)
    expect(points[0].period).toBe('2020-W02')
  })

  it('malformed trend point (missing period) rejected and dropped', () => {
    const raw = { ...REAL_LSD_RESPONSE, historical_trend: { ...REAL_LSD_RESPONSE.historical_trend, points: [{ count: 3 }] } }
    expect(normalizeAnalysisTrendsContext(raw).historicalTrend.points).toHaveLength(0)
  })

  it('non-integer count rejected', () => {
    const raw = { ...REAL_LSD_RESPONSE, historical_trend: { ...REAL_LSD_RESPONSE.historical_trend, points: [{ period: '2020-W01', count: 3.5 }] } }
    expect(normalizeAnalysisTrendsContext(raw).historicalTrend.points).toHaveLength(0)
  })
})

describe('GEO-ANALYSIS-02-ADAPTER-03: selected origin analytics', () => {
  it('selected_origin_analytics optional -- null when absent', () => {
    const raw = { ...REAL_LSD_RESPONSE, selected_origin_analytics: null }
    expect(normalizeAnalysisTrendsContext(raw).selectedOriginAnalytics).toBeNull()
  })

  it('apparent-rate value/unit-bearing field preserved', () => {
    const analytics = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).selectedOriginAnalytics
    expect(analytics.apparentRate.apparentRateKmDay).toBeCloseTo(3.946421443154751)
    expect(analytics.apparentRate.status).toBe('AVAILABLE')
  })

  it('direction unavailable preserved verbatim, never converted to a numeric bearing', () => {
    const analytics = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).selectedOriginAnalytics
    expect(analytics.directionContext.status).toBe('UNAVAILABLE_RUNTIME_METRIC')
  })

  it('nominal reach D1-D7 preserved', () => {
    const days = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).selectedOriginAnalytics.nominalReach.days
    expect(days.map((d) => d.day)).toEqual([1, 2])
    expect(days[0].nominalReachKm).toBeCloseTo(3.9)
  })

  it('no D0=0 fabricated -- a D0 entry in the raw response is dropped, never rendered', () => {
    const raw = {
      ...REAL_LSD_RESPONSE,
      selected_origin_analytics: {
        ...REAL_LSD_RESPONSE.selected_origin_analytics,
        nominal_reach: { ...REAL_LSD_RESPONSE.selected_origin_analytics.nominal_reach, days: [{ day: 0, nominal_reach_km: 0 }, { day: 1, nominal_reach_km: 3.9 }] },
      },
    }
    const days = normalizeAnalysisTrendsContext(raw).selectedOriginAnalytics.nominalReach.days
    expect(days.some((d) => d.day === 0)).toBe(false)
  })

  it('nominal reach disclaimer preserved exactly', () => {
    const reach = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).selectedOriginAnalytics.nominalReach
    expect(reach.disclaimer).toBe('Nominal reach — visualization only, not a disease boundary.')
  })

  it('RSS min/median/max preserved as raw unitless values', () => {
    const dist = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).selectedOriginAnalytics.relativeSpatialScoreDistribution
    expect(dist.minScore).toBe(0.357)
    expect(dist.medianScore).toBe(0.48)
    expect(dist.maxScore).toBe(0.868)
  })

  it('RSS never converted to a percentage -- value stays the raw fractional score', () => {
    const dist = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).selectedOriginAnalytics.relativeSpatialScoreDistribution
    expect(dist.maxScore).toBeLessThan(1)
    expect(dist.maxScore).not.toBe(86.8)
  })

  it('cross-snapshot unsupported status preserved', () => {
    const dist = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).selectedOriginAnalytics.relativeSpatialScoreDistribution
    expect(dist.crossSnapshotComparisonStatus).toBe('CROSS_SNAPSHOT_SCORE_COMPARISON_NOT_SUPPORTED')
  })

  it('area_score_availability preserved -- exact farm-point score stays unavailable', () => {
    const analytics = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).selectedOriginAnalytics
    expect(analytics.areaScoreAvailability).toBe('SCORE_UNAVAILABLE_CELL_GEOMETRY_NOT_EXPOSED_FOR_CONTAINMENT')
  })
})

describe('GEO-ANALYSIS-02-ADAPTER-04: evidence-availability blocks', () => {
  it('model evaluation unavailable preserved', () => {
    expect(normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).modelEvaluation.status).toBe('EVALUATION_METRICS_NOT_AVAILABLE')
  })

  it('confidence unavailable preserved', () => {
    expect(normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).confidence.status).toBe('CONFIDENCE_NOT_AVAILABLE')
  })

  it('drivers unavailable preserved', () => {
    expect(normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).drivers.status).toBe('DRIVER_DECOMPOSITION_NOT_AVAILABLE')
  })

  it('model-run comparison unavailable preserved', () => {
    expect(normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE).modelRunComparison.status).toBe('MODEL_RUN_COMPARISON_UNAVAILABLE')
  })

  it('FMD model-not-ready stays distinct from LSD evaluation-not-available', () => {
    const fmdRaw = { ...REAL_LSD_RESPONSE, disease: 'FMD', model_evaluation: { status: 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY' } }
    const lsd = normalizeAnalysisTrendsContext(REAL_LSD_RESPONSE)
    const fmd = normalizeAnalysisTrendsContext(fmdRaw)
    expect(fmd.modelEvaluation.status).not.toBe(lsd.modelEvaluation.status)
    expect(fmd.modelEvaluation.status).toBe('ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY')
  })
})

describe('GEO-ANALYSIS-02-ADAPTER-05: malformed top-level input', () => {
  it('null input returns null, never throws', () => {
    expect(normalizeAnalysisTrendsContext(null)).toBeNull()
  })

  it('non-object input returns null', () => {
    expect(normalizeAnalysisTrendsContext('not an object')).toBeNull()
  })

  it('missing historical_summary/trend normalize to null, not a crash', () => {
    const raw = { status: 'NO_HISTORICAL_DATA', disease: 'LSD', scope_country: 'Sri Lanka' }
    const normalized = normalizeAnalysisTrendsContext(raw)
    expect(normalized.historicalSummary).toBeNull()
    expect(normalized.historicalTrend).toBeNull()
    expect(normalized.selectedOriginAnalytics).toBeNull()
  })
})
