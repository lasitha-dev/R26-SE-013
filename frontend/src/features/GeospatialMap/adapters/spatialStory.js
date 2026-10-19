/**
 * Pure presentation adapters that turn ONE backend spatial-timeline snapshot
 * (`GET /api/geospatial/spatial-timeline`, contract SPATIAL_TIMELINE_1.0)
 * into the National Map's per-mode layers and its plain-language
 * "situation brief".
 *
 * Honesty contract (same as `spatialTimelineView.js`):
 *  - Risk cells are the backend's OWN scored cells (`cells[]`: centroid,
 *    `raw_c0_score`, `tier`) drawn at their true footprint: the scientific
 *    grid is a square 5 km grid laid out in degrees at the cell's latitude
 *    (`services/geospatial/grid.py`, SCIENTIFIC_GRID_CELL_SIZE_KM = 5.0).
 *    A cell is "within reach" on day N when its centroid lies inside the
 *    backend's own `frames[N].reach_envelope`. Unscored land is never drawn.
 *  - Reach envelopes and corridors are the backend's frame geometry, passed
 *    through unchanged. Nothing here scores, moves or grows a shape.
 *  - The relative score itself never changes with the day. What changes is
 *    how much of the scored area lies within the nominal-reach distance,
 *    and the copy says exactly that.
 *  - The "attention" prompt is a reading aid derived from the backend tier
 *    and area within reach. It is never an infection forecast or an order.
 */
import { isPointInsideDistrictFeature, normalizeDistrictDisplayName } from './districtGeometry'
import { parseVerificationTime, sriLankaDateKey, sriLankaEndOfDayMs } from './verificationTime'
import { formatDisplayDate } from './forecastDate'
import { HORIZON_STATUS, TIER_ORDER, TIER_TO_RISK_LEVEL, compassPoint, horizonLabel, isTimelineRenderable, plateauStartIndex, shortDateLabel, timelineFrames, clampFrameIndex } from './spatialTimelineView'

const EMPTY = Object.freeze({ type: 'FeatureCollection', features: Object.freeze([]) })

/** Where the analysis date ("as of") comes from. */
export const ANALYSIS_BASIS = Object.freeze({
  LIVE: 'LIVE',
  LATEST_VERIFIED: 'LATEST_VERIFIED',
  RETROSPECTIVE: 'RETROSPECTIVE',
  CUSTOM: 'CUSTOM',
})

/** Display words for the backend's relative tiers (highest relative score -> "High"). */
// Within-snapshot relative quartiles of the C0 score over scored land cells --
// never absolute risk, never a safety level (unscored land is simply not scored).
export const TIER_DISPLAY = Object.freeze({ highest: 'Highest relative', high: 'Elevated relative', moderate: 'Moderate relative', lower: 'Lowest relative' })

/** Map/legend colour per backend tier (red / orange / yellow / green). */
export const TIER_COLOR = Object.freeze({ highest: '#ef4444', high: '#f97316', moderate: '#eab308', lower: '#22c55e' })

function tierRank(tier) {
  return TIER_ORDER.indexOf(tier)
}

function isoDatePart(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : null
}

/** Latest real verification date (YYYY-MM-DD, Asia/Colombo calendar date of
 * the verification instant) among verified clinical contexts for one
 * disease, or null when there is none. */
export function latestVerifiedDate(contexts, disease) {
  let latest = null
  for (const context of Array.isArray(contexts) ? contexts : []) {
    if (disease && context?.disease !== disease) continue
    const date = sriLankaDateKey(context?.verificationTime)
    if (date && (!latest || date > latest)) latest = date
  }
  return latest
}

/** Date (t0) of the real historical origin used for retrospective replay:
 * the origin with the MOST real eligible source records (most informative
 * for a demonstration -- a single source has no direction), latest t0 on a
 * tie. Real data only; null when there is none. */
