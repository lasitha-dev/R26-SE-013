/**
 * Pure view-model adapters over ONE backend spatial-timeline snapshot
 * (`GET /api/geospatial/spatial-timeline`, contract SPATIAL_TIMELINE_1.0).
 *
 * Presentation contract (what the maps may and may not imply):
 *  - Risk zones are the backend's STATIC relative-score tiers (C0 quartiles
 *    at the as-of date). They are identical on every day and are drawn as
 *    such -- the map never shows coloured area growing over the days.
 *  - Day-dependent display comes from the nominal-reach OUTLINE and its
 *    backend scored-land intersections. The C0 scores never change by day.
 *  - Direction is a static C0-gradient tendency at each source. By default
 *    it is a short indicator (the backend's own Day-1 corridor geometry);
 *    the full reach-length corridors are research-inspection only.
 *
 * Nothing here scores, moves, grows or invents anything. Every geometry is
 * the backend's own GeoJSON passed through unchanged; every date, reach,
 * bearing, tier and area is copied from the selected backend frame. The
 * adapters only (a) pick the selected frame, (b) map backend tiers onto the
 * existing map/legend colour keys, and (c) shape the data into the objects
 * the existing canvases and panels already render.
 */

import { isPointInsideDistrictFeature } from './districtGeometry'
import { clipLineToDomain } from './clipLineToDomain'

export const TIMELINE_STATUS = Object.freeze({
  OK: 'OK',
  NO_ELIGIBLE_SOURCES: 'NO_ELIGIBLE_SOURCES',
  MODEL_NOT_READY: 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY',
  NO_GRID: 'ANALYSIS_UNAVAILABLE_GRID',
})

export const HORIZON_STATUS = Object.freeze({
  AS_OF: 'AS_OF_OBSERVED_CONTEXT',
  EVALUATED: 'WITHIN_D1_D7_REACH_HORIZON',
  EXPLORATORY: 'EXPLORATORY_BEYOND_D7_REACH_HORIZON',
})

export const TIER_ORDER = Object.freeze(['lower', 'moderate', 'high', 'highest'])

/** Backend tier -> the existing map colour keys (`PAGE1_RISK_TIER`/`AREA_RISK_COLORS`). */
export const TIER_TO_RISK_LEVEL = Object.freeze({ lower: 'green', moderate: 'yellow', high: 'orange', highest: 'red' })

/** Backend tier -> the existing My Area qualitative words (chart/panel/strip). */
export const TIER_TO_DISTRICT_RISK = Object.freeze({ lower: 'low', moderate: 'moderate', high: 'elevated', highest: 'high' })

const EMPTY = Object.freeze({ type: 'FeatureCollection', features: Object.freeze([]) })
// My Area draws its visible surface with the animated risk field; the zone
// polygons stay (transparent) for the click popup.
const MY_AREA_ZONE_HIT_OPACITY = 0
const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

export function horizonLabel(horizonStatus) {
  if (horizonStatus === HORIZON_STATUS.AS_OF) return 'As-of context (Day 0)'
  if (horizonStatus === HORIZON_STATUS.EVALUATED) return 'Day 1–7 nominal-reach horizon'
  if (horizonStatus === HORIZON_STATUS.EXPLORATORY) return 'Exploratory extension (Day 8–14)'
  return 'Horizon unavailable'
}

export function timelineFrames(timeline) {
  return Array.isArray(timeline?.frames) ? timeline.frames : []
}

/** Only a snapshot the backend computed (status OK) drives timeline layers. */
export function isTimelineRenderable(timeline) {
  return timeline?.status === TIMELINE_STATUS.OK && timelineFrames(timeline).length > 0
}

export function clampFrameIndex(timeline, index) {
  const last = Math.max(0, timelineFrames(timeline).length - 1)
  return Math.max(0, Math.min(last, Number.isInteger(index) ? index : 0))
}

export function frameDates(timeline) {
  return timelineFrames(timeline).map((frame) => frame.date)
}

export function compassPoint(bearingDeg) {
  if (!Number.isFinite(bearingDeg)) return null
  return COMPASS[Math.round((((bearingDeg % 360) + 360) % 360) / 45) % 8]
}

function tierRank(tier) {
  const rank = TIER_ORDER.indexOf(tier)
  return rank === -1 ? -1 : rank
}

function tierFeatures(collection, extraProperties) {
  const features = Array.isArray(collection?.features) ? collection.features : []
  return features
    .filter((feature) => feature?.geometry && TIER_TO_RISK_LEVEL[feature?.properties?.tier])
    .slice()
    .sort((a, b) => tierRank(a.properties.tier) - tierRank(b.properties.tier))
    .map((feature) => {
      const riskLevel = TIER_TO_RISK_LEVEL[feature.properties.tier]
      return {
        type: 'Feature',
        geometry: feature.geometry,
        properties: { ...feature.properties, riskLevel, ...extraProperties(riskLevel, feature.properties) },
      }
    })
}

/** source_id -> stable anchor id used to link map features, markers and cards.
 * An operational source links to its first verified case id (the id the red
 * case marker already uses); a historical source uses its own source id. */
