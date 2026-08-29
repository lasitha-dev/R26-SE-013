/**
 * GEO-AREA-02 Section 16: deterministic, glyph-independent presentation
 * icon for the authorized-farm ("My Area") map marker -- same raw-RGBA-
 * buffer technique as `presentationIcons.js`/`operationalIcons.js`
 * (Section 2: reuse the existing visual-language convention).
 *
 * Section 16: a professional, restrained solid marker -- emerald fill
 * with a white outline halo for contrast, never red/pulsing/risk-
 * colored. Deliberately SOLID and CIRCULAR, distinct in both fill (vs.
 * the hollow teal diamond/circle used for Verified Clinical Context,
 * `operationalIcons.js`) and shape/color (vs. the filled amber diamond
 * used for historical sources, `presentationIcons.js`) -- a farm marker
 * must never be visually confusable with either.
 */

export const FARM_MARKER_ICON_ID = 'geo-my-area-farm-icon'
export const FARM_MARKER_ICON_SIZE = 20

const FARM_MARKER_FILL = [16, 185, 129, 255] // emerald-500
const FARM_MARKER_HALO = [255, 255, 255, 255] // white outline, for contrast against any basemap

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

export function buildFarmMarkerImage(size = FARM_MARKER_ICON_SIZE) {
  const data = makeRgbaBuffer(size, size)
  const cx = (size - 1) / 2
  const cy = (size - 1) / 2
  const r = size / 2 - 1
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r
      if (dist <= 0.72) {
        setPixel(data, size, x, y, FARM_MARKER_FILL)
      } else if (dist <= 1.0) {
        setPixel(data, size, x, y, FARM_MARKER_HALO)
      }
    }
  }
  return { width: size, height: size, data }
}

export function farmMarkerIconLayout() {
  return { 'icon-image': FARM_MARKER_ICON_ID, 'icon-allow-overlap': true, 'icon-ignore-placement': true, 'icon-size': 1.15 }
}