export function latestHistoricalOriginDate(originsWithSources) {
  let best = null
  for (const origin of Array.isArray(originsWithSources) ? originsWithSources : []) {
    const date = isoDatePart(origin?.t0)
    if (!date) continue
    const count = Number(origin?.sourceCount ?? origin?.sourcesFeatureCollection?.features?.length ?? 0)
    if (!best || count > best.count || (count === best.count && date > best.date)) best = { date, count }
  }
  return best?.date ?? null
}

/** The analysis-date choices the vet can switch between. Only options backed
 * by a real date are offered; LIVE is always offered (backend "today"). */
export function buildAnalysisBasisOptions({ latestVerified = null, retrospective = null, allowCustom = false, customDate = null, today = null } = {}) {
  const options = [
    {
      id: ANALYSIS_BASIS.LIVE,
      label: 'Live (today)',
      shortLabel: 'Live',
      asOf: null,
      description: 'Vet-verified cases and records observed in the 14 days up to today.',
      domain: 'OPERATIONAL_AND_HISTORICAL',
    },
  ]
  if (latestVerified) {
    options.push({
      id: ANALYSIS_BASIS.LATEST_VERIFIED,
      label: `Latest verified · ${formatDisplayDate(latestVerified)}`,
      shortLabel: 'Latest verified',
      asOf: latestVerified,
      description: 'Analysis fixed at the date of the most recent vet-verified case for this disease.',
      domain: 'OPERATIONAL',
    })
  }
  if (retrospective) {
    options.push({
      id: ANALYSIS_BASIS.RETROSPECTIVE,
      label: `Retrospective · ${formatDisplayDate(retrospective)}`,
      shortLabel: 'Retrospective',
      asOf: retrospective,
      description: 'Historical research records (WAHIS) replayed at a past date. Not current activity.',
      domain: 'HISTORICAL',
    })
  }
  if (allowCustom) {
    // Any past Asia/Colombo date the vet picks (never future). Lets a vet in
    // a district without recent own cases review a real retrospective
    // window; the backend alone decides which sources are eligible and
    // returns NO_ELIGIBLE_SOURCES when there is no evidence.
    const date = isoDatePart(customDate) ?? isoDatePart(today)
    options.push({
      id: ANALYSIS_BASIS.CUSTOM,
      label: customDate ? `Chosen date · ${formatDisplayDate(date)}` : 'Choose a date…',
      shortLabel: 'Chosen date',
      asOf: date,
      description: 'Analysis fixed at a date you choose: records observed in the 14 days up to that date.',
      domain: 'OPERATIONAL_AND_HISTORICAL',
    })
  }
  return options
}

/** The backend's operational source window: cases verified in the 14
 * Asia/Colombo days ending at the analysis date (inclusive). */
export const SOURCE_WINDOW_DAYS = 14

/** Analysis date used until the vet picks one: today when a vet-verified
 * case falls inside today's 14-day source window, otherwise the date of the
 * latest real vet-verified case (so the Day 0-14 timeline has real sources).
 * Never a historical-research or invented date. */
export function automaticBasisId({ latestVerified = null, today = null } = {}) {
  const latest = isoDatePart(latestVerified)
  const now = isoDatePart(today)
  if (!latest || !now) return ANALYSIS_BASIS.LIVE
  const ageDays = Math.round((Date.parse(`${now}T00:00:00Z`) - Date.parse(`${latest}T00:00:00Z`)) / 86400000)
  return ageDays <= SOURCE_WINDOW_DAYS - 1 ? ANALYSIS_BASIS.LIVE : ANALYSIS_BASIS.LATEST_VERIFIED
}

export function selectedBasisOption(options, basisId) {
  return options.find((option) => option.id === basisId) ?? options[0]
}

export const SCIENTIFIC_CELL_SIZE_KM = 5
const KM_PER_DEG_LAT = 110.574

/** Square footprint of one scientific cell around its backend centroid. */
export function cellFootprint(lon, lat, sizeKm = SCIENTIFIC_CELL_SIZE_KM) {
  const halfLat = sizeKm / 2 / KM_PER_DEG_LAT
  const halfLon = sizeKm / 2 / (111.32 * Math.cos((lat * Math.PI) / 180))
  return {
    type: 'Polygon',
    coordinates: [[[lon - halfLon, lat - halfLat], [lon + halfLon, lat - halfLat], [lon + halfLon, lat + halfLat], [lon - halfLon, lat + halfLat], [lon - halfLon, lat - halfLat]]],
  }
}