export function anchorIdForSource(source) {
  if (source?.record_domain === 'OPERATIONAL' && Array.isArray(source.member_record_ids) && source.member_record_ids.length > 0) {
    return String(source.member_record_ids[0])
  }
  return source?.source_id ?? null
}

/**
 * First frame index from which every later frame's reach-limited zones are
 * geometrically identical (the nominal reach has passed the 25 km scored
 * buffer, so nothing more can be revealed). Derived from the backend
 * geometry itself, never assumed; `null` when there is no plateau.
 */
export function plateauStartIndex(timeline) {
  const frames = timelineFrames(timeline)
  if (!isTimelineRenderable(timeline) || frames.length < 3) return null
  const signature = (frame) => JSON.stringify((frame?.reach_limited_risk_zones?.features ?? []).map((f) => [f?.properties?.tier ?? null, f?.geometry ?? null]))
  const last = signature(frames.at(-1))
  let start = frames.length - 1
  while (start > 1 && signature(frames[start - 1]) === last) start -= 1
  return start < frames.length - 1 ? start : null
}

/** Plain-language note for the selected frame once the risk-zone geometry
 * has stopped changing, or null. It describes the ZONES only: the nominal
 * reach itself (and the land area inside it) can keep growing after this. */
export function plateauNote(timeline, index) {
  const start = plateauStartIndex(timeline)
  if (start == null || clampFrameIndex(timeline, index) < start) return null
  const day = timelineFrames(timeline)[start]?.day ?? start
  return `Reach covers scored area from Day ${day}`
}

/** First outlook row from which every later row has the same district area
 * within reach and the same tier (the chart's own plateau, independent of the
 * zone plateau); `null` when the area is still changing at the last frame. */
export function areaPlateauStartIndex(rows) {
  if (!Array.isArray(rows) || rows.length < 3) return null
  const last = rows.at(-1)
  const same = (row) => row.areaKm2 === last.areaKm2 && row.tier === last.tier
  let start = rows.length - 1
  while (start > 1 && same(rows[start - 1])) start -= 1
  return start < rows.length - 1 && last.areaKm2 > 0 ? start : null
}

function sourceIndex(timeline) {
  return new Map((Array.isArray(timeline?.sources) ? timeline.sources : []).map((source) => [source.source_id, source]))
}

function lastCoordinate(geometry) {
  if (!geometry) return null
  if (geometry.type === 'LineString') return geometry.coordinates.at(-1) ?? null
  if (geometry.type === 'MultiLineString') return geometry.coordinates.at(-1)?.at(-1) ?? null
  return null
}

/** Presentation guard only: reject an indicator that leaves the real land
 * polygons. Never rotate, bend or manufacture an inland alternative. */
export function directionGeometryInDomain(geometry, landDomain) {
  if (landDomain === undefined) return true
  const districts = landDomain?.type === 'FeatureCollection' ? landDomain.features : landDomain ? [landDomain] : []
  const lines = geometry?.type === 'LineString' ? [geometry.coordinates] : geometry?.type === 'MultiLineString' ? geometry.coordinates : []
  if (!districts.length || !lines.length) return false
  const onLand = (point) => Array.isArray(point) && point.every(Number.isFinite) && districts.some((feature) => isPointInsideDistrictFeature(point, feature))
  return lines.every((line) => Array.isArray(line) && line.length > 1 && line.every(onLand) && line.slice(1).every((point, i) => [0.25, 0.5, 0.75].every((t) => onLand([line[i][0] + (point[0] - line[i][0]) * t, line[i][1] + (point[1] - line[i][1]) * t]))))
}

function corridorCollections(timeline, frame, geometryBySource = null, landDomain) {
  const sources = sourceIndex(timeline)
  const paths = []
  const fronts = []
  const interval = Array.isArray(frame?.reach?.interval_km) ? frame.reach.interval_km : []
  for (const corridor of Array.isArray(frame?.source_corridors) ? frame.source_corridors : []) {
    if (!corridor?.geometry || !Number.isFinite(corridor.bearing_deg)) continue
    const indicator = geometryBySource?.get(corridor.source_id)
    const geometry = clipLineToDomain(geometryBySource ? indicator?.geometry : corridor.geometry, landDomain)
    if (!geometry) continue
    const source = sources.get(corridor.source_id)
    const properties = {
      sourceId: corridor.source_id,
      anchorId: anchorIdForSource(source) ?? corridor.source_id,
      recordDomain: source?.record_domain ?? null,
      disease: source?.disease ?? timeline?.disease ?? null,
      observationDate: source?.observation_date ?? null,
      bearingDeg: corridor.bearing_deg,
      // Popups describe the day's nominal reach; the drawn arrow is capped at the
      // 25 km direction domain by the backend (length_km), reported separately.
      lengthKm: Number.isFinite(corridor.nominal_reach_km) ? corridor.nominal_reach_km : corridor.length_km,
      arrowLengthKm: geometryBySource ? indicator.length_km : corridor.length_km,
      reachLowKm: Number.isFinite(interval[0]) ? interval[0] : null,
      reachHighKm: Number.isFinite(interval[1]) ? interval[1] : null,
      horizonStatus: frame.horizon_status,
      day: frame.day,
      date: frame.date,
      semantics: corridor.semantics,
    }
    paths.push({ type: 'Feature', geometry, properties: { ...properties, visualizationFeatureId: `${corridor.source_id}:corridor` } })
    const end = lastCoordinate(geometry)
    if (end) {
      fronts.push({ type: 'Feature', geometry: { type: 'Point', coordinates: end }, properties: { ...properties, visualizationFeatureId: `${corridor.source_id}:front` } })
    }
  }
  return { paths: { type: 'FeatureCollection', features: paths }, fronts: { type: 'FeatureCollection', features: fronts } }
}

