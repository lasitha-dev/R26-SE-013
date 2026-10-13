import { describe, expect, it } from 'vitest'
import { arrowTipOffset, shouldDrawArrow } from '../components/directionGeometry'

describe('11A-DIR-01: bearing null => no arrow', () => {
  it('returns false for null and undefined bearing', () => {
    expect(shouldDrawArrow(null)).toBe(false)
    expect(shouldDrawArrow(undefined)).toBe(false)
    expect(arrowTipOffset(null, 8)).toBeNull()
    expect(arrowTipOffset(undefined, 8)).toBeNull()
  })
})

describe('11A-DIR-02: bearing 0.0 => valid North arrow', () => {
  it('treats 0.0 as a real, drawable bearing (never falsy-skipped)', () => {
    expect(shouldDrawArrow(0.0)).toBe(true)
    const offset = arrowTipOffset(0.0, 8)
    expect(offset).not.toBeNull()
    // North = straight up on screen: dx ~ 0, dy negative (screen y grows downward)
    expect(offset.dx).toBeCloseTo(0, 6)
    expect(offset.dy).toBeCloseTo(-8, 6)
  })

  it('never uses bare truthiness on bearing (0.0 is falsy in JS but must still be drawn)', () => {
    const bearing = 0.0
    // eslint-disable-next-line no-constant-condition
    if (bearing) {
      throw new Error('bare truthiness check incorrectly treats 0.0 as falsy -- this branch proves the bug would exist if used')
    }
    expect(shouldDrawArrow(bearing)).toBe(true)
  })
})