/**
 * The backend's scored cells for the selected day. `inReach` = the cell
 * centroid lies inside that day's backend reach envelope (always false on
 * Day 0, where reach has not started). Only SCORED, in-scope cells appear.
 */
export function buildRiskCells(timeline, index) {
  if (!isTimelineRenderable(timeline)) return EMPTY
  const frame = timelineFrames(timeline)[clampFrameIndex(timeline, index)]
  const envelope = frame?.reach_envelope?.type ? { geometry: frame.reach_envelope } : null
  const cells = Array.isArray(timeline.cells) ? timeline.cells : []
  // The current engine sends every drawable cell's own scope-clipped polygon
  // and `geometry: null` for a cell clipped away entirely -- such a cell is
  // not drawn. Only a legacy snapshot with no cell geometry at all falls
  // back to the 5 km grid footprint.
  const snapshotHasCellGeometry = cells.some((cell) => cell?.geometry?.type)
  const sourcePoints = (Array.isArray(timeline.sources) ? timeline.sources : [])
    .filter((s) => Number.isFinite(s?.longitude) && Number.isFinite(s?.latitude))
    .map((s) => [s.longitude, s.latitude])
  const features = []
  for (const cell of cells) {
    const lon = cell?.centroid?.longitude
    const lat = cell?.centroid?.latitude
    if (!Number.isFinite(lon) || !Number.isFinite(lat) || cell.score_status !== 'SCORED' || cell.in_scope === false) continue
    if (snapshotHasCellGeometry && !cell.geometry?.type) continue
    const riskLevel = TIER_TO_RISK_LEVEL[cell.tier]
    if (!riskLevel) continue
    const geometry = cell.geometry?.type ? cell.geometry : cellFootprint(lon, lat)
    const inReach = Boolean(envelope) && isPointInsideDistrictFeature([lon, lat], envelope)
    // The cell holding a real source case is shown from Day 0 (the current
    // situation); every other cell appears only once that day's backend
    // nominal reach covers it -- so the zone spreads as the timeline plays.
    const isSourceCell = sourcePoints.some((point) => isPointInsideDistrictFeature(point, { geometry }))
    if (!inReach && !isSourceCell) continue
    features.push({
      type: 'Feature',
      // The backend's own domain- and scope-clipped cell polygon (Polygon or
      // MultiPolygon, drawn as sent).
      geometry,
      properties: {
        cellId: cell.cell_id,
        tier: cell.tier,
        tierLabel: TIER_DISPLAY[cell.tier],
        tierRank: tierRank(cell.tier),
        riskLevel,
        score: Number.isFinite(cell.raw_c0_score) ? cell.raw_c0_score : null,
        inReach,
        isSourceCell,
        bearingDeg: Number.isFinite(cell?.direction?.bearing_deg) ? cell.direction.bearing_deg : null,
        day: frame?.day ?? null,
        date: frame?.date ?? null,
        horizonStatus: frame?.horizon_status ?? null,
      },
    })
  }
  features.sort((a, b) => a.properties.tierRank - b.properties.tierRank)
  return { type: 'FeatureCollection', features }
}

/** In-reach cell counts per backend tier for the selected day. */
export function cellTierCounts(riskCells) {
  const counts = { highest: 0, high: 0, moderate: 0, lower: 0, scored: 0 }
  for (const feature of riskCells?.features ?? []) {
    counts.scored += 1
    if (feature.properties.inReach) counts[feature.properties.tier] += 1
  }
  return counts
}

/** Nominal-reach envelopes for every day up to the selected one (isochrone
 * rings). `age` 0 is the selected day; older days fade. */