/** One point per backend source at its own coordinates, with its direction
 * status, so every corridor visibly starts at a marked origin and a source
 * whose direction is indeterminate is still shown (with no arrow). */
export function buildTimelineOrigins(timeline, frame) {
  if (!isTimelineRenderable(timeline)) return EMPTY
  const directions = new Map((timeline.source_directions ?? []).map((direction) => [direction.source_id, direction]))
  // Engine 3.0: cases the model gives no individual path, and why.
  const withoutPath = new Map((timeline.sources_without_path ?? []).map((entry) => [entry.source_id, entry]))
  const reach = frame?.reach?.nominal_reach_km
  const features = (timeline.sources ?? [])
    .filter((source) => Number.isFinite(source?.longitude) && Number.isFinite(source?.latitude))
    .map((source) => {
      const direction = directions.get(source.source_id)
      const bearing = Number.isFinite(direction?.bearing_deg) ? direction.bearing_deg : null
      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [source.longitude, source.latitude] },
        properties: {
          sourceId: source.source_id,
          anchorId: anchorIdForSource(source) ?? source.source_id,
          recordDomain: source.record_domain ?? null,
          disease: source.disease ?? timeline.disease ?? null,
          observationDate: source.observation_date ?? null,
          bearingDeg: bearing,
          directionStatus: bearing == null ? 'NO_DIRECTIONAL_TENDENCY' : 'GEOMETRIC_TENDENCY_AVAILABLE',
          lengthKm: Number.isFinite(reach) ? reach : null,
          reachLowKm: Number.isFinite(frame?.reach?.interval_km?.[0]) ? frame.reach.interval_km[0] : null,
          reachHighKm: Number.isFinite(frame?.reach?.interval_km?.[1]) ? frame.reach.interval_km[1] : null,
          noPathReason: withoutPath.get(source.source_id)?.reason ?? null,
          casesWithin25Km: withoutPath.get(source.source_id)?.origin_basis?.cases_within_25km ?? null,
          horizonStatus: frame?.horizon_status ?? null,
          day: frame?.day ?? null,
          date: frame?.date ?? null,
          isOrigin: true,
        },
      }
    })
  return { type: 'FeatureCollection', features }
}

/** The backend's Day-1 corridor geometry per source: the shortest backend
 * corridor (one day of nominal reach), used unchanged as a static direction
 * indicator so the drawn line never grows with the selected day. */

/** Direction layers for the selected frame. Default: static short
 * indicators. `research`: the backend's full reach-length corridors. The
 * properties (bearing, reach, dates) come from the selected frame; on Day 0
 * (no corridors) the Day-1 frame supplies the bearing and the reach fields
 * are left empty. */
const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** '2026-09-07' -> '7 Sep' (map labels use the real date, never "Day N"). */
export function shortDateLabel(isoDate) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(isoDate ?? ''))
  return match ? `${Number(match[3])} ${SHORT_MONTHS[Number(match[2]) - 1]}` : null
}

/** Adds the on-map text "Day 7 · 25 km" to each line: the frame day and the
 * DRAWN backend corridor length (capped at the 25 km direction domain), never
 * the longer nominal reach, so the number always matches the line. */
function withPathLabels(collections) {
  const label = (fc) => ({
    ...fc,
    features: fc.features.map((f) => {
      const day = Number.isInteger(f.properties?.day) ? `Day ${f.properties.day}` : shortDateLabel(f.properties?.date)
      const drawn = Number.isFinite(f.properties?.arrowLengthKm) ? f.properties.arrowLengthKm : f.properties?.lengthKm
      const km = Number.isFinite(drawn) ? `${Math.round(drawn)} km` : null
      return { ...f, properties: { ...f.properties, pathLabel: [day, km].filter(Boolean).join(' · ') || null } }
    }),
  })
  return { paths: label(collections.paths), fronts: collections.fronts }
}

function directionCollections(timeline, frame, research, landDomain) {
  return withPathLabels(directionCollectionsUnlabelled(timeline, frame, research, landDomain))
}

/** The backend's day-by-day source paths (engine 3.1): for the selected
 * day, the path travelled so far (one heading a day from land, cattle, net
 * wind and nearby cases, turned gradually, stepped at the 9C rate, on land,
 * within the 25 km evaluated domain) and its front. Day 0 has no path. */
