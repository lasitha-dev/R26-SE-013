import { describe, expect, it } from 'vitest'

import {
  CLINICAL_CIRCLE_ICON_ID,
  CLINICAL_DIAMOND_ICON_ID,
  CLINICAL_ICON_SIZE,
  CLINICAL_MARKER_COLOR_HEX,
  buildClinicalCircleIcon,
  buildClinicalDiamondIcon,
} from '../components/operationalIcons'

// Section 9: the risk red/orange/amber/yellow/green family used
// elsewhere in this feature -- none of these may ever be the clinical
// marker color.
const RISK_FAMILY_HEXES = ['#dc2626', '#3b82f6', '#f59e0b', '#9ca3af', '#60a5fa', '#10b981', '#14b8a6']

function centerAlpha(image) {
  const cx = Math.round((image.width - 1) / 2)
  const cy = Math.round((image.height - 1) / 2)
  return image.data[(cy * image.width + cx) * 4 + 3]
}

describe('GEO-INT-03-ICON-01: clinical icons are deterministic', () => {
  it('two independent calls produce byte-identical pixel data for both shapes', () => {
    expect(Array.from(buildClinicalDiamondIcon().data)).toEqual(Array.from(buildClinicalDiamondIcon().data))
    expect(Array.from(buildClinicalCircleIcon().data)).toEqual(Array.from(buildClinicalCircleIcon().data))
  })

  it('requires no network/DOM/canvas -- plain RGBA Uint8ClampedArray MapLibre addImage() accepts directly', () => {
    const image = buildClinicalDiamondIcon()
    expect(image.data).toBeInstanceOf(Uint8ClampedArray)
    expect(image.data.length).toBe(image.width * image.height * 4)
    expect(image.width).toBe(CLINICAL_ICON_SIZE)
    expect(CLINICAL_DIAMOND_ICON_ID).toBeTruthy()
    expect(CLINICAL_CIRCLE_ICON_ID).toBeTruthy()
    expect(CLINICAL_DIAMOND_ICON_ID).not.toBe(CLINICAL_CIRCLE_ICON_ID)
  })
})

describe('GEO-INT-03-ICON-02: LSD (diamond) and FMD (circle) shapes remain visually distinct', () => {
  it('diamond and circle icons of the same size produce different pixel data', () => {
    const diamond = buildClinicalDiamondIcon(20)
    const circle = buildClinicalCircleIcon(20)
    expect(Array.from(diamond.data)).not.toEqual(Array.from(circle.data))
  })

  it('both icons are HOLLOW -- the center pixel is fully transparent, not filled', () => {
    expect(centerAlpha(buildClinicalDiamondIcon())).toBe(0)
    expect(centerAlpha(buildClinicalCircleIcon())).toBe(0)
  })

  it('both icons have a visible outline band (some non-transparent pixels exist)', () => {
    const diamond = buildClinicalDiamondIcon()
    const circle = buildClinicalCircleIcon()
    const hasVisiblePixel = (image) => Array.from(image.data).some((_, i) => i % 4 === 3 && image.data[i] > 0)
    expect(hasVisiblePixel(diamond)).toBe(true)
    expect(hasVisiblePixel(circle)).toBe(true)
  })
})

describe('GEO-INT-03-ICON-03: clinical marker uses non-risk, restrained styling', () => {
  it('the clinical marker color is never one of the risk/amber/emerald/teal-reach-ring family colors used elsewhere', () => {
    expect(RISK_FAMILY_HEXES).not.toContain(CLINICAL_MARKER_COLOR_HEX.toLowerCase())
  })

  it('the clinical marker color is not a red/orange/amber/yellow hue (no risk implication)', () => {
    const hex = CLINICAL_MARKER_COLOR_HEX.replace('#', '')
    const r = parseInt(hex.slice(0, 2), 16)
    const g = parseInt(hex.slice(2, 4), 16)
    const b = parseInt(hex.slice(4, 6), 16)
    // A red/orange/amber/yellow risk hue always has red as the dominant
    // channel with blue clearly the weakest; this teal/mint tone must not.
    expect(r > g && r > b).toBe(false)
  })
})
