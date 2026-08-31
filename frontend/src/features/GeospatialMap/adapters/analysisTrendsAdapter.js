/**
 * GEO-ANALYSIS-02 Section 7: deterministic normalizer for the real
 * `GET /api/geospatial/analysis-trends` response
 * (`AnalysisTrendsContext.as_dict()`, GEO-ANALYSIS-01/01H, verified
 * read-only). Converts the backend's snake_case field names to
 * camelCase, validates every numeric value, and rejects malformed data
 * defensively -- NaN/Infinity/negative counts/non-integer counts never
 * reach a UI component; a rejected value becomes `null` (honestly
 * unavailable), never a fabricated `0`.
 */

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

function isFiniteNonNegativeInt(value) {
  return isFiniteNumber(value) && Number.isInteger(value) && value >= 0
}

function str(value) {
  return typeof value === 'string' ? value : null
}

function normalizeTrendPoint(raw) {
  if (!raw || typeof raw !== 'object') return null
  if (typeof raw.period !== 'string') return null
  if (!isFiniteNonNegativeInt(raw.count)) return null
  return { period: raw.period, count: raw.count, countBasis: str(raw.count_basis) }
}

function normalizeHistoricalSummary(raw) {
  if (!raw || typeof raw !== 'object') return null
  return {
    status: str(raw.status),
    historicalSourceCount: isFiniteNonNegativeInt(raw.historical_source_count) ? raw.historical_source_count : null,
    forecastOriginCount: isFiniteNonNegativeInt(raw.forecast_origin_count) ? raw.forecast_origin_count : null,
    firstObservedDate: str(raw.first_observed_date),
    lastObservedDate: str(raw.last_observed_date),
    countBasis: str(raw.count_basis),
  }
}

function normalizeHistoricalTrend(raw) {
  if (!raw || typeof raw !== 'object') return null
  const points = Array.isArray(raw.points) ? raw.points.map(normalizeTrendPoint).filter(Boolean) : []
  return { status: str(raw.status), periodBasis: str(raw.period_basis), points }
}

function normalizeApparentRate(raw) {
  if (!raw || typeof raw !== 'object') return null
  return {
    status: str(raw.status),
    apparentRateKmDay: isFiniteNumber(raw.apparent_rate_km_day) ? raw.apparent_rate_km_day : null,
    context: raw.context && typeof raw.context === 'object' ? raw.context : null,
  }
}

function normalizeDirectionContext(raw) {
  if (!raw || typeof raw !== 'object') return null
  return { status: str(raw.status), reason: str(raw.reason) }
}

function normalizeNominalReachDay(raw) {
  if (!raw || typeof raw !== 'object') return null
  // D1-D7 only -- a malformed or D0 entry is dropped, never coerced.
  if (!Number.isInteger(raw.day) || raw.day < 1) return null
  return {
    day: raw.day,
    nominalReachKm: isFiniteNumber(raw.nominal_reach_km) ? raw.nominal_reach_km : null,
    derivedIntervalLowerKm: isFiniteNumber(raw.derived_interval_lower_km) ? raw.derived_interval_lower_km : null,
    derivedIntervalUpperKm: isFiniteNumber(raw.derived_interval_upper_km) ? raw.derived_interval_upper_km : null,
  }
}

function normalizeNominalReach(raw) {
  if (!raw || typeof raw !== 'object') return null
  const days = Array.isArray(raw.days) ? raw.days.map(normalizeNominalReachDay).filter(Boolean) : []
  return { status: str(raw.status), disclaimer: str(raw.disclaimer), days }
}

function normalizeRssDistribution(raw) {
  if (!raw || typeof raw !== 'object') return null
  return {
    status: str(raw.status),
    label: str(raw.label),
    temporalBasis: str(raw.temporal_basis),
    minScore: isFiniteNumber(raw.min_score) ? raw.min_score : null,
    medianScore: isFiniteNumber(raw.median_score) ? raw.median_score : null,
    maxScore: isFiniteNumber(raw.max_score) ? raw.max_score : null,
    nCellsScored: isFiniteNonNegativeInt(raw.n_cells_scored) ? raw.n_cells_scored : null,
    crossSnapshotComparisonStatus: str(raw.cross_snapshot_comparison_status),
  }
}

function normalizeSelectedOriginAnalytics(raw) {
  if (!raw || typeof raw !== 'object') return null
  return {
    status: str(raw.status),
    originId: str(raw.origin_id),
    disease: str(raw.disease),
    t0: str(raw.t0),
    scientificMode: str(raw.scientific_mode),
    eligibleSourceCount: isFiniteNonNegativeInt(raw.eligible_source_count) ? raw.eligible_source_count : null,
    apparentRate: normalizeApparentRate(raw.apparent_rate),
    directionContext: normalizeDirectionContext(raw.direction_context),
    nominalReach: normalizeNominalReach(raw.nominal_reach),
    relativeSpatialScoreDistribution: normalizeRssDistribution(raw.relative_spatial_score_distribution),
    areaScoreAvailability: str(raw.area_score_availability),
  }
}

function normalizeStatusOnlyBlock(raw) {
  if (!raw || typeof raw !== 'object') return null
  return { status: str(raw.status) }
}

/**
 * Top-level normalizer. `raw` is the exact JSON body of a 200 response
 * (or the parsed body of a structured 404/422/500 the caller chose to
 * surface anyway). Returns `null` for a completely malformed input --
 * never a half-built object with guessed fields.
 */
export function normalizeAnalysisTrendsContext(raw) {
  if (!raw || typeof raw !== 'object') return null
  return {
    status: str(raw.status),
    disease: str(raw.disease),
    scopeCountry: str(raw.scope_country),
    historicalSummary: normalizeHistoricalSummary(raw.historical_summary),
    historicalTrend: normalizeHistoricalTrend(raw.historical_trend),
    selectedOriginAnalytics: normalizeSelectedOriginAnalytics(raw.selected_origin_analytics),
    modelEvaluation: normalizeStatusOnlyBlock(raw.model_evaluation),
    modelRunComparison: normalizeStatusOnlyBlock(raw.model_run_comparison),
    confidence: normalizeStatusOnlyBlock(raw.confidence),
    drivers: normalizeStatusOnlyBlock(raw.drivers),
    generatedAt: str(raw.generated_at),
  }
}
