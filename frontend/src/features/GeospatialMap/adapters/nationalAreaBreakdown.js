/**
 * PAGE-3-NATIONAL-KPI: real, national (never single-district-fixed)
 * geographic breakdown for the Analysis & Trends "Affected Areas" KPI
 * and "Most Affected Areas" table. Built entirely from primitives this
 * feature already has and already tests -- never a second/approximate
 * geographic lookup:
 *
 *  - `buildNationalSourcesFeatureCollection` (`components/mapLibreAdapter.js`)
 *    merges every real origin's own real source geometry -- the same
 *    merge Page 1's national browsing layer already performs.
 *  - `aggregateNationalSourcesByLocation` (`nationalSourcePresentation.js`)
 *    collapses that merge to ONE feature per distinct real coordinate --
 *    the same dedup this codebase already relies on to avoid double-
 *    counting one physical record whose 14-day eligibility window is
 *    shared by more than one real origin (see that file's own header
 *    comment for the documented 9-rows/6-records example). Skipping this
 *    step here would silently inflate a district's real record count.
 *  - `isPointInsideDistrictFeature` (`districtGeometry.js`) is the exact
 *    ray-casting primitive already used for the Matara filter, applied
 *    here against EVERY feature in the full Sri Lanka ADM2 collection
 *    instead of just one, so a record is attributed to whichever real
 *    district polygon actually contains it.
 *
 * A record whose real coordinate falls outside every district polygon is
 * excluded from the district breakdown entirely -- never assigned to a
 * guessed/nearest district name.
 */

import { buildNationalSourcesFeatureCollection } from '../components/mapLibreAdapter'
import { isPointInsideDistrictFeature, normalizeDistrictDisplayName } from './districtGeometry'
import { aggregateNationalSourcesByLocation } from './nationalSourcePresentation'

/** Every real origin's own real source geometry, merged and deduplicated
 * to one feature per distinct real coordinate. `originsWithSources` is
 * `useNationalOutbreaks`'s own real, already-fetched state -- this never
 * triggers a new network request. */
export function buildDeduplicatedNationalSources(originsWithSources) {
  const merged = buildNationalSourcesFeatureCollection(originsWithSources ?? [])
  return aggregateNationalSourcesByLocation(merged)
}

/** The real district (short display name, e.g. "Matara") whose polygon
 * contains `feature`'s real coordinate, or `null` if none does. Never
 * guesses a nearest district for a point outside every polygon. */
export function resolveDistrictForFeature(feature, districtFeatureCollection) {
  const coordinates = feature?.geometry?.coordinates
  const districtFeatures = districtFeatureCollection?.features
  if (!Array.isArray(coordinates) || !Array.isArray(districtFeatures)) return null
  const match = districtFeatures.find((district) => isPointInsideDistrictFeature(coordinates, district))
  return match ? normalizeDistrictDisplayName(match.properties?.shapeName) : null
}

/** `{ count, districts }` -- the set of real districts containing at
 * least one real, deduplicated observed record. `districts` is sorted
 * alphabetically for a stable, deterministic result. `aggregatedSources`
 * is the real FeatureCollection `buildDeduplicatedNationalSources`
 * returns. */
export function deriveAffectedAreas(aggregatedSources, districtFeatureCollection) {
  const districts = new Set()
  for (const feature of aggregatedSources?.features ?? []) {
    const district = resolveDistrictForFeature(feature, districtFeatureCollection)
    if (district) districts.add(district)
  }
  return { count: districts.size, districts: [...districts].sort() }
}

/** `outbreakId -> t0` for every real origin -- used only to attach a
 * real "last observed" date to a district row (Section 20: no per-source
 * date field is exposed by the current data contract, so each real
 * origin's own real t0 is the finest-grained honest date available). */
function buildOriginT0Lookup(originsWithSources) {
  const lookup = new Map()
  for (const origin of originsWithSources ?? []) {
    if (origin?.outbreakId && typeof origin.t0 === 'string') lookup.set(origin.outbreakId, origin.t0)
  }
  return lookup
}

/**
 * Top-N real districts by real, deduplicated observed-record count,
 * descending (ties broken alphabetically for determinism). A district
 * with no real records never appears -- no filler rows are ever added to
 * reach `topN`. `lastObserved` is the most recent real t0 among the real
 * origins whose eligibility window covers a record in that district.
 * `aggregatedSources` is the real FeatureCollection
 * `buildDeduplicatedNationalSources` returns.
 */
export function buildMostAffectedAreas(aggregatedSources, districtFeatureCollection, originsWithSources, { topN = 5 } = {}) {
  const t0ByOutbreakId = buildOriginT0Lookup(originsWithSources)
  const byDistrict = new Map()

  for (const feature of aggregatedSources?.features ?? []) {
    const district = resolveDistrictForFeature(feature, districtFeatureCollection)
    if (!district) continue

    const outbreakIds = Array.isArray(feature.properties?.outbreakIds) ? feature.properties.outbreakIds : []
    const knownDates = outbreakIds.map((id) => t0ByOutbreakId.get(id)).filter((d) => typeof d === 'string' && d)
    const featureDate = knownDates.length > 0 ? knownDates.reduce((a, b) => (a > b ? a : b)) : null

    const entry = byDistrict.get(district) ?? { district, records: 0, lastObserved: null }
    entry.records += 1
    if (featureDate && (!entry.lastObserved || featureDate > entry.lastObserved)) {
      entry.lastObserved = featureDate
    }
    byDistrict.set(district, entry)
  }

  return [...byDistrict.values()]
    .sort((a, b) => b.records - a.records || a.district.localeCompare(b.district))
    .slice(0, topN)
}
