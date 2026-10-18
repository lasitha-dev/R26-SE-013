/**
 * "Farms in my district" (My Area): one row per authorised registered farm
 * inside the vet's district (the roster: assigned + district surveillance
 * farms from the operational backend, de-duplicated by farm id), with its
 * real herd size, verified case count, location and the selected day's
 * modelled status.
 *
 * Status, in order:
 *   ACTIVE CASES          a vet-verified report of the selected disease in the
 *                         last 30 days (the same age rule as the map's case
 *                         markers); older reports are listed, not active.
 *   LOCATION UNAVAILABLE  no valid GPS: never placed on the map or scored.
 *   PENDING               a spread line (an outbreak's or a new outbreak's
 *                         backend path, as travelled by the selected day)
 *                         passes within the model resolution (the backend's
 *                         `resolution_km`, 2.5 km) of the farm GPS: awaiting
 *                         a check, not a case. From that day on.
 *   COULD BE AFFECTED     the farm's GPS lies on the selected day's Risk
 *                         Zones surface (the backend day raster, the same
 *                         lookup the map colour and "farms that could be
 *                         affected" use). Modelled exposure, never infection.
 *   MONITORING            mapped, no report, not on today's surface.
 * A farm first reached on Day 13 is MONITORING on Days 0-12.
 */
import { CASE_AGE_CLASS, VISIBLE_CASE_MAX_AGE_DAYS, classifyCaseAge } from './caseAge'
import { bandOfScore, BAND_LABEL, rasterScoreAt } from './riskFieldModel'

export const FARM_LIST_STATUS = Object.freeze({
  VERIFIED: 'ACTIVE CASES',
  PENDING: 'PENDING',
  AFFECTED: 'COULD BE AFFECTED',
  MONITORING: 'MONITORING',
  NO_LOCATION: 'LOCATION UNAVAILABLE',
})
const ORDER = [FARM_LIST_STATUS.VERIFIED, FARM_LIST_STATUS.PENDING, FARM_LIST_STATUS.AFFECTED, FARM_LIST_STATUS.MONITORING, FARM_LIST_STATUS.NO_LOCATION]
const KM_PER_DEG_LAT = 110.574
// Registered herd sizes above this are treated as data-entry errors.
const MAX_PLAUSIBLE_HERD = 100000

/** A registered herd size, or null when missing / not a whole number / implausible. */
export function validAnimalCount(value) {
  return Number.isInteger(value) && value >= 0 && value <= MAX_PLAUSIBLE_HERD ? value : null
}

function scoreAt(model, day, coordinates) {
  const raster = model?.rasterFor?.(day)
  if (!raster || !coordinates) return null
  const score = rasterScoreAt(raster, model.grid, coordinates[0], coordinates[1])
  return Number.isFinite(score) ? score : null
}

/** Shortest distance (km) from a point to a line's vertices and segments. */
function distanceToLineKm([lon, lat], coords) {
  const kx = 111.32 * Math.cos((lat * Math.PI) / 180)
  let best = Infinity
  for (let i = 0; i < coords.length; i += 1) {
    const [ax, ay] = [(coords[i][0] - lon) * kx, (coords[i][1] - lat) * KM_PER_DEG_LAT]
    if (i === 0) { best = Math.min(best, Math.hypot(ax, ay)); continue }
    const [bx, by] = [(coords[i - 1][0] - lon) * kx, (coords[i - 1][1] - lat) * KM_PER_DEG_LAT]
    const dx = ax - bx
    const dy = ay - by
    const t = dx || dy ? Math.max(0, Math.min(1, -(bx * dx + by * dy) / (dx * dx + dy * dy))) : 0
    best = Math.min(best, Math.hypot(bx + t * dx, by + t * dy))
  }
  return best
}

/** First day a backend spread line passes within `catchKm` of the farm, and that path. */
function firstSpreadLine(timeline, gps, catchKm) {
  if (!gps || !Number.isFinite(catchKm)) return null
  for (const frame of Array.isArray(timeline?.frames) ? timeline.frames : []) {
    for (const path of frame.source_paths ?? []) {
      const coords = path?.geometry?.type === 'LineString' ? path.geometry.coordinates : null
      if (coords?.length >= 2 && distanceToLineKm(gps, coords) <= catchKm) {
        return { day: frame.day, sourceId: path.source_id, newOutbreak: Boolean(path.possible_new_case) }
      }
    }
  }
  return null
}

/** Verified reports of the disease within the last 30 days of the reference
 * date (`null` reference: every report counts, as before). */
function activeCases(farm, disease, referenceDateKey) {
  const ofDisease = (farm.cases ?? []).filter((c) => !disease || c.disease === disease)
  if (!referenceDateKey) return ofDisease.length
  return ofDisease.filter((c) => {
    const age = classifyCaseAge(c.reportedAt ?? c.verificationTime, referenceDateKey).ageClass
    return age === CASE_AGE_CLASS.RECENT || age === CASE_AGE_CLASS.OLDER
  }).length
}