export function buildReachHistory(timeline, index) {
  if (!isTimelineRenderable(timeline)) return EMPTY
  const frames = timelineFrames(timeline)
  const active = clampFrameIndex(timeline, index)
  const features = []
  for (let i = 1; i <= active; i += 1) {
    const frame = frames[i]
    if (!frame?.reach_envelope?.type) continue
    features.push({
      type: 'Feature',
      geometry: frame.reach_envelope,
      properties: {
        day: frame.day,
        date: frame.date,
        age: active - i,
        isCurrent: i === active,
        exploratory: frame.horizon_status === HORIZON_STATUS.EXPLORATORY,
        nominalReachKm: frame?.reach?.nominal_reach_km ?? null,
        // Backend nominal reach for this day, written on the ring.
        label: Number.isFinite(frame?.reach?.nominal_reach_km) ? `${shortDateLabel(frame.date)} · ${frame.reach.nominal_reach_km.toFixed(1)} km reach` : shortDateLabel(frame.date),
      },
    })
  }
  return { type: 'FeatureCollection', features }
}

/** Per-day nominal reach (km) for the timeline dock, one entry per frame. */
export function reachSeries(timeline) {
  return timelineFrames(timeline).map((frame) => ({
    day: frame.day,
    date: frame.date,
    horizonStatus: frame.horizon_status,
    reachKm: Number.isFinite(frame?.reach?.nominal_reach_km) ? frame.reach.nominal_reach_km : 0,
  }))
}

function ringCentroid(ring) {
  let area = 0
  let cx = 0
  let cy = 0
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [x0, y0] = ring[j]
    const [x1, y1] = ring[i]
    const cross = x0 * y1 - x1 * y0
    area += cross
    cx += (x0 + x1) * cross
    cy += (y0 + y1) * cross
  }
  if (area === 0) return { area: 0, point: ring[0] ?? null }
  return { area: Math.abs(area / 2), point: [cx / (3 * area), cy / (3 * area)] }
}

/** Label anchor for a district polygon: centroid of its largest outer ring. */
export function districtLabelPoint(feature) {
  const geometry = feature?.geometry
  const polygons = geometry?.type === 'Polygon' ? [geometry.coordinates] : geometry?.type === 'MultiPolygon' ? geometry.coordinates : []
  let best = null
  for (const polygon of polygons) {
    const outer = polygon?.[0]
    if (!Array.isArray(outer) || outer.length < 3) continue
    const candidate = ringCentroid(outer)
    if (!best || candidate.area > best.area) best = candidate
  }
  return best?.point ?? null
}

/** True when a verification time falls in the `days`-long window ENDING at
 * `endIsoDate` (inclusive, whole days, UTC). Unlike a "since now" window it
 * EXCLUDES anything verified after the end date, so a past analysis date
 * never shows later cases. */
export function isWithinWindowEndingAt(verificationTime, days, endIsoDate) {
  const parsed = parseVerificationTime(verificationTime)
  if (!parsed || typeof endIsoDate !== 'string') return false
  // The analysis date is an Asia/Colombo calendar date (backend as_of).
  const end = sriLankaEndOfDayMs(endIsoDate)
  if (!Number.isFinite(end)) return false
  const t = parsed.getTime()
  return t <= end && end - t <= days * 24 * 60 * 60 * 1000
}

function sameDistrict(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false
  const norm = (value) => value.trim().toLowerCase().replace(/\s+district$/, '')
  return norm(a) === norm(b)
}