function pathCollections(timeline, frame) {
  const sources = sourceIndex(timeline)
  const paths = []
  const fronts = []
  for (const sp of Array.isArray(frame?.source_paths) ? frame.source_paths : []) {
    if (!sp?.geometry || !Array.isArray(sp.front)) continue
    const source = sources.get(sp.source_id)
    const properties = {
      sourceId: sp.source_id,
      anchorId: anchorIdForSource(source) ?? sp.source_id,
      recordDomain: source?.record_domain ?? null,
      disease: source?.disease ?? timeline?.disease ?? null,
      observationDate: source?.observation_date ?? null,
      bearingDeg: Number.isFinite(sp.front_bearing_deg) ? sp.front_bearing_deg : null,
      lengthKm: Number.isFinite(sp.length_km) ? sp.length_km : null,
      arrowLengthKm: Number.isFinite(sp.length_km) ? sp.length_km : null,
      stopReason: sp.stop_reason ?? null,
      memberSourceIds: Array.isArray(sp.member_source_ids) ? sp.member_source_ids : [sp.source_id],
      // The day's heading basis (engine 3.1): land, cattle, net wind, nearby cases.
      confidence: Number.isFinite(sp.heading_basis?.confidence) ? sp.heading_basis.confidence : null,
      windTowardDeg: Number.isFinite(sp.heading_basis?.wind_toward_deg) ? sp.heading_basis.wind_toward_deg : null,
      windWeight: Number.isFinite(sp.heading_basis?.wind_weight) ? sp.heading_basis.wind_weight : null,
      windSpeedMs: Number.isFinite(sp.heading_basis?.wind_speed_ms) ? sp.heading_basis.wind_speed_ms : null,
      windKind: sp.heading_basis?.wind_kind ?? null,
      cattleHere: Number.isFinite(sp.heading_basis?.cattle_here_per_km2) ? sp.heading_basis.cattle_here_per_km2 : null,
      cattleAhead: Number.isFinite(sp.heading_basis?.cattle_ahead_per_km2) ? sp.heading_basis.cattle_ahead_per_km2 : null,
      caseBearingDeg: Number.isFinite(sp.heading_basis?.case_bearing_deg) ? sp.heading_basis.case_bearing_deg : null,
      caseShare: Number.isFinite(sp.heading_basis?.case_share) ? sp.heading_basis.case_share : null,
      heldAtCoast: Boolean(sp.heading_basis?.held_at_coast),
      casesWithin25Km: Number.isFinite(sp.origin_basis?.cases_within_25km) ? sp.origin_basis.cases_within_25km : null,
      reachLowKm: Number.isFinite(sp.reach_interval_km?.[0]) ? sp.reach_interval_km[0] : null,
      reachHighKm: Number.isFinite(sp.reach_interval_km?.[1]) ? sp.reach_interval_km[1] : null,
      nominalReachKm: Number.isFinite(frame?.reach?.nominal_reach_km) ? frame.reach.nominal_reach_km : null,
      displacementKm: Number.isFinite(sp.distance_check?.displacement_km) ? sp.distance_check.displacement_km : null,
      horizonStatus: frame.horizon_status,
      day: frame.day,
      date: frame.date,
      semantics: sp.semantics,
      // My Area: a modelled new outbreak's own path (pink), and an existing
      // outbreak whose front became that new outbreak (its path stops there).
      possibleNewCase: Boolean(sp.possible_new_case),
      handedOverTo: sp.handed_over_to ?? null,
      handoverDay: Number.isInteger(sp.handover_day) ? sp.handover_day : null,
    }
    paths.push({ type: 'Feature', geometry: sp.geometry, properties: { ...properties, visualizationFeatureId: `${sp.source_id}:path` } })
    // A handed-over front has no arrow: the new outbreak marker stands there.
    if (!sp.handed_over_to) fronts.push({ type: 'Feature', geometry: { type: 'Point', coordinates: sp.front }, properties: { ...properties, visualizationFeatureId: `${sp.source_id}:front` } })
  }
  return { paths: { type: 'FeatureCollection', features: paths }, fronts: { type: 'FeatureCollection', features: fronts } }
}

/** Each case's own spread area so far (backend `plume`, on land); none on Day 0. */
export function buildPathPlumes(timeline, frame) {
  if (!isTimelineRenderable(timeline) || !frame || frame.day < 1) return EMPTY
  const features = (Array.isArray(frame.source_paths) ? frame.source_paths : [])
    .filter((sp) => sp?.plume?.type)
    .map((sp) => ({ type: 'Feature', geometry: sp.plume, properties: { sourceId: sp.source_id, memberSourceIds: sp.member_source_ids ?? [sp.source_id], day: frame.day } }))
  return { type: 'FeatureCollection', features }
}

function directionCollectionsUnlabelled(timeline, frame, research, landDomain) {
  // Engine 1.6+: the backend's day-by-day paths (curved by the direction field).
  if (Array.isArray(frame?.source_paths)) return frame.day === 0 ? { paths: EMPTY, fronts: EMPTY } : pathCollections(timeline, frame)
  // Timeline-driven: no direction on the as-of day (reach starts on Day 1);
  // from Day 1 each date draws that frame's OWN backend corridors, which grow
  // with the nominal reach (backend cap 25 km) and are land-clipped.
  if (!frame || frame.day === 0 || !Array.isArray(frame.source_corridors) || frame.source_corridors.length === 0) {
    return { paths: EMPTY, fronts: EMPTY }
  }
  return corridorCollections(timeline, frame, null, landDomain)
}