export function buildFarmListRows({ roster = null, model = null, dayIndex = 0, futureMode = true, possibleNewCases = [], placeFor = null, disease = null, referenceDateKey = null, timeline = null } = {}) {
  const minScore = model?.grid?.min_score ?? 0.03
  // A farm is "on a spread line" within the model's own spatial resolution.
  const catchKm = timeline?.provenance?.risk_field_rule?.resolution_km ?? null
  const dayCount = model?.frameCount ?? 0
  const seen = new Set()
  const rows = []
  for (const farm of roster?.rows ?? []) {
    // Other districts' farms are never listed; the vet's own farms elsewhere
    // are counted in the summary only.
    if (farm.outsideDistrict || !farm.farmId || seen.has(farm.farmId)) continue
    seen.add(farm.farmId)
    const gps = Array.isArray(farm.coordinates) && farm.coordinates.every(Number.isFinite) ? farm.coordinates : null
    const scoreToday = futureMode && gps ? scoreAt(model, dayIndex, gps) : null
    const onSurface = scoreToday !== null && scoreToday >= minScore
    let firstSurfaceDay = null
    if (futureMode && gps) {
      for (let d = 0; d < dayCount; d += 1) {
        const s = scoreAt(model, d, gps)
        if (s !== null && s >= minScore) { firstSurfaceDay = d; break }
      }
    }
    const line = futureMode ? firstSpreadLine(timeline, gps, catchKm) : null
    const onLine = line !== null && dayIndex >= line.day
    const possible = futureMode
      ? (possibleNewCases ?? []).find((p) => p?.farm_id === farm.farmId && Number.isInteger(p.seed_day) && p.seed_day <= dayIndex) ?? null
      : null
    const allCases = Number.isInteger(farm.diseaseCaseCount) ? farm.diseaseCaseCount : 0
    const caseCount = farm.cases ? activeCases(farm, disease, referenceDateKey) : allCases
    const olderCaseCount = Math.max(0, allCases - caseCount)
    const status = caseCount > 0 ? FARM_LIST_STATUS.VERIFIED
      : !gps ? FARM_LIST_STATUS.NO_LOCATION
        : onLine ? FARM_LIST_STATUS.PENDING
          : onSurface ? FARM_LIST_STATUS.AFFECTED : FARM_LIST_STATUS.MONITORING
    const band = onSurface ? bandOfScore(scoreToday, model.bands) : null
    const animals = validAnimalCount(farm.totalAnimals)
    const place = gps ? placeFor?.(farm.farmId) ?? null : null
    let detail
    if (status === FARM_LIST_STATUS.NO_LOCATION) detail = 'No valid GPS on record: listed, not mapped or scored'
    else if (onLine) detail = `On the ${line.newOutbreak ? 'new outbreak' : 'outbreak'} spread line since Day ${line.day} (within ${catchKm} km) · awaiting a check, not a case`
    else if (futureMode && line && line.day > dayIndex && (firstSurfaceDay === null || firstSurfaceDay > dayIndex)) detail = `Spread line reaches this farm on Day ${line.day}`
    else if (onSurface) detail = `${BAND_LABEL[band]} risk zone on Day ${dayIndex} (score ${scoreToday.toFixed(2)}) · modelled exposure, not infected`
    else if (futureMode && firstSurfaceDay !== null && firstSurfaceDay > dayIndex) detail = `Risk zone reaches this farm on Day ${firstSurfaceDay}`
    else if (futureMode) detail = 'Not on the risk surface this day'
    else detail = null
    if (olderCaseCount > 0) {
      const older = `${olderCaseCount} older case${olderCaseCount === 1 ? '' : 's'} (over ${VISIBLE_CASE_MAX_AGE_DAYS} days)`
      detail = detail ? `${detail} · ${older}` : older
    }
    rows.push({
      farmId: farm.farmId,
      name: farm.label,
      personallyAssigned: Boolean(farm.personallyAssigned),
      animals,
      // Herd size the backend withholds (not the vet's assigned farm) vs a
      // value that is present but unusable.
      animalCountStatus: animals !== null ? 'OK' : farm.totalAnimals === null || farm.totalAnimals === undefined ? (farm.personallyAssigned ? 'MISSING' : 'NOT_SHARED') : 'INVALID',
      caseCount,
      olderCaseCount,
      spreadLineDay: line?.day ?? null,
      coordinates: gps,
      locationText: gps ? `${place ? `${place} · ` : ''}${gps[1].toFixed(3)}, ${gps[0].toFixed(3)}` : 'Location unavailable',
      status,
      band,
      score: onSurface ? scoreToday : null,
      onSurface,
      firstSurfaceDay,
      possibleNewCaseDay: possible ? possible.seed_day : null,
      detail,
    })
  }
  rows.sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status)
    || b.caseCount - a.caseCount
    || (b.score ?? 0) - (a.score ?? 0)
    || (a.firstSurfaceDay ?? 99) - (b.firstSurfaceDay ?? 99)
    || String(a.name).localeCompare(String(b.name)))
  const count = (status) => rows.filter((r) => r.status === status).length
  return {
    rows,
    summary: {
      total: rows.length,
      verified: count(FARM_LIST_STATUS.VERIFIED),
      pending: count(FARM_LIST_STATUS.PENDING),
      affected: count(FARM_LIST_STATUS.AFFECTED),
      monitoring: count(FARM_LIST_STATUS.MONITORING),
      noLocation: count(FARM_LIST_STATUS.NO_LOCATION),
      assignedOutsideDistrict: (roster?.rows ?? []).filter((r) => r.outsideDistrict).length,
    },
  }
}
