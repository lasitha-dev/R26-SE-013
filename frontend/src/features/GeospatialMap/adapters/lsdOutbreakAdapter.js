/**
 * LSD-UI-02: maps the real `geospatial_tracking` API response shapes
 * (verified against the live backend, 2026-08-27, e.g.
 * `GET /api/geospatial/origins?disease=lsd&country=Sri%20Lanka`) to this
 * feature's `ForecastFrame`/outbreak-summary shapes (plan Section D/E).
 *
 * Field names below are load-bearing and copied verbatim from real
 * responses, not guessed:
 *  - origins: { forecast_origin_id, country, t0, trigger_source_count }
 *  - summary: { analysis_metadata, n_eligible_sources,
 *               apparent_rate_context, nominal_reach_by_day: [
 *                 { day, nominal_reach_km, derived_interval_lower_km,
 *                   derived_interval_upper_km } ], snapshot_id,
 *               generated_at_utc }
 *  - sources / cells: GeoJSON FeatureCollection, [lon,lat], EPSG:4326
 *
 * There is no per-outbreak "outbreakId" separate from the origin in the
 * real backend (plan Gap: "no sub-origin outbreak id exists") -- the
 * forecast_origin_id IS the addressable outbreak unit for this slice.
 */

import { addDaysToIsoDate, forecastDayLabel } from './forecastDate'
import { isPointInPolygonRing } from './geo'

/** `GET /origins` response items -> a display-ready outbreak summary
 * list for Page 1's national view / origin picker. */
export function mapOriginsToOutbreakSummaries(originsResponse) {
  return (originsResponse.origins ?? []).map((origin) => ({
    outbreakId: origin.forecast_origin_id,
    country: origin.country,
    t0: origin.t0,
    sourceCount: origin.trigger_source_count,
  }))
}

/** Real day 1..7 from `nominal_reach_by_day`, plus 0 (observed/current)
 * -- never a hardcoded 14/15. An origin with an empty/missing table
 * (e.g. `ANALYSIS_UNAVAILABLE_*`) still gets day 0 alone. */
export function getAvailableForecastDays(summary) {
  const days = (summary?.nominal_reach_by_day ?? []).map((entry) => entry.day)
  return [0, ...days]
}

function findNominalReach(summary, dayIndex) {
  if (dayIndex === 0) return null
  return (summary.nominal_reach_by_day ?? []).find((entry) => entry.day === dayIndex) ?? null
}

/**
 * Builds the single authoritative `ForecastFrame` for one outbreak/day
 * (plan Section D). `sources`/`cells` are the real GeoJSON
 * FeatureCollections already fetched for this outbreak -- they do not
 * vary by `dayIndex` (the backend has no day-varying risk surface yet,
 * plan Section O), so the same collections are reused across every
 * frame for this outbreak; only `nominalReachKm` changes per day.
 * Every field with no real backend counterpart is explicit `null`,
 * never fabricated (plan Section D's `ForecastFrame` contract).
 */
export function buildForecastFrame({ summary, sources, cells, dayIndex }) {
  const meta = summary.analysis_metadata
  const reach = findNominalReach(summary, dayIndex)

  return {
    outbreakId: meta.forecast_origin_id,
    disease: 'LSD',
    modelRunId: summary.snapshot_id,
    dayIndex,
    dayLabel: forecastDayLabel(dayIndex),
    actualDate: addDaysToIsoDate(meta.t0, dayIndex),
    status: dayIndex === 0 ? 'observed' : 'forecast',
    confirmedMarkers: sources,
    clusterBoundaries: null,
    riskSurface: cells,
    riskZones: null,
    predictedHotspots: null,
    trajectory: null,
    uncertainty: null,
    nominalReachKm: reach ? reach.nominal_reach_km : 0,
    nominalReachIntervalKm: reach
      ? { lower: reach.derived_interval_lower_km, upper: reach.derived_interval_upper_km }
      : null,
    arrivalWindow: null,
    confidence: null,
    aiExplanation: null,
    recommendedActions: null,
  }
}

const RELEVANCE_REASON = {
  INSIDE_AREA: 'SOURCE_INSIDE_ASSIGNED_AREA',
}

/**
 * Plan Section E's relevance rule (corrected per Section Q after
 * `visualLayerStructural.test.js` flagged a client-side earth-distance
 * helper as forbidden scientific recomputation -- see `geo.js`'s header
 * comment): an origin is "relevant" to the vet's area if any of its
 * real source points fall inside the area polygon. A "within N km of
 * the boundary" test is NOT implemented here -- it would need either a
 * real backend endpoint or a server-computed buffer polygon, since this
 * project's hard rule is that real-world distance computation belongs
 * to the backend's own WGS84 math (`pyproj`), never a frontend
 * approximation. Returns only origins with at least one relevant
 * source, each annotated with *why* -- never a fabricated attribution
 * percentage (plan Section 25).
 *
 * `areaPolygonRing` is a single [lon,lat] ring (GeoJSON Polygon
 * coordinates[0]); `originsWithSources` is
 * `[{ outbreakId, country, t0, sourcesFeatureCollection }]`.
 */
export function computeRelevantOrigins(originsWithSources, areaPolygonRing) {
  if (!areaPolygonRing || areaPolygonRing.length < 3) return []

  const relevant = []
  for (const origin of originsWithSources) {
    const features = origin.sourcesFeatureCollection?.features ?? []
    const isRelevant = features.some((feature) => isPointInPolygonRing(feature.geometry.coordinates, areaPolygonRing))
    if (isRelevant) {
      relevant.push({ outbreakId: origin.outbreakId, reason: RELEVANCE_REASON.INSIDE_AREA })
    }
  }
  return relevant
}

export { RELEVANCE_REASON }
