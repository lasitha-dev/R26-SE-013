import { describe, expect, it } from 'vitest'

import { districtSnapshotSummary } from '../adapters/myAreaFarmIntelligence'

const timeline = (row) => ({ as_of: '2026-08-31', district_summaries: [{ district: 'Kegalle', district_area_km2: 1662.1, ...row }], risk_zones: { features: [] } })

describe('district relative-zone summary', () => {
  it('uses the backend centroid max_tier when present', () => {
    const s = districtSnapshotSummary(timeline({ max_tier: 'high', tier_area_km2: { lower: 1, moderate: 0, high: 2, highest: 0 }, scored_area_km2: 3 }), 'Kegalle')
    expect(s.maxTier).toBe('high')
    expect(s.maxTierFromEdgeArea).toBe(false)
  })

  it('falls back to the highest tier with backend scored area when only the district edge is reached', () => {
    const s = districtSnapshotSummary(timeline({ max_tier: null, tier_area_km2: { lower: 0.339, moderate: 0, high: 0, highest: 0 }, scored_area_km2: 0.339 }), 'Kegalle')
    expect(s.maxTier).toBe('lower')
    expect(s.maxTierFromEdgeArea).toBe(true)
  })

  it('reports no tier (never invents one) when there is no scored land inside', () => {
    const s = districtSnapshotSummary(timeline({ max_tier: null, tier_area_km2: { lower: 0, moderate: 0, high: 0, highest: 0 }, scored_area_km2: 0 }), 'Kegalle')
    expect(s.maxTier).toBeNull()
  })
})