/** The selected frame's nominal-reach envelope as ONE outline feature
 * (`riskLevel: 'reach'`), or empty on Day 0 (reach starts on Day 1). */
export function buildReachOutline(timeline, frame) {
  const envelope = frame?.reach_envelope
  if (!isTimelineRenderable(timeline) || !envelope?.type) return EMPTY
  return {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: envelope,
      properties: {
        riskLevel: 'reach',
        layerRole: 'NOMINAL_REACH_OUTLINE',
        day: frame.day,
        date: frame.date,
        nominalReachKm: frame?.reach?.nominal_reach_km ?? null,
        semantics: 'NOMINAL_REACH_DISTANCE_GEOMETRIC_NOT_OBSERVED_SPREAD',
        fillOpacity: 0,
        lineOpacity: 0.85,
      },
    }],
  }
}

/** Static relative-score tier zones (backend `risk_zones`, as-of date). */
function staticTierZones(timeline, extraProperties = () => ({})) {
  return {
    type: 'FeatureCollection',
    features: tierFeatures(timeline.risk_zones, (riskLevel, properties) => ({ layerRole: 'STATIC_RELATIVE_SCORE_TIER', asOf: timeline.as_of, ...extraProperties(riskLevel, properties) })),
  }
}

/** Exact backend-scored land inside this frame's nominal reach. No centroid
 * approximation, client squares, or interpolation of scientific geometry. */
export function buildMonitoringZones(timeline, index) {
  if (!isTimelineRenderable(timeline)) return EMPTY
  const frame = timelineFrames(timeline)[clampFrameIndex(timeline, index)]
  return {
    type: 'FeatureCollection',
    features: tierFeatures(frame?.reach_limited_risk_zones, (_riskLevel, properties) => ({
      cellId: `monitoring:${properties.tier}`,
      tierLabel: properties.label ?? properties.tier,
      layerRole: 'SCORED_LAND_WITHIN_NOMINAL_REACH',
      inReach: true,
      score: null,
      areaKm2: Number.isFinite(properties.area_km2) ? properties.area_km2 : null,
      asOf: timeline.as_of,
      day: frame.day,
      date: frame.date,
      horizonStatus: frame.horizon_status,
    })),
  }
}

/** National Map view model: same shape the existing MapLibreCanvas Page-1
 * layers render. `riskZones` are the STATIC backend tier zones (identical on
 * every day, so the cross-fader never animates them); `contextZones` carries
 * the selected day's nominal-reach outline; `paths`/`fronts` are the static
 * direction indicators (full corridors only with `research`). */
export function buildNationalTimelineLayers(timeline, index, { research = false, landDomain } = {}) {
  if (!isTimelineRenderable(timeline)) {
    return { activeIndex: 0, date: null, frame: null, anchorCount: 0, riskZones: EMPTY, contextZones: EMPTY, paths: EMPTY, fronts: EMPTY, remaining: EMPTY, plumes: EMPTY, origins: EMPTY, plateauIndex: null }
  }
  const activeIndex = clampFrameIndex(timeline, index)
  const frame = timelineFrames(timeline)[activeIndex]
  const { paths, fronts } = directionCollections(timeline, frame, research, landDomain)
  return {
    activeIndex,
    date: frame.date,
    frame,
    anchorCount: (timeline.sources ?? []).length,
    riskZones: staticTierZones(timeline),
    contextZones: buildReachOutline(timeline, frame),
    paths,
    fronts,
    // Nothing ahead of the selected day is drawn: no future line or end point.
    remaining: EMPTY,
    plumes: buildPathPlumes(timeline, frame),
    origins: buildTimelineOrigins(timeline, frame),
    plateauIndex: plateauStartIndex(timeline),
  }
}

function districtFrameSummary(frame, districtName) {
  const key = typeof districtName === 'string' ? districtName.trim().toLowerCase() : null
  const summaries = Array.isArray(frame?.district_summaries) ? frame.district_summaries : []
  return summaries.find((summary) => typeof summary?.district === 'string' && summary.district.toLowerCase() === key) ?? null
}

/** One bar per backend frame: height = the frame's own area within nominal
 * reach (km2) relative to the largest frame, colour = the highest backend
 * tier within reach. A real plateau in these values is shown as flat bars. */
export function buildAreaOutlookFrames(timeline, districtName) {
  const frames = timelineFrames(timeline)
  const rows = frames.map((frame, index) => {
    const summary = districtFrameSummary(frame, districtName)
    const tier = summary?.highest_tier_within_reach ?? null
    return {
      index,
      day: frame.day,
      date: frame.date,
      horizonStatus: frame.horizon_status,
      tier,
      riskLevel: tier ? TIER_TO_DISTRICT_RISK[tier] : null,
      areaKm2: Number.isFinite(summary?.area_within_reach_km2) ? summary.area_within_reach_km2 : 0,
    }
  })
  const maxArea = Math.max(0, ...rows.map((row) => row.areaKm2))
  return rows.map((row) => ({ ...row, heightPercent: maxArea > 0 ? (row.areaKm2 / maxArea) * 100 : 0 }))
}

