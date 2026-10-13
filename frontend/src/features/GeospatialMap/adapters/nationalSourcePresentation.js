/**
 * GEO33B Section 7: PRESENTATION AGGREGATION for the national observed
 * (historical/scientific) source layer.
 *
 * Deliberately NOT clustering. This is not ST-DBSCAN, not a spatial
 * cluster model, and must never be labelled as one anywhere in the UI --
 * `services/stdbscan` on the backend is real but unwired, and the map's
 * own `Clusters` mode is honestly disabled for exactly that reason
 * (`ModeToolbar.jsx`). What happens here is purely a rendering concern:
 * several FeatureCollection rows that occupy the SAME real coordinate are
 * drawn as ONE marker instead of N invisible ones stacked on top of each
 * other. No coordinate is moved, averaged, snapped, or invented; the
 * marker sits on a real record's own real coordinate.
 *
 * WHY THIS IS NEEDED (real, reproduced evidence, 2026-08-30):
 * `buildNationalSourcesFeatureCollection` merges every origin's
 * `/analysis/{id}/sources` response. That endpoint returns each origin's
 * ELIGIBLE source set, and eligibility is a WINDOW
 * (`services/source_selector.py`: `t0 - active_window_days <= date <= t0`,
 * with `ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT = 14`), not a same-day
 * bucket. So ONE physical historical record is legitimately returned again
 * under every origin whose window still contains it. For the real Sri
 * Lanka LSD corpus (6 model-candidate records, 5 origins) that produces 9
 * merged rows over only 6 distinct real records/locations -- 3 records are
 * each returned twice. The "9 features but I only see 6 markers"
 * observation was therefore CORRECT BEHAVIOR being misread: 6 is the real
 * number of observed LSD locations; 9 was a transport artifact of
 * overlapping eligibility windows, never 9 real outbreak points.
 *
 * Two concrete bugs the raw 9-row collection caused, both fixed by
 * aggregating here:
 *  1. `MapLibreCanvas.jsx` adds the national source with
 *     `promoteId: 'source_id'`. Two rows sharing one `source_id` collide
 *     on that promoted feature id, so the selection halo/dim
 *     `setFeatureState` loop wrote conflicting values for the same id
 *     depending on iteration order.
 *  2. Every duplicate row painted a second identical icon at the exact
 *     same pixel, costing render work for zero visible information.
 *
 * `stackCount` counts DISTINCT REAL SOURCE RECORDS at a location -- never
 * the number of merged rows. A record returned twice by two overlapping
 * eligibility windows is ONE observation, and reporting "2" there would be
 * a fabricated count. `mergedFeatureCount` keeps the raw row count for
 * diagnostics only; nothing user-facing reads it as an observation count.
 */

/** ~5 decimal places is ~1.1 m at the equator -- far below any distinction
 * these WAHIS/FAO records actually carry (their own `gps_quality` is a
 * coarse EXACT/UNKNOWN label), so two rows agreeing to 5 dp are the same
 * physical place, not two neighbouring places being conflated. */
const COORDINATE_KEY_DECIMALS = 5

export function coordinateKey(longitude, latitude) {
  return `${Number(longitude).toFixed(COORDINATE_KEY_DECIMALS)},${Number(latitude).toFixed(COORDINATE_KEY_DECIMALS)}`
}

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

/**
 * Collapses a merged national-sources FeatureCollection to ONE feature per
 * real coordinate.
 *
 * Every returned feature:
 *  - keeps the FIRST contributing row's real `geometry` verbatim (never a
 *    centroid/average -- an averaged point would be a coordinate no real
 *    record has);
 *  - keeps that row's real `properties` verbatim (`source_id`,
 *    `availability_quality`, `gps_quality`, ...), so the existing popup and
 *    the existing `promoteId: 'source_id'` feature-state contract keep
 *    working unchanged;
 *  - ADDS `sourceIds` / `outbreakIds` (every distinct real id that
 *    contributed), `stackCount` (distinct real source records here) and
 *    `mergedFeatureCount` (raw rows merged, diagnostics only).
 *
 * A row with a missing/non-finite coordinate is DROPPED, never repaired --
 * matching `operationalContextAdapter.js`'s own "never invent a
 * coordinate" rule.
 */
