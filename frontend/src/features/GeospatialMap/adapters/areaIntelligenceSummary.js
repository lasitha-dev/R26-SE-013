/**
 * Area Intelligence summary (My Area, Future Impact): every value for the
 * selected backend frame, from the same sources the map draws --
 *   - risk category, peak score, coloured area, colour extent, farms and
 *     animals on coloured land: the selected day's outlook row (the day's
 *     backend raster inside the district, adapters/riskOutlook.js);
 *   - influencing sources: the cards (`district_influence`, Task 4);
 *   - projected spread: the day's backend source paths;
 *   - farms / cases: the authorised roster and verified case intelligence.
 * Nothing is computed from a score; quantities of different kinds (score,
 * area, farm counts, distances) are kept in separate fields.
 */
import { INFLUENCE_KIND } from './spatialTimelineView'

export const DISTRICT_RISK_NONE = 'none'

function influenceCounts(influences = [], dataAvailable = true) {
  const cards = influences.map((i) => i.card).filter(Boolean)
  if (!dataAvailable || cards.length === 0 || cards.every((c) => !c.modelData)) return null
  const local = cards.filter((c) => c.kind === INFLUENCE_KIND.LOCAL)
  const external = cards.filter((c) => c.kind === INFLUENCE_KIND.APPROACHING)
  return {
    local: local.length,
    external: external.length,
    externalReachingNow: external.filter((c) => c.influencingToday).length,
    nearbyNoInfluence: cards.filter((c) => c.modelData && !c.kind).length,
  }
}

function spreadToday(frame) {
  const paths = (frame?.source_paths ?? []).filter((p) => p?.geometry && !p.possible_new_case)
  const lengths = paths.map((p) => p.length_km).filter(Number.isFinite)
  return {
    activePaths: paths.length,
    possiblePaths: (frame?.source_paths ?? []).filter((p) => p?.geometry && p.possible_new_case).length,
    travelledKm: lengths.length ? Math.max(...lengths) : 0,
  }
}

export function buildAreaIntelligenceSummary({
  view = null, frame = null, row = null, roster = null, caseIntel = null, breakdown = null, focusedSource = null, focusedLabel = null,
} = {}) {
  const summary = roster?.summary ?? {}
  const influence = influenceCounts(view?.influences, view?.influenceDataAvailable !== false)
  const nominal = Number.isFinite(frame?.reach?.nominal_reach_km) ? frame.reach.nominal_reach_km : null
  return {
    farms: { mapped: summary.mapped ?? 0, total: summary.total ?? 0 },
    frame: { index: view?.activeIndex ?? 0, count: view?.frameCount ?? 0, day: view?.day ?? null, date: view?.date ?? null, horizonStatus: view?.horizonStatus ?? null },
    risk: row
      ? { band: row.maxBand ?? DISTRICT_RISK_NONE, peakScore: Number.isFinite(row.maxScore) ? row.maxScore : null }
      : null,
    // Model-confirmed influence when the snapshot has it; otherwise only
    // the geometric inside/outside split of the eligible sources (flagged).
    sources: influence
      ? { ...influence, basis: 'MODELLED_INFLUENCE' }
      : { local: breakdown?.inside ?? 0, external: breakdown?.outside ?? 0, externalReachingNow: null, nearbyNoInfluence: 0, basis: 'LOCATION_ONLY' },
    spread: {
      ...spreadToday(frame),
      // How far colour is drawn from its main case today (raster), which on
      // Day 0 is the position uncertainty around each case, not spread.
      colourExtentKm: row?.extentKm ?? null,
      // 9C nominal reach = S0 x day: a distance rate, not capped at the 25 km
      // local domain the paths and colours stop at.
      nominalReachKm: nominal,
    },
    area: row ? { coloredKm2: row.coloredKm2, share: row.coloredShare, districtKm2: row.districtKm2 } : null,
    affected: row
      ? { farms: row.monitoredFarms, animals: row.monitoredAnimals ?? 0, farmsWithoutAnimalCount: row.monitoredFarmsWithoutAnimalCount ?? 0, possibleNewCases: view?.possibleCases?.features?.length ?? 0 }
      : null,
    cases: { reports: caseIntel?.reportCount ?? 0, farms: caseIntel?.uniqueFarmCount ?? 0, pending: caseIntel?.pending?.length ?? 0 },
    focused: focusedSource ? (focusedLabel ?? focusedSource.sourceId ?? 'Selected source') : 'All sources',
  }
}