function attentionFor({ myDistrict, topConcern, day, hasSources }) {
  if (!hasSources) {
    return { level: 'NONE', headline: 'No eligible sources for this analysis date', detail: 'Nothing is scored, so no area is highlighted.' }
  }
  if (myDistrict?.name && myDistrict.tierWithinReach) {
    const label = TIER_DISPLAY[myDistrict.tierWithinReach]
    const area = `${Math.round(myDistrict.areaWithinReachKm2)} km²`
    if (myDistrict.tierWithinReach === 'highest' || myDistrict.tierWithinReach === 'high') {
      return {
        level: 'PRIORITISE',
        headline: `Prioritise clinical surveillance in ${myDistrict.name}`,
        detail: `${label} spatial score lies within the Day ${day} nominal reach (${area}). A relative ranking of proximity to source cases, not an infection forecast.`,
      }
    }
    return {
      level: 'MONITOR',
      headline: `Keep ${myDistrict.name} under observation`,
      detail: `${label} spatial score within the Day ${day} nominal reach (${area}).`,
    }
  }
  if (myDistrict?.name && myDistrict.scoredAreaKm2 > 0) {
    return {
      level: 'MONITOR',
      headline: `${myDistrict.name}: scored area lies beyond Day ${day} nominal reach`,
      detail: 'Step forward in the timeline to see when the nominal reach distance covers it.',
    }
  }
  if (myDistrict?.name) {
    return {
      level: 'ROUTINE',
      headline: `No scored area in ${myDistrict.name} for this analysis date`,
      detail: topConcern ? `Main concern is ${topConcern.district} (${TIER_DISPLAY[topConcern.tier]}). Routine surveillance in your district.` : 'Routine surveillance.',
    }
  }
  return topConcern
    ? { level: 'MONITOR', headline: `Main concern: ${topConcern.district}`, detail: `${TIER_DISPLAY[topConcern.tier]} spatial score within the Day ${day} nominal reach.` }
    : { level: 'ROUTINE', headline: 'No scored area within nominal reach yet', detail: 'Day 0 is the as-of context; reach starts on Day 1.' }
}

/**
 * Situation-brief view model for the selected frame. Everything is copied
 * or counted from the backend snapshot; `vetDistrict` only selects which
 * backend district summary to read.
 */