export function aggregateNationalSourcesByLocation(featureCollection) {
  const groups = new Map()

  for (const feature of featureCollection?.features ?? []) {
    const coordinates = feature?.geometry?.coordinates
    if (!Array.isArray(coordinates) || coordinates.length < 2) continue
    const [longitude, latitude] = coordinates
    if (!isFiniteNumber(longitude) || !isFiniteNumber(latitude)) continue

    const key = coordinateKey(longitude, latitude)
    let group = groups.get(key)
    if (!group) {
      group = { key, first: feature, sourceIds: new Set(), outbreakIds: new Set(), mergedFeatureCount: 0 }
      groups.set(key, group)
    }
    group.mergedFeatureCount += 1
    if (feature.properties?.source_id) group.sourceIds.add(feature.properties.source_id)
    if (feature.properties?.outbreakId) group.outbreakIds.add(feature.properties.outbreakId)
  }

  const features = []
  for (const group of groups.values()) {
    const sourceIds = Array.from(group.sourceIds).sort()
    const outbreakIds = Array.from(group.outbreakIds).sort()
    features.push({
      ...group.first,
      properties: {
        ...group.first.properties,
        presentationKey: group.key,
        sourceIds,
        outbreakIds,
        // Distinct REAL observed records at this exact coordinate. `1` for
        // every location in the real Sri Lanka LSD corpus today -- a value
        // above 1 only ever comes from genuinely different `source_id`s
        // sharing a coordinate, never from eligibility-window repetition.
        stackCount: sourceIds.length,
        mergedFeatureCount: group.mergedFeatureCount,
      },
    })
  }

  // Deterministic ordering by the real coordinate key (this feature's
  // convention everywhere else: never Mongo/network arrival order).
  features.sort((a, b) => (a.properties.presentationKey < b.properties.presentationKey ? -1 : 1))
  return { type: 'FeatureCollection', features }
}

/** True when this aggregated feature belongs to `outbreakId` -- the
 * multi-origin-aware replacement for the old
 * `properties.outbreakId === selectedOutbreakId` equality check, which
 * silently failed for a record eligible under more than one real origin. */
export function featureBelongsToOutbreak(feature, outbreakId) {
  if (outbreakId == null) return false
  const outbreakIds = feature?.properties?.outbreakIds
  if (Array.isArray(outbreakIds)) return outbreakIds.includes(outbreakId)
  return feature?.properties?.outbreakId === outbreakId
}

/**
 * MapLibre paint for the "more than one distinct real observed record at
 * this exact coordinate" indicator ring. Deliberately NOT a text badge:
 * this feature's `visualLayerStructural.test.js` forbids any
 * `text-field`/`text-font` dependency in the map layer specs (the
 * token-free fallback basemap declares no `glyphs` URL), so the exact
 * count is surfaced in `SourcePopup.jsx` instead and the ring only signals
 * "there is more than one here". Fully invisible at `stackCount <= 1`, so
 * a dataset with no genuine co-location -- like the real Sri Lanka LSD
 * corpus today -- shows nothing at all rather than a decorative ring.
 */
export function nationalStackIndicatorPaint() {
  return {
    'circle-color': 'transparent',
    'circle-radius': ['step', ['get', 'stackCount'], 0, 2, 13, 4, 16],
    'circle-stroke-width': ['step', ['get', 'stackCount'], 0, 2, 1.5],
    'circle-stroke-color': '#fca5a5',
    'circle-stroke-opacity': ['step', ['get', 'stackCount'], 0, 2, 0.9],
  }
}
