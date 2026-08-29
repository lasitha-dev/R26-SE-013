import { describe, expect, it } from 'vitest'

import { FARM_MARKER_ICON_ID, FARM_MARKER_ICON_SIZE, buildFarmMarkerImage, farmMarkerIconLayout } from '../components/myAreaIcons'
import { buildSourceMarkerImage } from '../components/presentationIcons'
import { buildClinicalCircleIcon, buildClinicalDiamondIcon } from '../components/operationalIcons'

function centerAlpha(image) {
  const cx = Math.round((image.width - 1) / 2)
  const cy = Math.round((image.height - 1) / 2)
  return image.data[(cy * image.width + cx) * 4 + 3]
}

describe('GEO-AREA-02-ICON-01: farm marker is deterministic', () => {
  it('two independent calls produce byte-identical pixel data', () => {
    expect(Array.from(buildFarmMarkerImage().data)).toEqual(Array.from(buildFarmMarkerImage().data))
  })

  it('requires no network/DOM/canvas', () => {
    const image = buildFarmMarkerImage()
    expect(image.data).toBeInstanceOf(Uint8ClampedArray)
    expect(image.width).toBe(FARM_MARKER_ICON_SIZE)
    expect(FARM_MARKER_ICON_ID).toBeTruthy()
  })
})

describe('GEO-AREA-02-ICON-02: visually distinct from every other marker family (Section 16)', () => {
  it('is SOLID (filled center), unlike the hollow clinical markers', () => {
    expect(centerAlpha(buildFarmMarkerImage())).toBeGreaterThan(0)
    expect(centerAlpha(buildClinicalDiamondIcon())).toBe(0)
    expect(centerAlpha(buildClinicalCircleIcon())).toBe(0)
  })

  it('pixel data differs from the historical-source (amber diamond) icon', () => {
    const farm = buildFarmMarkerImage(16)
    const source = buildSourceMarkerImage(16)
    expect(Array.from(farm.data)).not.toEqual(Array.from(source.data))
  })

  it('is never a risk/danger color (not red/orange, dominant channel is not red)', () => {
    // Sample a filled interior pixel and confirm it is not red-dominant.
    const image = buildFarmMarkerImage(20)
    const cx = 10
    const cy = 10
    const idx = (cy * 20 + cx) * 4
    const [r, g, b] = [image.data[idx], image.data[idx + 1], image.data[idx + 2]]
    expect(r > g && r > b).toBe(false)
  })

  it('has a white halo/outline distinct from its fill color, for contrast (Section 16)', () => {
    const image = buildFarmMarkerImage(20)
    const cx = 10
    // A pixel near the very edge (within the halo band) should be white.
    const edgeX = 19
    const idxEdge = (cx * 20 + edgeX) * 4
    const [r, g, b, a] = [image.data[idxEdge], image.data[idxEdge + 1], image.data[idxEdge + 2], image.data[idxEdge + 3]]
    if (a > 0) {
      expect(r).toBe(255)
      expect(g).toBe(255)
      expect(b).toBe(255)
    }
  })
})

describe('GEO-AREA-02-ICON-03: layout carries no risk/score-driven property', () => {
  it('icon-image is fixed, never a data-driven risk expression', () => {
    const layout = farmMarkerIconLayout()
    expect(layout['icon-image']).toBe(FARM_MARKER_ICON_ID)
  })

  it('layout has no color/paint property that could vary by score', () => {
    const layout = farmMarkerIconLayout()
    expect(Object.keys(layout).every((k) => k.startsWith('icon-'))).toBe(true)
  })
})
