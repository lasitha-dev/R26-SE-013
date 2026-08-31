/**
 * GEO-INT-03 Section 9, REDESIGNED by GEO31A Section 2: deterministic,
 * glyph-independent presentation icons for the Verified Clinical
 * Context / observed-outbreak overlay -- same raw-RGBA-buffer technique
 * as `presentationIcons.js`.
 *
 * GEO31A Section 2 explicitly supersedes GEO-INT-03's original "hollow
 * mint, never red, never a glow" restraint: the owner's reference shows a
 * STEADY RED CORE + RED INNER RING for an observed outbreak marker,
 * matching the same red family `presentationIcons.js`'s historical
 * `SOURCE_FILL` already uses for the scientific "source" layer (GEO30B) --
 * one consistent "red = a real observed event" language across both
 * layers. The soft EXPANDING outer halo (arrival pulse, steady selection
 * ring) is a separate, larger MapLibre `circle` layer underneath this
 * icon (`operationalMarkerLayer.js`/`MapLibreCanvas.jsx`), never baked
 * into this raster icon -- this icon alone is the "the center dot MUST
 * remain visible at all times" guarantee (Section 2): its own opacity
 * never drops to 0 (`operationalMarkerPaint`), only the halo around it
 * animates. Shape alone still carries disease identity (diamond=LSD,
 * circle=FMD, matching `disease/diseaseRegistry.js`'s `markerShape`
 * convention) -- color never varies by disease.
 */

export const CLINICAL_DIAMOND_ICON_ID = 'geo-clinical-diamond-icon'
export const CLINICAL_CIRCLE_ICON_ID = 'geo-clinical-circle-icon'
export const CLINICAL_ICON_SIZE = 18

// GEO31A Section 2/10: red-500 core / red-700 ring -- the SAME red family
// `presentationIcons.js`'s historical SOURCE_FILL/SOURCE_STROKE use, so
// "red" consistently means "a real observed event" across both the
// scientific-origin layer and this operational/clinical layer.
export const CLINICAL_MARKER_COLOR_HEX = '#ef4444'
const CLINICAL_FILL = [239, 68, 68, 255]
const CLINICAL_STROKE = [185, 28, 28, 255]

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

/** Solid red diamond (LSD) with a darker red ring -- steady core, always
 * visible (Section 2: "the center dot MUST remain visible at all times"). */
export function buildClinicalDiamondIcon(size = CLINICAL_ICON_SIZE) {
  const data = makeRgbaBuffer(size, size)
  const cx = (size - 1) / 2
  const cy = (size - 1) / 2
  const r = size / 2 - 1
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const norm = Math.abs(x - cx) / r + Math.abs(y - cy) / r // diamond (L1) distance
      if (norm <= 0.82) {
        setPixel(data, size, x, y, CLINICAL_FILL)
      } else if (norm <= 1.15) {
        setPixel(data, size, x, y, CLINICAL_STROKE)
      }
    }
  }
  return { width: size, height: size, data }
}

/** Solid red circle (FMD) with a darker red ring -- steady core, always
 * visible (Section 2: "the center dot MUST remain visible at all times"). */
export function buildClinicalCircleIcon(size = CLINICAL_ICON_SIZE) {
  const data = makeRgbaBuffer(size, size)
  const cx = (size - 1) / 2
  const cy = (size - 1) / 2
  const r = size / 2 - 1
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r // circular (L2) distance
      if (dist <= 0.78) {
        setPixel(data, size, x, y, CLINICAL_FILL)
      } else if (dist <= 1.0) {
        setPixel(data, size, x, y, CLINICAL_STROKE)
      }
    }
  }
  return { width: size, height: size, data }
}
