import { describe, expect, it } from 'vitest'

import { basemapPlaceSourceId, buildTrajectoryLabels, nearestMappedPlace } from '../components/trajectoryLabels'

const place = (name, cls, lon, lat, extra = {}) => ({ geometry: { type: 'Point', coordinates: [lon, lat] }, properties: { class: cls, name, ...extra } })
const fakeMap = (features) => ({
  getStyle: () => ({ sources: { openmaptiles: { type: 'vector' }, other: { type: 'geojson' } } }),
  querySourceFeatures: (sourceId, { sourceLayer }) => (sourceId === 'openmaptiles' && sourceLayer === 'place' ? features : []),
})

describe('trajectory place labels (real basemap places only)', () => {
  it('uses the OpenMapTiles vector source of the basemap', () => {
    expect(basemapPlaceSourceId(fakeMap([]))).toBe('openmaptiles')
    expect(basemapPlaceSourceId({ getStyle: () => ({ sources: { a: { type: 'raster' } } }) })).toBeNull()
  })

  it('returns the nearest populated place within the limit, English name first', () => {
    const map = fakeMap([
      place('අකුරැස්ස', 'town', 80.476, 6.098, { 'name:en': 'Akuressa' }),
      place('Far Town', 'town', 80.9, 6.5),
      place('Some Hamlet', 'hamlet', 80.47, 6.09), // hamlets are not used
      place('Peak', 'peak', 80.47, 6.09),
    ])
    expect(nearestMappedPlace(map, [80.47, 6.09])).toMatchObject({ name: 'Akuressa' })
    expect(nearestMappedPlace(map, [81.5, 7.5])).toBeNull() // nothing within 8 km: no name is invented
  })

  it('labels each path front with its day and place; nothing on Day 0; no-direction sources say so', () => {
    const fronts = { features: [
      { geometry: { type: 'Point', coordinates: [80.47, 6.09] }, properties: { day: 7, bearingDeg: 80, sourceId: 'S1' } },
      { geometry: { type: 'Point', coordinates: [81.5, 7.5] }, properties: { day: 7, bearingDeg: 260, sourceId: 'S2' } },
      { geometry: { type: 'Point', coordinates: [80.5, 5.95] }, properties: { day: 0, bearingDeg: 80, sourceId: 'S1' } }, // Day 0: never labelled
    ] }
    const origins = { features: [
      { geometry: { type: 'Point', coordinates: [80.5, 5.95] }, properties: { day: 7, bearingDeg: 80, sourceId: 'S1' } }, // has a path: no origin label
      { geometry: { type: 'Point', coordinates: [80.7, 6.9] }, properties: { day: 7, bearingDeg: null, sourceId: 'S3' } },
      { geometry: { type: 'Point', coordinates: [80.7, 6.9] }, properties: { day: 0, bearingDeg: null, sourceId: 'S4' } }, // Day 0: nothing
    ] }
    const findPlace = ([lon]) => (lon === 80.47 ? { name: 'Akuressa' } : null)
    const labels = buildTrajectoryLabels({ fronts, origins, findPlace }).features.map((f) => [f.properties.sourceId, f.properties.label])
    expect(labels).toEqual([['S1', 'Day 7 · near Akuressa'], ['S2', 'Day 7 · heading W'], ['S3', 'Insufficient directional evidence']])
  })
})
