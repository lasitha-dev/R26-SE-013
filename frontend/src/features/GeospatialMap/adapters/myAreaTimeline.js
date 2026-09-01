import { addDaysToIsoDate } from './forecastDate'

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

function safeForecastDate(t0, day) {
  if (typeof t0 !== 'string' || !t0) return null
  try {
    return addDaysToIsoDate(t0, day)
  } catch {
    return null
  }
}

/**
 * Builds the one canonical My Area timeline from the selected origin's
 * genuine `nominal_reach_by_day` entries. Missing, duplicate, malformed,
 * and synthetic in-between days are never created. D0 is the selected
 * origin's real T0 context and deliberately carries no fabricated 0 km.
 */
export function buildMyAreaForecastFrames({ t0 = null, nominalReachByDay = [] } = {}) {
  const byDay = new Map()
  for (const entry of Array.isArray(nominalReachByDay) ? nominalReachByDay : []) {
    if (!Number.isInteger(entry?.day) || entry.day <= 0 || !finiteNumber(entry.nominal_reach_km)) continue
    if (!byDay.has(entry.day)) byDay.set(entry.day, entry)
  }

  const futureFrames = [...byDay.values()]
    .sort((a, b) => a.day - b.day)
    .map((entry) => ({
      day: entry.day,
      actualDate: safeForecastDate(t0, entry.day),
      nominalReachKm: entry.nominal_reach_km,
      intervalLowerKm: finiteNumber(entry.derived_interval_lower_km) ? entry.derived_interval_lower_km : null,
      intervalUpperKm: finiteNumber(entry.derived_interval_upper_km) ? entry.derived_interval_upper_km : null,
      semantic: 'FORECAST_REACH',
    }))

  return [
    {
      day: 0,
      actualDate: safeForecastDate(t0, 0),
      nominalReachKm: null,
      intervalLowerKm: null,
      intervalUpperKm: null,
      semantic: 'CURRENT_OBSERVED_CONTEXT',
    },
    ...futureFrames,
  ]
}

export function findMyAreaForecastFrame(frames, day) {
  return (frames ?? []).find((frame) => frame.day === day) ?? (frames ?? [])[0] ?? null
}

export function adjacentMyAreaForecastDay(frames, selectedDay, direction) {
  const safeFrames = Array.isArray(frames) ? frames : []
  if (safeFrames.length === 0) return null
  const index = Math.max(0, safeFrames.findIndex((frame) => frame.day === selectedDay))
  const nextIndex = Math.min(safeFrames.length - 1, Math.max(0, index + direction))
  return safeFrames[nextIndex].day
}
