/**
 * LSD-UI-01: the one place a disease code is resolved to display/marker
 * config. Mirrors the backend's own single-registry discipline
 * (`services/disease.py::SUPPORTED_DISEASES`) so the frontend never
 * hardcodes a second copy of a disease name/abbreviation to check
 * against.
 *
 * `apiValue` must match `SUPPORTED_DISEASES`'s abbreviation keys exactly
 * (`?disease=lsd`/`?disease=fmd` query params). `ready` reflects the
 * backend's `DISEASE_MODEL_READINESS_10A` reality, confirmed live against
 * the running API (2026-08-27): LSD analysis endpoints return real data
 * for Sri Lanka; FMD analysis endpoints return
 * `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY` (HTTP 409) for every
 * origin, because the FMD model pipeline has not reached its own
 * Checkpoint 09 API-integration stage yet (see FMD07B_MODEL_DEVELOPMENT_PROTOCOL.md).
 * `ready: false` here is a data-availability fact, not a frontend
 * restriction to lift casually -- flip it only after confirming
 * `DISEASE_MODEL_READINESS_10A` on the backend actually includes FMD.
 */

export const DISEASE_CODE = {
  LSD: 'LSD',
  FMD: 'FMD',
}

/**
 * FMD-10C: fine-grained capability flags, checked with `hasCapability()`
 * below -- never inferred from the coarse `ready` flag. `ready` still
 * means exactly what it always meant (the full LSD-shaped spatial
 * snapshot -- summary/cells/sources/direction/rate/reach -- is API-ready
 * for this disease) and stays `false` for FMD; flipping it to `true`
 * would wrongly imply FMD has cells/direction/rate/reach too, which it
 * does not (`FMD_RUNTIME_LIMITATIONS_9` on the backend). FMD's real,
 * live capabilities (confirmed against the running backend, 2026-08-28:
 * `GET /api/geospatial/origins?disease=fmd` returns real Sri Lanka
 * origins; `GET /api/geospatial/analysis/{id}/fmd-risk` returns a real
 * scalar `risk_score`; `GET /api/geospatial/analysis/{id}/sources
 * ?disease=fmd` still 409s `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY`)
 * are expressed here instead, one flag per concern, so a component can
 * ask "can I show a scalar FMD risk score" without that also unlocking
 * "can I show a spatial cell grid".
 */
const CAPABILITY = {
  // Real `/origins` ledger listing (metadata only -- no geometry).
  HISTORICAL_ORIGINS: 'historicalOrigins',
  // Real single origin-level scalar score (`/analysis/{id}/fmd-risk`).
  SCALAR_ORIGIN_RISK: 'scalarOriginRisk',
  // Some real analysis exists over historical data for a selected origin
  // (LSD: the full snapshot; FMD: the scalar risk score) -- NOT the same
  // thing as `spatialCells` (a per-cell grid), see module docstring.
  ANALYSIS_HISTORICAL: 'analysisHistorical',
  // LSD-shaped per-cell C0 spatial grid (`/analysis/{id}/cells`, and by
  // extension `/summary`+`/sources`, which share the same
  // `DISEASE_MODEL_READINESS_10A` backend gate).
  SPATIAL_CELLS: 'spatialCells',
  // Map "Risk Zones" mode (the nominal-reach ring), which depends on
  // `nominalReach` + real source geometry from `spatialCells`.
  RISK_ZONES: 'riskZones',
  TRAJECTORY: 'trajectory',
  DIRECTION: 'direction',
  APPARENT_RATE: 'apparentRate',
  NOMINAL_REACH: 'nominalReach',
  ENVIRONMENTAL_VECTORS: 'environmentalVectors',
  FORECAST_FRAMES: 'forecastFrames',
}

export const DISEASE_REGISTRY = {
  [DISEASE_CODE.LSD]: {
    code: DISEASE_CODE.LSD,
    apiValue: 'lsd',
    label: 'Lumpy Skin Disease',
    shortLabel: 'LSD',
    markerShape: 'diamond',
    ready: true,
    capabilities: {
      [CAPABILITY.HISTORICAL_ORIGINS]: true,
      [CAPABILITY.SCALAR_ORIGIN_RISK]: false,
      [CAPABILITY.ANALYSIS_HISTORICAL]: true,
      [CAPABILITY.SPATIAL_CELLS]: true,
      [CAPABILITY.RISK_ZONES]: true,
      [CAPABILITY.TRAJECTORY]: false,
      [CAPABILITY.DIRECTION]: true,
      [CAPABILITY.APPARENT_RATE]: true,
      [CAPABILITY.NOMINAL_REACH]: true,
      [CAPABILITY.ENVIRONMENTAL_VECTORS]: false,
      [CAPABILITY.FORECAST_FRAMES]: true,
    },
  },
  [DISEASE_CODE.FMD]: {
    code: DISEASE_CODE.FMD,
    apiValue: 'fmd',
    label: 'Foot-and-Mouth Disease',
    shortLabel: 'FMD',
    markerShape: 'circle',
    ready: false,
    capabilities: {
      [CAPABILITY.HISTORICAL_ORIGINS]: true,
      [CAPABILITY.SCALAR_ORIGIN_RISK]: true,
      [CAPABILITY.ANALYSIS_HISTORICAL]: true,
      [CAPABILITY.SPATIAL_CELLS]: false,
      [CAPABILITY.RISK_ZONES]: false,
      [CAPABILITY.TRAJECTORY]: false,
      [CAPABILITY.DIRECTION]: false,
      [CAPABILITY.APPARENT_RATE]: false,
      [CAPABILITY.NOMINAL_REACH]: false,
      [CAPABILITY.ENVIRONMENTAL_VECTORS]: false,
      [CAPABILITY.FORECAST_FRAMES]: false,
    },
  },
}

export const DEFAULT_DISEASE_CODE = DISEASE_CODE.LSD

export function getDiseaseConfig(code) {
  const config = DISEASE_REGISTRY[code]
  if (!config) {
    throw new Error(`unknown disease code: ${code} -- supported: ${Object.keys(DISEASE_REGISTRY).join(', ')}`)
  }
  return config
}

export function isDiseaseReady(code) {
  return Boolean(DISEASE_REGISTRY[code]?.ready)
}

/** The one place a component checks a single, named capability rather
 * than the coarse `ready` flag -- see `CAPABILITY`/module docstring
 * above for why the two are not interchangeable. Exported `CAPABILITY`
 * so callers reference the same string constants this registry uses,
 * never a hand-typed capability name that could silently typo/drift. */
export function hasCapability(code, capability) {
  return Boolean(DISEASE_REGISTRY[code]?.capabilities?.[capability])
}

export { CAPABILITY }

export function listDiseaseCodes() {
  return Object.keys(DISEASE_REGISTRY)
}
