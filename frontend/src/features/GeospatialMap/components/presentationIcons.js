/**
 * Checkpoint 11B.1: deterministic, glyph-INDEPENDENT presentation icons
 * for the source and direction overlays.
 *
 * Checkpoint 11B used text-based symbol layers ('text-field': '■' / '▲')
 * whose actual rendering depends on MapLibre's font-glyph pipeline
 * (local PBF glyphs or a remote glyph/sprite server declared by the
 * active style's `glyphs` URL). The neutral token-free fallback style
 * declares no `glyphs` URL at all, so that assumption was never proven
 * -- see CHECKPOINT_11B1 for the audit. Rather than adding a remote
 * glyph dependency (which would make the "token-free" mode
 * network-dependent) or upgrading maplibre-gl purely to chase newer
 * font behavior, these functions build the marker pixels DIRECTLY as a
 * raw RGBA buffer -- the exact shape MapLibre's `map.addImage(id, {
 * width, height, data })` accepts -- with zero canvas, zero DOM, and
 * zero font/glyph/sprite dependency of any kind. That also makes them
 * fully unit-testable in this repo's Node-only Vitest environment.
 *
 * These functions read NO scientific value -- they only ever accept a
 * pixel size and return presentation pixels.
 */

export const SOURCE_ICON_ID = 'geo-source-marker-icon'
// FMD-10C1: FMD's own national-source marker -- SAME fill/stroke colors
// as `SOURCE_ICON_ID`, shape-only difference (circle, not diamond),
// matching `diseaseRegistry.js`'s existing `markerShape` convention
// ('diamond' for LSD, 'circle' for FMD) -- color never varies by disease.
export const FMD_SOURCE_ICON_ID = 'geo-fmd-source-marker-icon'
export const DIRECTION_ICON_ID = 'geo-direction-arrow-icon'
export const SOURCE_ICON_SIZE = 16
export const DIRECTION_ICON_SIZE = 20

// GEO30B Section 8/12/33: RED is the ONE color reserved for a real
// OBSERVED outbreak/trigger-source point on the national map -- never
// reused for forecast/trajectory movement (that stays a different family
// entirely, e.g. `nominalReachRing.js`'s teal). Two-tone red (a brighter
// core, a slightly deeper red ring) so a single opaque marker still
// reads as "outbreak" at national zoom without needing a second overlay
// layer -- shape (diamond=LSD, circle=FMD) still carries disease
// identity, per this module's existing convention; color never varies
// by disease.
const SOURCE_FILL = [239, 68, 68, 255] // red-500 core
const SOURCE_STROKE = [185, 28, 28, 255] // red-700 ring
const DIRECTION_FILL = [30, 41, 59, 255] // slate-800 -- neutral, never red (not an outbreak marker)

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

/**
 * A diamond marker, deliberately DIFFERENT IN SHAPE (not merely color)
 * from the circular scientific-cell markers, per Part 3's "visually
 * distinct... beyond color" requirement. Presentation pixels only.
 */
export function buildSourceMarkerImage(size = SOURCE_ICON_SIZE) {
  const data = makeRgbaBuffer(size, size)
  const cx = (size - 1) / 2
  const cy = (size - 1) / 2
  const r = size / 2 - 1
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const norm = Math.abs(x - cx) / r + Math.abs(y - cy) / r // diamond (L1) distance
      if (norm <= 1) {
        setPixel(data, size, x, y, SOURCE_FILL)
      } else if (norm <= 1.3) {
        setPixel(data, size, x, y, SOURCE_STROKE)
      }
    }
  }
  return { width: size, height: size, data }
}

/**
 * FMD-10C1: a circle marker -- SAME `SOURCE_FILL`/`SOURCE_STROKE`
 * colors as `buildSourceMarkerImage`'s diamond, deliberately different
 * in SHAPE only (matches `diseaseRegistry.js`'s `markerShape: 'circle'`
 * for FMD). Presentation pixels only -- reads no scientific value.
 */
export function buildFmdSourceMarkerImage(size = SOURCE_ICON_SIZE) {
  const data = makeRgbaBuffer(size, size)
  const cx = (size - 1) / 2
  const cy = (size - 1) / 2
  const r = size / 2 - 1
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
      if (dist <= r) {
        setPixel(data, size, x, y, SOURCE_FILL)
      } else if (dist <= r + 1.3) {
        setPixel(data, size, x, y, SOURCE_STROKE)
      }
    }
  }
  return { width: size, height: size, data }
}

/**
 * A NORTH-FACING (pointing up) triangle, rendered upright at
 * `icon-rotate: 0`. MapLibre's `icon-rotate` then rotates this image
 * CLOCKWISE by the exact degree value supplied -- so passing the
 * backend's own `bearing_deg` verbatim reproduces the compass
 * convention (0=North, 90=East, 180=South, 270=West) with zero
 * direction math performed in this module or by the caller.
 */
export function buildDirectionArrowImage(size = DIRECTION_ICON_SIZE) {
  const data = makeRgbaBuffer(size, size)
  const cx = (size - 1) / 2
  const tipY = 1
  const baseY = size - 2
  const halfWidthAtBase = size / 3
  for (let y = tipY; y <= baseY; y += 1) {
    const t = (y - tipY) / (baseY - tipY) // 0 at the tip (North), 1 at the base
    const halfWidth = t * halfWidthAtBase
    for (let x = 0; x < size; x += 1) {
      if (Math.abs(x - cx) <= halfWidth) {
        setPixel(data, size, x, y, DIRECTION_FILL)
      }
    }
  }
  return { width: size, height: size, data }
}
