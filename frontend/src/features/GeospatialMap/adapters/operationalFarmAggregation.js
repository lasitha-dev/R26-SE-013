/**
 * GEO26B Section 8/9: groups already-normalized, already-window-filtered
 * verified clinical contexts (`operationalContextAdapter.js`'s
 * `clinicalContexts`) into ONE row per real farm, so the map never draws
 * more than one marker per farm+disease combination. Pure function, no
 * Mongo access, no aggregate collection -- this is a presentation/read
 * model only, computed fresh from the caller-supplied list every time
 * (Section 8: "Do NOT create an aggregate Mongo collection").
 *
 * Group key is `farmId + disease` (Section 8's exact rule) so a farm
 * with both a verified LSD and a verified FMD case never merges into one
 * count -- defensive even though callers today pre-filter to a single
 * selected disease before calling this.
 */
import { classifyRecency, RECENT_MARKER_THRESHOLD_DAYS } from './observationWindow'
import { parseVerificationTime } from './verificationTime'

function groupKey(context) {
  return `${context.farmId}::${context.disease}`
}

export function aggregateClinicalContextsByFarm(clinicalContexts, nowMs = Date.now()) {
  const groups = new Map()

  for (const context of clinicalContexts) {
    const key = groupKey(context)
    let group = groups.get(key)
    if (!group) {
      group = {
        farmId: context.farmId,
        disease: context.disease,
        latitude: context.latitude,
        longitude: context.longitude,
        locationDistrict: context.locationDistrict,
        // GEO29A Phase 5: every case in one farm+disease group shares the
        // same farm, so this is a farm-level property -- `!== false`
        // matches `operationalContextAdapter.js`'s own default-true rule
        // when a context predates this field.
        personallyAssigned: context.personallyAssigned !== false,
        caseIds: [],
        verificationTimes: [],
      }
      groups.set(key, group)
    }
    group.caseIds.push(context.caseId)
    group.verificationTimes.push(context.verificationTime ?? null)
  }

  const result = []
  for (const group of groups.values()) {
    // Deterministic ordering (Section 25's convention): caseIds sorted,
    // verificationTimes sorted newest-first with unparseable/missing
    // values pushed to the end (never treated as "most recent").
    const caseIds = [...group.caseIds].sort()
    const verificationTimes = [...group.verificationTimes].sort((a, b) => {
      const da = parseVerificationTime(a)
      const db = parseVerificationTime(b)
      if (!da && !db) return 0
      if (!da) return 1
      if (!db) return -1
      return db.getTime() - da.getTime()
    })
    const latestVerificationTime = verificationTimes.find((t) => parseVerificationTime(t)) ?? null

    result.push({
      farmId: group.farmId,
      disease: group.disease,
      latitude: group.latitude,
      longitude: group.longitude,
      locationDistrict: group.locationDistrict,
      personallyAssigned: group.personallyAssigned,
      caseCount: caseIds.length,
      caseIds,
      verificationTimes,
      latestVerificationTime,
      recencyTier: classifyRecency(latestVerificationTime, nowMs),
    })
  }

  return result.sort((a, b) => {
    if (a.farmId !== b.farmId) return a.farmId < b.farmId ? -1 : 1
    return a.disease < b.disease ? -1 : a.disease > b.disease ? 1 : 0
  })
}

/**
 * GEO-LIVE-FINAL-PROOF-09: a cheap, stable semantic fingerprint of an
 * already-computed farm-group list -- mirrors `MapLibreCanvas.jsx`'s own
 * `pulseKeySignature` idiom (sorted, joined real identifiers) rather than
 * `JSON.stringify`-ing the whole structure. Built ONLY from fields that
 * actually drive the rendered marker (`operationalMarkerLayer.js`):
 * `farmId`/`disease` (which marker), `caseCount` (icon size),
 * `latestVerificationTime` (when a case is added/re-verified), and
 * `recencyTier` (icon opacity -- DERIVED from wall-clock time, so it can
 * flip from "recent" to "older" with no underlying data change at all;
 * omitting it would let a marker's opacity go stale). Two calls that
 * return the same string are safe to treat as "no visible change" -- a
 * caller can keep its previous FeatureCollection reference and skip
 * `source.setData()` entirely.
 */
export function operationalFarmGroupsSignature(farmGroups) {
  return farmGroups
    .map((g) => `${g.farmId}::${g.disease}::${g.caseCount}::${g.latestVerificationTime ?? ''}::${g.recencyTier}`)
    .sort()
    .join('|')
}

export { RECENT_MARKER_THRESHOLD_DAYS }
