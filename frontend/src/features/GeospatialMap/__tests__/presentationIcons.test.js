import { describe, expect, it } from 'vitest'
import {
  DIRECTION_ICON_ID,
  DIRECTION_ICON_SIZE,
  SOURCE_ICON_ID,
  SOURCE_ICON_SIZE,
  buildDirectionArrowImage,
  buildSourceMarkerImage,
} from '../components/presentationIcons'

describe('11B1-ICON-01: source icon image definition is deterministic', () => {
  it('two independent calls produce byte-identical pixel data', () => {
    const a = buildSourceMarkerImage()
    const b = buildSourceMarkerImage()
    expect(Array.from(a.data)).toEqual(Array.from(b.data))
    expect(a.width).toBe(SOURCE_ICON_SIZE)
    expect(a.height).toBe(SOURCE_ICON_SIZE)
  })

  it('requires no network/DOM/canvas -- a plain RGBA Uint8ClampedArray MapLibre addImage() accepts directly', () => {
    const image = buildSourceMarkerImage()
    expect(image.data).toBeInstanceOf(Uint8ClampedArray)
    expect(image.data.length).toBe(image.width * image.height * 4)
    expect(SOURCE_ICON_ID).toBeTruthy()
  })

  it('is visually distinct in SHAPE (a diamond, not a filled square) -- the image corners stay empty while the mid-edge points are filled', () => {
    const size = 16
    const image = buildSourceMarkerImage(size)
    const cornerAlpha = image.data[(0 * size + 0) * 4 + 3]
    const cx = Math.round((size - 1) / 2)
    const topMidEdgeAlpha = image.data[(1 * size + cx) * 4 + 3] // near the diamond's top vertex
    expect(cornerAlpha).toBe(0) // a filled square would light up the corner; a diamond does not
    expect(topMidEdgeAlpha).toBeGreaterThan(0)
  })
})

describe('11B1-ICON-02: direction icon is north-facing at base orientation', () => {
  it('the tip (top rows) is narrower than the base (bottom rows) -- points up, not down/sideways', () => {
    const size = DIRECTION_ICON_SIZE
    const image = buildDirectionArrowImage(size)
    function rowFilledWidth(y) {
      let count = 0
      for (let x = 0; x < size; x += 1) {
        if (image.data[(y * size + x) * 4 + 3] > 0) count += 1
      }
      return count
    }
    const tipWidth = rowFilledWidth(2)
    const baseWidth = rowFilledWidth(size - 3)
    expect(tipWidth).toBeLessThan(baseWidth)
  })

  it('is horizontally symmetric about the vertical center axis (an unrotated upright arrow)', () => {
    const size = DIRECTION_ICON_SIZE
    const image = buildDirectionArrowImage(size)
    // the shape's true center is (size-1)/2 -- reflecting x -> (size-1-x)
    // is an exact symmetry regardless of whether that center falls on an
    // integer pixel index.
    for (let y = 0; y < size; y += 1) {
      for (let x = 0; x < size; x += 1) {
        const alpha = image.data[(y * size + x) * 4 + 3]
        const mirroredAlpha = image.data[(y * size + (size - 1 - x)) * 4 + 3]
        expect(alpha > 0).toBe(mirroredAlpha > 0)
      }
    }
  })

  it('requires no network/DOM/canvas', () => {
    const image = buildDirectionArrowImage()
    expect(image.data).toBeInstanceOf(Uint8ClampedArray)
    expect(DIRECTION_ICON_ID).toBeTruthy()
  })
})