/** A source's influence inside the vet's district on the selected day, from
 * the backend's `district_influence` (source-specific modeled risk on district
 * land). Before its first influence day a source is not shown as influencing. */
export function districtInfluenceStatus(entry, day, districtName = 'the district') {
  if (!entry) return null
  const today = entry.by_day?.find((d) => d.day === day) ?? null
  const first = Number.isInteger(entry.first_influence_day) ? entry.first_influence_day : null
  const reachDay = Number.isInteger(entry.first_nominal_reach_day) ? entry.first_nominal_reach_day : null
  const influencing = first !== null && day >= first && today?.area_km2 > 0
  return {
    insideDistrict: Boolean(entry.inside_district),
    influencing,
    firstInfluenceDay: first,
    firstNominalReachDay: reachDay,
    areaKm2: influencing ? today.area_km2 : 0,
    maxScore: influencing ? today.max_score : null,
    distanceKm: Number.isFinite(entry.distance_to_district_km) ? entry.distance_to_district_km : null,
    label: entry.inside_district ? 'IN MY DISTRICT' : influencing ? 'INFLUENCING MY DISTRICT' : first !== null ? `FROM DAY ${first}` : 'NO MODELED INFLUENCE',
    text: influencing
      ? `Modeled influence covers ${Math.round(today.area_km2).toLocaleString('en-US')} km² of ${districtName} on Day ${day} (highest score ${today.max_score.toFixed(2)}); first influence Day ${first}.`
      : first !== null
        ? `No modeled influence inside ${districtName} on Day ${day}. First influence Day ${first}${reachDay !== null && reachDay !== first ? `; first nominal reach Day ${reachDay}` : ''}.`
        : `No modeled influence inside ${districtName} within the ${entry.by_day?.length ? entry.by_day.length - 1 : 14}-day horizon${reachDay !== null ? `; first nominal reach Day ${reachDay} (distance only)` : ''}.`,
  }
}

export const INFLUENCE_KIND = Object.freeze({ LOCAL: 'LOCAL SOURCE', APPROACHING: 'APPROACHING AREA' })

function daysBetween(fromIso, toIso) {
  const from = Date.parse(`${fromIso}T00:00:00Z`)
  const to = Date.parse(`${toIso}T00:00:00Z`)
  return Number.isFinite(from) && Number.isFinite(to) ? Math.round((to - from) / 86400000) : null
}

/** Backend display band of a score (`provenance.display_bands`, highest first). */
function bandNameOf(score, displayBands) {
  if (!Number.isFinite(score) || !Array.isArray(displayBands) || displayBands.length === 0) return null
  const band = displayBands.find((b) => score >= b.min) ?? displayBands[displayBands.length - 1]
  return typeof band?.band === 'string' ? band.band[0].toUpperCase() + band.band.slice(1) : null
}

/**
 * "Outbreaks influencing my area" card for one source on the selected day,
 * read only from the backend snapshot: the district influence per day
 * (`district_influence.by_day`: the highest score this source's own kernel
 * gives on district land), the day's path heading, and the new
 * cases it triggers. Before `first_influence_day` the source is never shown
 * as having reached the district. `kind` is null when the source has no
 * modelled influence in the horizon (or the snapshot has no influence data).
 */
export function influenceCard(source, frame, districtEntry, { asOf = null, direction = null, possibleNewCases = [], displayBands = [], districtName = 'the district', horizonDays = 14 } = {}) {
  const day = Number.isInteger(frame?.day) ? frame.day : 0
  const pathToday = (frame?.source_paths ?? []).find((path) => path?.source_id === source.source_id && !path.possible_new_case)
  const heading = day >= 1 && pathToday?.geometry && Number.isFinite(pathToday.front_bearing_deg) ? pathToday.front_bearing_deg : direction?.bearing_deg
  const directionText = Number.isFinite(heading) ? `heading ${compassPoint(heading)} ${Math.round(heading)}°` : 'direction unavailable'
  const ageDays = asOf && source.observation_date ? daysBetween(source.observation_date, asOf) : null
  const triggered = possibleNewCases.filter((p) => Array.isArray(p?.triggered_by) && p.triggered_by.includes(source.source_id) && Number.isInteger(p.seed_day))
  const seededBy = triggered.filter((p) => p.seed_day <= day)
  const nextSeed = triggered.filter((p) => p.seed_day > day).map((p) => p.seed_day).sort((a, b) => a - b)[0]
  const possibleText = seededBy.length
    ? `Started a new outbreak in ${districtName} on Day ${Math.min(...seededBy.map((p) => p.seed_day))} (modelled)`
    : Number.isInteger(nextSeed) ? `Could start a new outbreak in ${districtName} on Day ${nextSeed} (modelled)` : null
  const base = { directionText, ageDays, possibleText, possibleCount: seededBy.length, caseRef: Array.isArray(source.case_refs) && source.case_refs.length ? String(source.case_refs[0]) : null }
  if (!districtEntry) {
    return { ...base, kind: null, modelData: false, series: [], firstInfluenceDay: null, influencingToday: false, whereText: null, dayStatusText: 'District influence is not available in this snapshot' }
  }
  const byDay = new Map((districtEntry.by_day ?? []).map((entry) => [entry.day, entry]))
  const lastDay = Math.max(horizonDays, ...byDay.keys())
  const series = Array.from({ length: lastDay + 1 }, (_, d) => {
    const entry = byDay.get(d)
    return entry?.area_km2 > 0 && Number.isFinite(entry.max_score) ? entry.max_score : 0
  })
  const first = Number.isInteger(districtEntry.first_influence_day) ? districtEntry.first_influence_day : null
  const inside = Boolean(districtEntry.inside_district)
  const influencingToday = first !== null && day >= first && series[day] > 0
  const distanceKm = Number.isFinite(districtEntry.distance_to_district_km) ? districtEntry.distance_to_district_km : null
  const dayStatusText = influencingToday
    ? `${bandNameOf(series[day], displayBands) ?? 'Modelled'} influence on Day ${day}`
    : first !== null && day < first
      ? `reaches the district on Day ${first}`
      : first !== null ? `no modelled influence on Day ${day}` : `no modelled influence within ${lastDay} days`
  return {
    ...base,
    kind: inside ? INFLUENCE_KIND.LOCAL : first !== null ? INFLUENCE_KIND.APPROACHING : null,
    modelData: true,
    series,
    firstInfluenceDay: first,
    influencingToday,
    whereText: inside ? `Inside ${districtName} (local source)` : distanceKm !== null ? `${distanceKm.toFixed(1)} km from ${districtName}` : `Outside ${districtName}`,
    dayStatusText,
  }
}

