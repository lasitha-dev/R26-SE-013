import { describe, expect, it } from 'vitest'

import { isPointInPolygonRing } from '../adapters/geo'

const SQUARE_RING = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
  [0, 0],
]

describe('geo', () => {
  it('isPointInPolygonRing: inside/outside/vertex-adjacent cases', () => {
    expect(isPointInPolygonRing([0.5, 0.5], SQUARE_RING)).toBe(true)
    expect(isPointInPolygonRing([2, 2], SQUARE_RING)).toBe(false)
    expect(isPointInPolygonRing([0.01, 0.01], SQUARE_RING)).toBe(true)
  })
})