export function buildSpatialStory(timeline, index, { vetDistrict = null } = {}) {
  if (!isTimelineRenderable(timeline)) {
    return { renderable: false, status: timeline?.status ?? null, environment: timeline?.environment ?? null, sourceExclusions: timeline?.source_exclusions ?? null, timeWindow: timeline?.time_window ?? null }
  }
  const frames = timelineFrames(timeline)
  const activeIndex = clampFrameIndex(timeline, index)
  const frame = frames[activeIndex]
  const directions = new Map((timeline.source_directions ?? []).map((d) => [d.source_id, d]))
  const sources = (timeline.sources ?? []).map((source) => {
    const direction = directions.get(source.source_id)
    const bearing = Number.isFinite(direction?.bearing_deg) ? direction.bearing_deg : null
    return {
      sourceId: source.source_id,
      domain: source.record_domain,
      observationDate: source.observation_date ?? null,
      gpsQuality: source.gps_quality ?? null,
      bearingDeg: bearing,
      compass: compassPoint(bearing),
      clarity: Number.isFinite(direction?.directional_clarity) ? direction.directional_clarity : null,
      active: Array.isArray(frame.active_source_ids) ? frame.active_source_ids.includes(source.source_id) : true,
    }
  })
  const domainCounts = sources.reduce(
    (acc, s) => ({ ...acc, [s.domain === 'OPERATIONAL' ? 'operational' : 'historical']: acc[s.domain === 'OPERATIONAL' ? 'operational' : 'historical'] + 1 }),
    { operational: 0, historical: 0 },
  )
  const districtsInReach = (Array.isArray(frame.district_summaries) ? frame.district_summaries : [])
    .filter((d) => d?.highest_tier_within_reach && Number(d.area_within_reach_km2) > 0)
    .map((d) => ({ district: d.district, tier: d.highest_tier_within_reach, riskLevel: TIER_TO_RISK_LEVEL[d.highest_tier_within_reach], areaKm2: Number(d.area_within_reach_km2) }))
    .sort((a, b) => tierRank(b.tier) - tierRank(a.tier) || b.areaKm2 - a.areaKm2)
  const scoredDistricts = (Array.isArray(timeline.district_summaries) ? timeline.district_summaries : [])
    .filter((d) => Number(d?.scored_area_km2) > 0)
    .map((d) => ({ district: d.district, maxTier: d.max_tier ?? null, scoredAreaKm2: Number(d.scored_area_km2), sources: d.n_sources_in_district ?? 0 }))
  const myFrame = vetDistrict ? (frame.district_summaries ?? []).find((d) => sameDistrict(d?.district, vetDistrict)) : null
  const myStatic = vetDistrict ? (timeline.district_summaries ?? []).find((d) => sameDistrict(d?.district, vetDistrict)) : null
  const myDistrict = vetDistrict
    ? {
        name: normalizeDistrictDisplayName(vetDistrict),
        tierWithinReach: Number(myFrame?.area_within_reach_km2) > 0 ? myFrame?.highest_tier_within_reach ?? null : null,
        areaWithinReachKm2: Number(myFrame?.area_within_reach_km2) || 0,
        scoredAreaKm2: Number(myStatic?.scored_area_km2) || 0,
        sourcesInDistrict: myStatic?.n_sources_in_district ?? 0,
      }
    : null
  const topConcern = districtsInReach[0] ?? null
  const reachKm = Number.isFinite(frame?.reach?.nominal_reach_km) ? frame.reach.nominal_reach_km : null
  const interval = Array.isArray(frame?.reach?.interval_km) ? frame.reach.interval_km : null
  const plateau = plateauStartIndex(timeline)
  return {
    renderable: true,
    status: timeline.status,
    asOf: timeline.as_of,
    timeWindow: timeline.time_window ?? null,
    activeIndex,
    frameCount: frames.length,
    day: frame.day,
    date: frame.date,
    horizonStatus: frame.horizon_status,
    horizonLabel: horizonLabel(frame.horizon_status),
    exploratory: frame.horizon_status === HORIZON_STATUS.EXPLORATORY,
    reachKm,
    reachIntervalKm: interval,
    rateKmDay: Number.isFinite(frame?.reach?.rate_km_day) ? frame.reach.rate_km_day : null,
    sources,
    domainCounts,
    districtsInReach,
    scoredDistricts,
    topConcern,
    myDistrict,
    attention: attentionFor({ myDistrict, topConcern, day: frame.day, hasSources: sources.length > 0 }),
    plateauReached: plateau != null && activeIndex >= plateau,
    environment: timeline.environment ?? null,
    model: timeline.model ?? null,
    limitations: Array.isArray(timeline.limitations) ? timeline.limitations : [],
    sourceExclusions: timeline.source_exclusions ?? null,
    scope: timeline.scope ?? null,
  }
}

const FAILURE_REASON = Object.freeze({
  SESSION_REQUIRED: ['Sign-in required', 'Your session is missing or expired, so the spatial timeline was not requested. Sign in again.'],
  FORBIDDEN: ['Not authorised', 'This account is not a veterinarian account, so spatial outputs are not available to it.'],
  DISTRICT_NOT_AUTHORISED: ['District not authorised', 'This district is outside your authorised districts.'],
  NO_AUTHORISED_DISTRICT: ['No authorised district', 'No district is registered on your veterinarian profile.'],
  NETWORK_ERROR: ['Backend unreachable', 'The spatial timeline request did not reach the backend (network or server down). Nothing was computed or shown.'],
  INVALID_RESPONSE: ['Unreadable response', 'The backend answered, but the response was not a spatial timeline snapshot, so nothing is drawn from it.'],
  OPERATIONAL_DATA_UNAVAILABLE: ['Operational data unavailable', 'The backend could not read the operational case data for this request.'],
})

