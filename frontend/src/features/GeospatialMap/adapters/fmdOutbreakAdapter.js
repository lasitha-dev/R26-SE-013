/**
 * FMD-10C: plug point for the FMD adapter, matching
 * `lsdOutbreakAdapter.js`'s exact function shapes so callers never
 * branch on disease. Confirmed live against the backend (2026-08-28):
 * `GET /api/geospatial/analysis/{id}/summary?disease=fmd` (and `/cells`,
 * `/sources`) still return `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY`
 * (HTTP 409) for every origin -- `DISEASE_MODEL_READINESS_10A` still has
 * no FMD entry, so every function below except
 * `mapOriginsToOutbreakSummaries` still intentionally throws rather than
 * returning fabricated/empty data.
 *
 * `mapOriginsToOutbreakSummaries` is the one exception (FMD-10C):
 * `GET /api/geospatial/origins?disease=fmd` is a REAL, live endpoint --
 * 16 real Sri Lanka FMD forecast origins, metadata-only, same response
 * shape as LSD's (`forecast_origin_id`/`country`/`t0`/
 * `trigger_source_count`). This mirrors `useDiseaseOriginLedger.js`'s
 * own already-proven read of the identical endpoint for Page 3.
 */

export class FmdModelNotReadyError extends Error {
  constructor() {
    super('FMD analysis is not API-ready yet (DISEASE_MODEL_READINESS_10A has no FMD entry) -- see FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md')
    this.name = 'FmdModelNotReadyError'
  }
}

/** `GET /origins` response items -> the same display-ready outbreak
 * summary shape `lsdOutbreakAdapter.js` produces -- real metadata only,
 * no geometry (FMD has no coordinate-bearing endpoint yet; callers must
 * treat `sourcesFeatureCollection` as unavailable for FMD, never fetch
 * it from `/analysis/{id}/sources`, which still 409s). */
export function mapOriginsToOutbreakSummaries(originsResponse) {
  return (originsResponse.origins ?? []).map((origin) => ({
    outbreakId: origin.forecast_origin_id,
    country: origin.country,
    t0: origin.t0,
    sourceCount: origin.trigger_source_count,
  }))
}

export function getAvailableForecastDays() {
  throw new FmdModelNotReadyError()
}

export function buildForecastFrame() {
  throw new FmdModelNotReadyError()
}

export function computeRelevantOrigins() {
  throw new FmdModelNotReadyError()
}
