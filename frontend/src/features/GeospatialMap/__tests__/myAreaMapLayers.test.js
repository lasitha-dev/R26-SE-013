import { describe, expect, it } from 'vitest'

import { buildObservedCaseFeatures, scopePointFeaturesToDistrict, scopeRiskCellsToNominalReach } from '../adapters/myAreaMapLayers'

const DISTRICT = {
  type: 'Feature',
  properties: { shapeName: 'Matara District' },
  geometry: { type: 'Polygon', coordinates: [[[79.8, 5.8], [80.3, 5.8], [80.3, 6.3], [79.8, 6.3], [79.8, 5.8]]] },
}

function point(id, coordinates) {
  return { type: 'Feature', geometry: { type: 'Point', coordinates }, properties: { scientific_cell_id: id, risk: { raw_c0_score: 0.5 } } }
}

describe('My Area observed/scoped map layers', () => {
  it('never substitutes a farm coordinate for coordinate-free case records', () => {
    const result = buildObservedCaseFeatures([
      { caseId: 'C1', disease: 'LSD', latitude: null, longitude: null },
      { caseId: 'C2', disease: 'LSD' },
    ])
    expect(result).toEqual([])
  })

  it('renders only explicit genuine case coordinates and preserves metadata', () => {
    const result = buildObservedCaseFeatures([
      { caseId: 'C1', disease: 'LSD', semanticClass: 'VERIFIED_CLINICAL_CONTEXT', verificationTime: '2026-08-31 09:00:00', latitude: 6.05, longitude: 80.1 },
    ])
    expect(result).toHaveLength(1)
    expect(result[0].geometry.coordinates).toEqual([80.1, 6.05])
    expect(result[0].properties.caseId).toBe('C1')
  })

  it('rejects invalid explicit case coordinates instead of repairing them', () => {
    expect(buildObservedCaseFeatures([{ caseId: 'C1', disease: 'LSD', latitude: 999, longitude: 80 }])).toEqual([])
  })

  it('scopes genuine risk points to the real district geometry without changing properties', () => {
    const inside = point('inside', [80.05, 6.05])
    const outside = point('outside', [81, 7])
    const scoped = scopePointFeaturesToDistrict([inside, outside], DISTRICT)
    expect(scoped).toEqual([inside])
    expect(scoped[0].properties.risk.raw_c0_score).toBe(0.5)
  })

  it('exposes only reach-intersecting cells for the selected real reach and leaves the source score unchanged', () => {
    const near = point('near', [80.01, 6])
    const far = point('far', [80.5, 6.5])
    const scoped = scopeRiskCellsToNominalReach([near, far], [[80, 6]], 5)
    expect(scoped).toEqual([near])
    expect(scoped[0].properties.risk.raw_c0_score).toBe(0.5)
  })

  it('D0 and unavailable reach highlight no future cells', () => {
    const cell = point('cell', [80.01, 6])
    expect(scopeRiskCellsToNominalReach([cell], [[80, 6]], null)).toEqual([])
    expect(scopeRiskCellsToNominalReach([cell], [], 5)).toEqual([])
  })
})