// Backend source-exclusion keys (`services/spatial_timeline/sources.py`,
// prefixed "operational:"/"historical:") -> plain language, most actionable
// first. Other-disease records and merged same-farm duplicates are not
// reasons a source is missing, so they are not listed.
const EXCLUSION_REASON_TEXT = [
  ['MISSING_OR_INVALID_COORDINATES', (n) => `${n} report${n === 1 ? ' has' : 's have'} no farm GPS (set the farm location in ADRS to map ${n === 1 ? 'it' : 'them'})`],
  ['FARM_COORDINATES_OUTSIDE_SRI_LANKA', (n) => `${n} with farm GPS outside Sri Lanka`],
  ['NOT_VET_VERIFIED', (n) => `${n} awaiting vet verification`],
  ['MISSING_OR_UNPARSEABLE_VERIFICATION_DATE', (n) => `${n} without a verification date`],
  ['OUTSIDE_ACTIVE_SOURCE_WINDOW', (n) => `${n} verified before the 14-day window`],
  ['VERIFIED_AFTER_AS_OF_DATE', (n) => `${n} verified after this date`],
  ['BEYOND_MODEL_REACH_OF_DISTRICT', (n) => `${n} too far to reach the district within the forecast`],
]

const NOT_A_MISSING_SOURCE_REASON = ['WRONG_DISEASE', 'MERGED_DUPLICATE_SAME_FARM_SAME_DISEASE', 'DUPLICATE_CASE_RECORD']

/** Plain-language list of why records did not become model sources. */
export function sourceExclusionReasons(exclusions) {
  if (!exclusions || typeof exclusions !== 'object') return []
  const totals = {}
  for (const [key, value] of Object.entries(exclusions)) {
    const reason = String(key).split(':').pop()
    totals[reason] = (totals[reason] ?? 0) + (Number(value) || 0)
  }
  const reasons = EXCLUSION_REASON_TEXT.filter(([reason]) => totals[reason] > 0).map(([reason, text]) => text(totals[reason]))
  // A reason this page does not know yet is still counted, never hidden.
  const known = new Set([...EXCLUSION_REASON_TEXT.map(([reason]) => reason), ...NOT_A_MISSING_SOURCE_REASON])
  const other = Object.entries(totals).filter(([reason]) => !known.has(reason)).reduce((sum, [, n]) => sum + n, 0)
  if (other > 0) reasons.push(`${other} excluded for other reasons`)
  return reasons
}

/** Plain-language reason for a non-renderable snapshot (empty-state copy).
 * A failed request (`fetchState: 'error'`) is reported as a failure with
 * its status -- never as "no eligible sources". */
export function unavailableReason(timeline, { diseaseShortLabel = 'this disease', basis = ANALYSIS_BASIS.LIVE, fetchState = null, errorStatus = null } = {}) {
  if (fetchState === 'error') {
    const [title, body] = FAILURE_REASON[errorStatus] ?? ['Spatial timeline request failed', `The backend returned an error${errorStatus ? ` (${errorStatus})` : ''}; no spatial output is shown.`]
    const authProblem = errorStatus === 'SESSION_REQUIRED' || errorStatus === 'FORBIDDEN' || errorStatus === 'NO_AUTHORISED_DISTRICT'
    return { title, body, canSwitchBasis: !authProblem, failed: true }
  }
  const status = timeline?.status
  if (status === 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY') {
    return {
      title: `No validated spatial model for ${diseaseShortLabel}`,
      body: `${diseaseShortLabel} has no frozen spatial kernel or spread-rate parameters yet, so no risk zones, reach or direction are computed. Verified cases remain available in Cases mode.`,
      canSwitchBasis: false,
    }
  }
  if (status === 'NO_ELIGIBLE_SOURCES') {
    const window = timeline?.time_window
    const span = window?.source_window_start && window?.source_window_end
      ? ` between ${formatDisplayDate(window.source_window_start)} and ${formatDisplayDate(window.source_window_end)}`
      : ''
    const reasons = sourceExclusionReasons(timeline?.source_exclusions)
    return {
      title: `No eligible ${diseaseShortLabel} source cases${basis === ANALYSIS_BASIS.LIVE ? ' in the last 14 days' : ''}`,
      body: `No vet-verified ${diseaseShortLabel} case or research record qualifies as a model source${span}${reasons.length ? `: ${reasons.join('; ')}` : ''}. No risk zones, reach or direction are drawn.`,
      reasons,
      canSwitchBasis: true,
    }
  }
  return { title: 'Spatial analysis unavailable', body: 'The spatial timeline could not be computed for this selection.', canSwitchBasis: true }
}
