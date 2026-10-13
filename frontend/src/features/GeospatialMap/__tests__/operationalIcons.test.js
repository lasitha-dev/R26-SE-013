import { describe, expect, it } from 'vitest'

import {
  CLINICAL_CIRCLE_ICON_ID,
  CLINICAL_DIAMOND_ICON_ID,
  CLINICAL_ICON_SIZE,
  CLINICAL_MARKER_COLOR_HEX,
  buildClinicalCircleIcon,
  buildClinicalDiamondIcon,
} from '../components/operationalIcons'

// GEO31A Section 2/10: the SCIENTIFIC RISK gradient family used by
// `mapLibreAdapter.js`'s cell coloring -- distinct from the flat
// red-500 this module now shares with `presentationIcons.js`'s
// historical SOURCE_FILL (both mean "a real observed event", never a
// risk score). `#dc2626` (red-600) is deliberately excluded here: it is
// the risk gradient's OWN high-end red, close enough to this module's
// red-500 that asserting non-membership would be testing shade, not
// meaning -- the real firewall is "never a risk-gradient color", which
// the remaining non-red entries already cover.
const RISK_FAMILY_HEXES = ['#3b82f6', '#f59e0b', '#9ca3af', '#60a5fa', '#10b981', '#14b8a6']

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

  it('GEO31A Section 2: both icons have a SOLID, always-visible center -- the center pixel is fully opaque, never transparent (the whole marker must never blink off)', () => {
    expect(centerAlpha(buildClinicalDiamondIcon())).toBe(255)
    expect(centerAlpha(buildClinicalCircleIcon())).toBe(255)
  })

  it('both icons have a visible ring band distinct from the core fill (some non-transparent pixels exist)', () => {
    const diamond = buildClinicalDiamondIcon()
    const circle = buildClinicalCircleIcon()
    const hasVisiblePixel = (image) => Array.from(image.data).some((_, i) => i % 4 === 3 && image.data[i] > 0)
    expect(hasVisiblePixel(diamond)).toBe(true)
    expect(hasVisiblePixel(circle)).toBe(true)
  })
})

describe('GEO31A Section 2/10: clinical marker is a steady RED core, matching the observed-event color family', () => {
  it('the clinical marker color is never one of the scientific risk-gradient/reach-ring family colors', () => {
    expect(RISK_FAMILY_HEXES).not.toContain(CLINICAL_MARKER_COLOR_HEX.toLowerCase())
  })

  it('the clinical marker color IS a red hue -- red is the dominant channel (Section 2: "observed outbreak markers... STEADY RED CORE")', () => {
    const hex = CLINICAL_MARKER_COLOR_HEX.replace('#', '')
    const r = parseInt(hex.slice(0, 2), 16)
    const g = parseInt(hex.slice(2, 4), 16)
    const b = parseInt(hex.slice(4, 6), 16)
    expect(r > g && r > b).toBe(true)
  })
})