function influenceFor(source, frame, direction, districtEntry, districtName, cardContext = {}) {
  const reach = frame?.reach?.nominal_reach_km
  const bearing = direction?.bearing_deg
  const domainLabel = source.record_domain === 'OPERATIONAL' ? 'Vet-verified case' : 'Historical record'
  let description
  if (frame?.day === 0 || !Number.isFinite(reach)) {
    description = `${domainLabel} observed ${source.observation_date}. Nominal reach starts on Day 1.`
  } else if (Number.isFinite(bearing)) {
    description = `${domainLabel}. Geometric tendency ${Math.round(bearing)}° (${compassPoint(bearing)}), nominal reach ${reach.toFixed(1)} km on ${frame.date}.`
  } else {
    description = `${domainLabel}. No directional tendency (no neighbouring source); nominal reach ${reach.toFixed(1)} km on ${frame.date}.`
  }
  const district = districtInfluenceStatus(districtEntry, frame?.day ?? 0, districtName ?? 'the district')
  if (district) description = `${district.text} ${description}`
  return {
    district,
    anchorId: anchorIdForSource(source),
    caseId: source.record_domain === 'OPERATIONAL' ? anchorIdForSource(source) : source.source_id,
    sourceId: source.source_id,
    recordDomain: source.record_domain,
    farmId: typeof source.farm_id === 'string' ? source.farm_id : null,
    observationDate: source.observation_date ?? null,
    // The source's own position (backend value), for "View on Map".
    latitude: Number.isFinite(source.latitude) ? source.latitude : null,
    longitude: Number.isFinite(source.longitude) ? source.longitude : null,
    provenance: source.provenance ?? null,
    locationDistrict: null,
    status: district?.label ?? horizonLabel(frame?.horizon_status).toUpperCase(),
    description,
    bearingDeg: Number.isFinite(bearing) ? bearing : null,
    // Another vet's case (backend DETAIL_PRIVACY_REDUCED): one-way keys only.
    privacyReduced: source.detail_access === 'PRIVACY_REDUCED_EXTERNAL_FARM',
    card: influenceCard(source, frame, districtEntry, { ...cardContext, direction, districtName: districtName ?? 'the district' }),
  }
}

/** Modelled new outbreaks in the vet's district that have appeared by the
 * selected day (backend `possible_new_cases`, seed day <= day): where an
 * existing outbreak's front first stands in the district. Never confirmed
 * cases: shown with their own pink marker, hover card and label. */
export function buildPossibleCases(timeline, frame) {
  const day = Number.isInteger(frame?.day) ? frame.day : -1
  const features = (Array.isArray(timeline?.possible_new_cases) ? timeline.possible_new_cases : [])
    .filter((p) => Number.isFinite(p?.longitude) && Number.isFinite(p?.latitude) && Number.isInteger(p.seed_day) && p.seed_day <= day)
    .map((p) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
      properties: {
        id: p.id, farmId: p.farm_id ?? null, seedDay: p.seed_day, seedDate: p.seed_date ?? null, seedScore: p.seed_score,
        generation: p.generation, triggeredBy: Array.isArray(p.triggered_by) ? p.triggered_by : [], newToday: p.seed_day === day,
        arrival: p.arrival ?? null,
        label: `New outbreak · Day ${p.seed_day}`,
      },
    }))
  return { type: 'FeatureCollection', features }
}

/** Sources inside the district first, then those influencing it today,
 * then by first influence day (no influence last); otherwise backend order. */
function sortInfluences(influences) {
  const rank = (i) => (!i.district ? 3 : i.district.insideDistrict ? 0 : i.district.influencing ? 1 : i.district.firstInfluenceDay !== null ? 2 : 3)
  return influences
    .map((influence, index) => ({ influence, index }))
    .sort((a, b) => rank(a.influence) - rank(b.influence)
      || (a.influence.district?.firstInfluenceDay ?? 99) - (b.influence.district?.firstInfluenceDay ?? 99)
      || a.index - b.index)
    .map(({ influence }) => influence)
}

