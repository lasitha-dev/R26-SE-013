/**
 * GEO30B Section 16/17/19: real Sri Lanka district (ADM2) geometry --
 * see `data/ATTRIBUTION.md` for the dataset's source/license. Pure
 * functions only (name matching + bounds extraction); the actual fetch
 * lives in `context/useDistrictGeometry.js`.
 *
 * `districtNameMatches` mirrors the backend's own
 * `host_operational_adapter.py::district_matches` normalization exactly
 * (case-insensitive substring, e.g. real vet field `"Matara"` inside the
 * real geoBoundaries field `"Matara District"`) so the SAME vet-district
 * string resolves consistently on both sides -- never a second,
 * divergent matching rule.
 */

import { isPointInPolygonRing } from './geo'

/**
 * GEO-MY-AREA-FINAL-PASS: canonical district DISPLAY-NAME normalization.
 *
 * Real `location_district` values on a farm record are NOT a clean
 * district name -- verified directly from the backend's own documented
 * real example (`host_operational_adapter.py::district_matches`
 * docstring): `"8.4162, 80.0261 (Anuradhapura District)"`. The backend's
 * OWN `district_matches` handles this correctly by checking the SHORT
 * vet district substring INSIDE that long raw string
 * (`vet_district in farm_location_district`) -- but this file's
 * `districtNameMatches` above checks the OPPOSITE direction (whether the
 * real ADM2 `shapeName` -- always short, e.g. "Matara District" --
 * contains `vetDistrict`), which can never be true if `vetDistrict`
 * itself is still the long coordinate-prefixed raw string. Passing that
 * raw value straight into `findDistrictFeature` therefore silently never
 * matches (not an error, not a crash -- just a permanently-null
 * `districtFeature`), and showing it verbatim as a primary UI label
 * reads as debug output, not a real area name.
 *
 * This extracts the real district name from either shape -- the raw
 * `"<lat>, <lon> (<District> District)"` form, or an already-clean
 * `"<District>"`/`"<District> District"`/`"<DISTRICT> DISTRICT"` (this
 * codebase's own test-data convention) -- into one short, Title-Case,
 * no-suffix canonical form (e.g. "Matara"). That form is BOTH a safe
 * primary display label and a still-valid `districtNameMatches` input
 * (a genuine substring of the real ADM2 `shapeName`: "matara" is inside
 * "matara district"). Never invents a district from coordinates alone --
 * a raw value with no parenthesized suffix and no real content is
 * `null`, same as today.
 */
export function normalizeDistrictDisplayName(raw) {
  if (typeof raw !== 'string' || !raw.trim()) return null
  const parenMatch = raw.match(/\(([^()]+)\)\s*$/)
  const candidate = (parenMatch ? parenMatch[1] : raw).trim()
  if (!candidate) return null
  const titleCased = candidate
    .split(/\s+/)
    .map((word) => (word.length === 0 ? word : word[0].toUpperCase() + word.slice(1).toLowerCase()))
    .join(' ')
  return titleCased.replace(/\s+District$/i, '').trim() || null
}

export function districtNameMatches(vetDistrict, shapeName) {
  if (!vetDistrict || !shapeName) return false
  const normalizedVet = vetDistrict.trim().toLowerCase()
  const normalizedShape = shapeName.trim().toLowerCase()
  if (!normalizedVet || !normalizedShape) return false
  return normalizedShape.includes(normalizedVet)
}

/** Returns the one real `Feature` whose `properties.shapeName` matches
 * `vetDistrict`, or `null` -- never a fabricated/synthesized feature,
 * never more than one match assumed (`find` takes the first). */
export function findDistrictFeature(featureCollection, vetDistrict) {
  if (!featureCollection || !Array.isArray(featureCollection.features)) return null
  if (!vetDistrict) return null
  return featureCollection.features.find((f) => districtNameMatches(vetDistrict, f?.properties?.shapeName)) ?? null
}

