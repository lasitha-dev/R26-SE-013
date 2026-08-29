/**
 * GEO-INT-03 Section 9: deterministic, glyph-independent presentation
 * icons for the Verified Clinical Context overlay -- same raw-RGBA-
 * buffer technique as `presentationIcons.js` (Section 3: reuse the
 * existing visual-language convention rather than inventing a second
 * one), kept in a sibling module so that file's own documented scope
 * (source/direction overlay icons) stays accurate.
 *
 * Section 9: hollow/outlined only (transparent interior, no fill) with a
 * single restrained neutral-mint stroke -- never the risk red/orange/
 * amber/yellow/green family used elsewhere in this feature
 * (`mapLibreAdapter.js`'s risk gradient, `presentationIcons.js`'s amber
 * source fill), never a glow/pulse. Shape alone carries disease identity
 * (diamond=LSD, circle=FMD, matching `disease/diseaseRegistry.js`'s
 * existing `markerShape` convention) -- color never varies by disease.
 */

export const CLINICAL_DIAMOND_ICON_ID = 'geo-clinical-diamond-icon'
export const CLINICAL_CIRCLE_ICON_ID = 'geo-clinical-circle-icon'
export const CLINICAL_ICON_SIZE = 18

// teal-400 -- a restrained clinical mint, deliberately distinct from the
// amber source fill, the emerald selection halo (#10b981), the teal reach
// ring (#14b8a6), and the entire red-orange-amber-yellow-green risk family.
export const CLINICAL_MARKER_COLOR_HEX = '#2dd4bf'
const CLINICAL_STROKE = [45, 212, 191, 255]

function makeRgbaBuffer(width, height) {
  return new Uint8ClampedArray(width * height * 4)
}

function setPixel(data, width, x, y, [r, g, b, a]) {
  if (x < 0 || y < 0 || x >= width) return
  const idx = (y * width + x) * 4
  data[idx] = r
  data[idx + 1] = g
  data[idx + 2] = b
  data[idx + 3] = a
}

/** Hollow diamond (LSD) -- an outline band only, transparent interior. */
export function buildClinicalDiamondIcon(size = CLINICAL_ICON_SIZE) {
  const data = makeRgbaBuffer(size, size)
  const cx = (size - 1) / 2
  const cy = (size - 1) / 2
  const r = size / 2 - 1
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const norm = Math.abs(x - cx) / r + Math.abs(y - cy) / r // diamond (L1) distance
      if (norm > 0.82 && norm <= 1.15) {
        setPixel(data, size, x, y, CLINICAL_STROKE)
      }
    }
  }
  return { width: size, height: size, data }
}

/** Hollow circle (FMD) -- an outline band only, transparent interior. */
export function buildClinicalCircleIcon(size = CLINICAL_ICON_SIZE) {
  const data = makeRgbaBuffer(size, size)
  const cx = (size - 1) / 2
  const cy = (size - 1) / 2
  const r = size / 2 - 1
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r // circular (L2) distance
      if (dist > 0.78 && dist <= 1.0) {
        setPixel(data, size, x, y, CLINICAL_STROKE)
      }
    }
  }
  return { width: size, height: size, data }
}