/** My Area view model in the shape the existing My Area canvas, strip,
 * chart, KPI cards, intelligence panel and influence cards render. */
export function buildMyAreaTimelineView(timeline, index, districtName, { research = false, landDomain } = {}) {
  const renderable = isTimelineRenderable(timeline)
  const frames = timelineFrames(timeline)
  const activeIndex = renderable ? clampFrameIndex(timeline, index) : 0
  const frame = renderable ? frames[activeIndex] : null
  const summary = districtFrameSummary(frame, districtName)
  const tier = summary?.highest_tier_within_reach ?? null
  const directions = new Map((timeline?.source_directions ?? []).map((direction) => [direction.source_id, direction]))
  const districtEntries = new Map((timeline?.district_influence?.sources ?? []).map((entry) => [entry.source_id, entry]))
  const { paths, fronts } = renderable ? directionCollections(timeline, frame, research, landDomain) : { paths: EMPTY, fronts: EMPTY }
  // The as-of surface stays faint and fixed. Bright polygons are only the
  // backend's scored-land intersection with the selected day's reach.
  // This changes monitoring coverage, never C0 scores or infection status.
  const contextFeatures = renderable ? [
    // Static tiers stay in the data (a click still names the area and its
    // tier) but are not painted: the map shows only what the selected day's
    // reach covers, so the spread appears as the timeline plays.
    ...staticTierZones(timeline, () => ({ fillOpacity: 0, lineOpacity: 0 })).features,
    // The day's nominal reach is drawn in red with a light red wash: how far
    // the reach extends that day (distance only, not observed spread).
    ...buildReachOutline(timeline, frame).features.map((feature) => ({
      ...feature,
      properties: {
        ...feature.properties,
        fillOpacity: 0.07,
        label: Number.isFinite(feature.properties.nominalReachKm) ? `${shortDateLabel(feature.properties.date)} · ${feature.properties.nominalReachKm.toFixed(1)} km reach` : null,
      },
    })),
  ] : []
  const foregroundFeatures = renderable
    ? tierFeatures(frame?.reach_limited_risk_zones, () => ({ fillOpacity: MY_AREA_ZONE_HIT_OPACITY, lineOpacity: 0, layerRole: 'SCORED_LAND_WITHIN_NOMINAL_REACH', asOf: timeline.as_of, day: frame.day, date: frame.date }))
    : []
  return {
    renderable,
    status: timeline?.status ?? null,
    activeIndex,
    frameCount: frames.length,
    dates: frames.map((f) => f.date),
    date: frame?.date ?? null,
    day: frame?.day ?? null,
    horizonStatus: frame?.horizon_status ?? null,
    reachKm: Number.isFinite(frame?.reach?.nominal_reach_km) ? frame.reach.nominal_reach_km : null,
    reachIntervalKm: Array.isArray(frame?.reach?.interval_km) ? frame.reach.interval_km : null,
    areaWithinReachKm2: Number.isFinite(summary?.area_within_reach_km2) ? summary.area_within_reach_km2 : null,
    districtTier: tier,
    districtRisk: tier ? TIER_TO_DISTRICT_RISK[tier] : null,
    anchorCount: (timeline?.sources ?? []).length,
    // Faint context = fixed score tiers; bright zones = backend reach
    // intersections, the same day-specific areas used in the outlook chart.
    contextZones: { type: 'FeatureCollection', features: contextFeatures },
    riskZones: { type: 'FeatureCollection', features: foregroundFeatures },
    paths,
    fronts,
    origins: renderable ? buildTimelineOrigins(timeline, frame) : EMPTY,
    plateauIndex: renderable ? plateauStartIndex(timeline) : null,
    plateauNote: renderable ? plateauNote(timeline, activeIndex) : null,
    areaPlateauIndex: renderable ? areaPlateauStartIndex(buildAreaOutlookFrames(timeline, districtName)) : null,
    limitations: renderable && Array.isArray(timeline.limitations) ? timeline.limitations : [],
    // The selected raw backend frame (Area Intelligence reads its paths and reach).
    frame: renderable ? frame : null,
    possibleCases: renderable ? buildPossibleCases(timeline, frame) : EMPTY,
    influences: renderable ? sortInfluences((timeline.sources ?? []).map((source) => influenceFor(source, frame, directions.get(source.source_id), districtEntries.get(source.source_id), districtName, {
      asOf: timeline.as_of ?? null,
      possibleNewCases: Array.isArray(timeline.possible_new_cases) ? timeline.possible_new_cases : [],
      displayBands: timeline.provenance?.display_bands ?? [],
      horizonDays: Number.isInteger(timeline.horizon_days) ? timeline.horizon_days : frames.length - 1,
    }))) : [],
    influenceDataAvailable: renderable && Boolean(timeline.district_influence),
    outlook: renderable ? buildAreaOutlookFrames(timeline, districtName) : [],
    environmentStatus: timeline?.environment?.status ?? null,
  }
}