function eachCoordinate(geometry, visit) {
  if (!geometry) return
  const { type, coordinates } = geometry
  if (type === 'Polygon') {
    for (const ring of coordinates) for (const [lng, lat] of ring) visit(lng, lat)
  } else if (type === 'MultiPolygon') {
    for (const polygon of coordinates) for (const ring of polygon) for (const [lng, lat] of ring) visit(lng, lat)
  }
}

/** Real bounds `[[minLng,minLat],[maxLng,maxLat]]` derived directly from
 * the district polygon's own real coordinates -- never a guessed/padded
 * box, never the national/Sri-Lanka-wide fallback. Returns `null` only
 * for a missing/empty geometry (never a fabricated box). */
export function computeFeatureBounds(feature) {
  if (!feature?.geometry) return null
  let minLng = Infinity
  let minLat = Infinity
  let maxLng = -Infinity
  let maxLat = -Infinity
  eachCoordinate(feature.geometry, (lng, lat) => {
    if (lng < minLng) minLng = lng
    if (lng > maxLng) maxLng = lng
    if (lat < minLat) minLat = lat
    if (lat > maxLat) maxLat = lat
  })
  if (!Number.isFinite(minLng) || !Number.isFinite(minLat) || !Number.isFinite(maxLng) || !Number.isFinite(maxLat)) {
    return null
  }
  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ]
}

/**
 * URGENT-MATARA-REAL-FILTER: real point-in-district containment, for
 * filtering database-backed origin/source coordinates -- never for
 * rendering a map on this page. Reuses `isPointInPolygonRing` (the SAME
 * tested ray-casting primitive `lsdOutbreakAdapter.js::
 * computeRelevantOrigins` already uses for Page 1's area-relevance rule)
 * against every OUTER ring of the district's real geometry -- holes are
 * not evaluated, matching `isPointInPolygonRing`'s own documented scope
 * ("no holes needed for district boundaries"). Supports both `Polygon`
 * and `MultiPolygon` (a real ADM2 district can be either shape). Returns
 * `false` for any missing/malformed input -- never guesses containment.
 */
export function isPointInsideDistrictFeature(coordinates, feature) {
  if (!Array.isArray(coordinates) || coordinates.length !== 2) return false
  const geometry = feature?.geometry
  if (!geometry) return false
  if (geometry.type === 'Polygon') {
    const outerRing = geometry.coordinates?.[0]
    return Array.isArray(outerRing) ? isPointInPolygonRing(coordinates, outerRing) : false
  }
  if (geometry.type === 'MultiPolygon') {
    return (geometry.coordinates ?? []).some((polygon) => {
      const outerRing = polygon?.[0]
      return Array.isArray(outerRing) && isPointInPolygonRing(coordinates, outerRing)
    })
  }
  return false
}

/**
 * URGENT-MATARA-REAL-FILTER: filters `useNationalOutbreaks`' real
 * `originsWithSources` list (`{ outbreakId, country, t0, sourceCount,
 * sourcesFeatureCollection }`, already fetched from the real backend --
 * never a second/duplicated network call here) down to only the origins
 * with at least one real source point inside `districtFeature`. Mirrors
 * `lsdOutbreakAdapter.js::computeRelevantOrigins`'s "any real source
 * point inside the polygon" rule, but disease-neutral (works for both
 * LSD's `/analysis/{id}/sources` geometry and FMD's `/origins/{id}/
 * trigger-sources` geometry, since both already arrive in the SAME
 * `sourcesFeatureCollection` shape) and returns the full real origin
 * object (never just an id/reason pair), since Page 3's Matara KPIs/
 * chart/table need the real `t0`/`sourceCount` values too. A missing
 * `districtFeature` (not yet resolved, or the real dataset had no match)
 * returns an empty list -- never "all origins", which would silently
 * mislabel national data as Matara-specific.
 */
export function filterOriginsInsideDistrict(originsWithSources, districtFeature) {
  if (!districtFeature || !Array.isArray(originsWithSources)) return []
  return originsWithSources.filter((origin) => {
    const features = origin?.sourcesFeatureCollection?.features ?? []
    return features.some((f) => isPointInsideDistrictFeature(f?.geometry?.coordinates, districtFeature))
  })
}
