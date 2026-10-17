/**
 * Phase 4: frame-to-frame map transitions shared by the National Map
 * (`MapLibreCanvas.jsx`) and My Area (`MyAreaMapCanvas.jsx`).
 *
 * Scientific contract: nothing here creates, morphs or moves a polygon.
 *  - Risk zones are DOUBLE-BUFFERED: the incoming backend frame is loaded
 *    into the idle buffer and the two buffers' layer opacities cross-fade.
 *    Every polygon on screen at every instant is an exact backend polygon,
 *    only its opacity changes. Identical geometry (the reach plateau) is
 *    detected by signature and never re-faded, so it stays perfectly still.
 *  - Corridors are REVEALED along the backend corridor geometry itself (a
 *    prefix of its own coordinates), so the drawn line is always a part of
 *    the backend line and the travelling front always sits on it.
 * Everything is RAF-driven (no timers), cancellable, and instant under
 * reduced motion.
 */

export const RISK_CROSSFADE_MS = 460
export const PATH_REVEAL_MS = 520
export const DIRECTION_ARROW_ICON_ID = 'geo-direction-arrow'
export const EMPTY_FEATURE_COLLECTION = Object.freeze({ type: 'FeatureCollection', features: Object.freeze([]) })

// Standard MapLibre "animated line" dash frames: a dash travelling along the
// line direction (origin -> nominal-reach end), stepped every FLOW_STEP_MS.
export const FLOW_DASH_SEQUENCE = Object.freeze([
  [0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
  [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5],
])
export const FLOW_STEP_MS = 70

const signatureCache = new WeakMap()

/** Geometry + tier identity of a risk-zone collection. Two frames with the
 * same signature draw the same polygons (the post-Day-7 reach plateau). */
export function geometrySignature(collection) {
  if (!collection || typeof collection !== 'object') return 'EMPTY'
  const cached = signatureCache.get(collection)
  if (cached) return cached
  const features = Array.isArray(collection.features) ? collection.features : []
  const signature = features.length === 0
    ? 'EMPTY'
    // `inReach` is part of what is drawn: Risk Zones cells keep the same
    // geometry every day and only their in-reach state changes.
    : JSON.stringify(features.map((f) => [f?.properties?.riskLevel ?? f?.properties?.tier ?? null, f?.properties?.inReach ?? null, f?.geometry ?? null]))
  signatureCache.set(collection, signature)
  return signature
}

/** `alpha * base` as a MapLibre paint value; full alpha returns `base` untouched. */
export function scaledOpacity(alpha, base) {
  const a = Math.max(0, Math.min(1, Math.round(alpha * 1000) / 1000))
  if (a >= 1) return base
  if (typeof base === 'number') return Math.round(base * a * 1000) / 1000
  return ['*', a, base]
}

function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
}

function defaultNow() {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

/**
 * Double-buffered opacity cross-fader for one logical risk-zone layer group.
 *
 * `buffers`: exactly two `{ sourceId, layers: [{ id, property, role, base }] }`
 * (the same layer stack built twice over two GeoJSON sources). `role` lets the
 * ambient pulse swap a base expression for every layer of that role at once.
 * `reduceMotion` may be a boolean or a getter (read on every frame change).
 */
export function createRiskZoneCrossFader({
  map,
  buffers,
  durationMs = RISK_CROSSFADE_MS,
  reduceMotion = false,
  raf = (cb) => requestAnimationFrame(cb),
  caf = (id) => cancelAnimationFrame(id),
  now = defaultNow,
}) {
  if (!Array.isArray(buffers) || buffers.length !== 2) throw new Error('createRiskZoneCrossFader needs exactly two buffers')
  const alphas = [1, 0]
  let active = 0
  let signature = null
  let frameId = null
  let destroyed = false
  let transitions = 0

  function applyAlpha(index) {
    for (const layer of buffers[index].layers) {
      if (map.getLayer(layer.id)) map.setPaintProperty(layer.id, layer.property, scaledOpacity(alphas[index], layer.base))
    }
  }

  function setData(index, data) {
    map.getSource(buffers[index].sourceId)?.setData(data ?? EMPTY_FEATURE_COLLECTION)
  }

  function stop() {
    if (frameId != null) caf(frameId)
    frameId = null
  }

  function settle(index) {
    stop()
    active = index
    alphas[index] = 1
    alphas[1 - index] = 0
    applyAlpha(0)
    applyAlpha(1)
    setData(1 - index, EMPTY_FEATURE_COLLECTION)
  }

  return {
    /** Show one backend frame. Returns 'UNCHANGED' | 'INSTANT' | 'CROSSFADE'. */
    show(collection) {
      if (destroyed) return 'UNCHANGED'
      const next = geometrySignature(collection)
      if (next === signature) return 'UNCHANGED'
      const first = signature == null
      signature = next
      const instant = typeof reduceMotion === 'function' ? reduceMotion() : reduceMotion
      if (first || instant || !(durationMs > 0)) {
        setData(active, collection)
        settle(active)
        return 'INSTANT'
      }
      // The buffer that is currently LESS visible receives the new frame. If
      // a fade was still running (rapid scrubbing), that buffer holds a stale
      // intermediate frame: it is dropped to 0 first so it can never flash.
      const incoming = alphas[0] <= alphas[1] ? 0 : 1
      const outgoing = 1 - incoming
      stop()
      alphas[incoming] = 0
      applyAlpha(incoming)
      setData(incoming, collection)
      const fromOut = alphas[outgoing]
      const start = now()
      transitions += 1
      const tick = () => {
        const t = Math.min(1, (now() - start) / durationMs)
        const e = easeInOutCubic(t)
        alphas[incoming] = e
        alphas[outgoing] = fromOut * (1 - e)
        applyAlpha(incoming)
        applyAlpha(outgoing)
        if (t < 1) frameId = raf(tick)
        else {
          frameId = null
          settle(incoming)
        }
      }
      frameId = raf(tick)
      return 'CROSSFADE'
    },
    /** Swap the base opacity expression of every layer with this role (ambient pulse). */
    setBase(role, base) {
      for (let index = 0; index < 2; index += 1) {
        for (const layer of buffers[index].layers) if (layer.role === role) layer.base = base
        applyAlpha(index)
      }
    },
    /** Jump to the end state of a running fade (e.g. reduced motion turned on). */
    finish() {
      if (frameId != null) settle(alphas[0] >= alphas[1] ? 0 : 1)
    },
    destroy() {
      destroyed = true
      stop()
    },
    debugState() {
      return { alphas: [...alphas], active, animating: frameId != null, transitions, signature }
    },
  }
}

// ---- corridor reveal --------------------------------------------------

function segmentKm(a, b) {
  const meanLat = ((a[1] + b[1]) / 2) * (Math.PI / 180)
  const dx = (b[0] - a[0]) * 111.32 * Math.cos(meanLat)
  const dy = (b[1] - a[1]) * 110.574
  return Math.hypot(dx, dy)
}

function lineParts(geometry) {
  if (geometry?.type === 'LineString') return [geometry.coordinates]
  if (geometry?.type === 'MultiLineString') return geometry.coordinates
  return []
}

export function lineLengthKm(geometry) {
  let total = 0
  for (const part of lineParts(geometry)) for (let i = 1; i < part.length; i += 1) total += segmentKm(part[i - 1], part[i])
  return total
}

/** The first `fraction` of the backend line, cut along its own vertices. */
export function sliceLineToFraction(geometry, fraction) {
  const parts = lineParts(geometry)
  if (parts.length === 0) return null
  const f = Math.max(0, Math.min(1, fraction))
  if (f >= 1) return geometry
  let remaining = lineLengthKm(geometry) * f
  const out = []
  for (const part of parts) {
    if (part.length === 0) continue
    const kept = [part[0]]
    for (let i = 1; i < part.length; i += 1) {
      const step = segmentKm(part[i - 1], part[i])
      if (step <= remaining) {
        kept.push(part[i])
        remaining -= step
        continue
      }
      const ratio = step > 0 ? remaining / step : 0
      kept.push([part[i - 1][0] + (part[i][0] - part[i - 1][0]) * ratio, part[i - 1][1] + (part[i][1] - part[i - 1][1]) * ratio])
      remaining = 0
      break
    }
    out.push(kept.length === 1 ? [kept[0], kept[0]] : kept)
    if (remaining <= 0) break
  }
  return out.length === 1 ? { type: 'LineString', coordinates: out[0] } : { type: 'MultiLineString', coordinates: out }
}

function endPoint(geometry) {
  const parts = lineParts(geometry)
  return parts.at(-1)?.at(-1) ?? null
}

/**
 * One animation step between two frames' corridor collections. A source
 * present in both frames grows (or shrinks) along the corridor that is
 * longer; a new source grows from its origin; a vanished source is dropped.
 * Fronts are re-derived at the visible end, so the travelling indicator
 * always sits on the drawn backend line. `t` = eased progress 0..1.
 */
export function revealCorridorStep(previousPaths, nextPaths, nextFronts, t) {
  const previousById = new Map((previousPaths?.features ?? []).map((f) => [f.properties?.sourceId, f]))
  const frontsById = new Map((nextFronts?.features ?? []).map((f) => [f.properties?.sourceId, f]))
  const paths = []
  const fronts = []
  for (const feature of nextPaths?.features ?? []) {
    const id = feature.properties?.sourceId
    const prior = previousById.get(id)
    const nextLength = lineLengthKm(feature.geometry)
    const priorLength = prior ? lineLengthKm(prior.geometry) : 0
    let geometry
    if (nextLength >= priorLength) {
      const from = nextLength > 0 ? priorLength / nextLength : 1
      geometry = sliceLineToFraction(feature.geometry, from + (1 - from) * t)
    } else {
      const to = priorLength > 0 ? nextLength / priorLength : 0
      geometry = t >= 1 ? feature.geometry : sliceLineToFraction(prior.geometry, 1 + (to - 1) * t)
    }
    if (!geometry) continue
    paths.push({ ...feature, geometry })
    const front = frontsById.get(id)
    const end = endPoint(geometry)
    if (front && end) fronts.push({ ...front, geometry: { type: 'Point', coordinates: end } })
  }
  return { paths: { type: 'FeatureCollection', features: paths }, fronts: { type: 'FeatureCollection', features: fronts } }
}

/**
 * RAF runner for `revealCorridorStep`. Returns a cancel function. Calls
 * `apply({paths, fronts})` every frame and once more with the exact backend
 * collections at the end (or immediately under reduced motion).
 */
export function runCorridorReveal({
  previous,
  next,
  apply,
  durationMs = PATH_REVEAL_MS,
  reduceMotion = false,
  raf = (cb) => requestAnimationFrame(cb),
  caf = (id) => cancelAnimationFrame(id),
  now = defaultNow,
}) {
  const finalState = { paths: next?.paths ?? EMPTY_FEATURE_COLLECTION, fronts: next?.fronts ?? EMPTY_FEATURE_COLLECTION }
  if (reduceMotion || !(durationMs > 0) || !previous) {
    apply(finalState)
    return () => {}
  }
  let frameId = null
  const start = now()
  const tick = () => {
    const t = Math.min(1, (now() - start) / durationMs)
    if (t >= 1) {
      frameId = null
      apply(finalState)
      return
    }
    apply(revealCorridorStep(previous.paths, finalState.paths, finalState.fronts, 1 - (1 - t) ** 3))
    frameId = raf(tick)
  }
  frameId = raf(tick)
  return () => {
    if (frameId != null) caf(frameId)
    frameId = null
  }
}

/** RAF loop stepping `line-dasharray` on the flow layer(s); `getMap()` may
 * return null until the map has loaded. Returns a stop function. */
export function startFlowDash({
  getMap,
  layerIds,
  raf = (cb) => requestAnimationFrame(cb),
  caf = (id) => cancelAnimationFrame(id),
  now = defaultNow,
}) {
  let step = 0
  let last = now()
  let frameId = null
  const tick = () => {
    const current = now()
    const map = getMap()
    if (map && current - last >= FLOW_STEP_MS) {
      last = current
      step = (step + 1) % FLOW_DASH_SEQUENCE.length
      for (const id of layerIds) {
        if (map.getLayer(id) && map.getLayoutProperty?.(id, 'visibility') !== 'none') {
          map.setPaintProperty(id, 'line-dasharray', FLOW_DASH_SEQUENCE[step])
        }
      }
    }
    frameId = raf(tick)
  }
  frameId = raf(tick)
  return () => {
    if (frameId != null) caf(frameId)
    frameId = null
  }
}

// ---- direction arrow icon ---------------------------------------------

/** Raw RGBA chevron-arrow pointing NORTH (rotated per feature by the
 * layer's `icon-rotate: bearingDeg`, map-aligned). Supersampled edges. */
export function buildDirectionArrowIcon(size = 22, fill = [233, 213, 255], stroke = [126, 34, 206]) {
  const data = new Uint8ClampedArray(size * size * 4)
  const tip = [size / 2, 1.5]
  const left = [2.5, size - 3]
  const notch = [size / 2, size * 0.66]
  const right = [size - 2.5, size - 3]
  const polygon = [tip, right, notch, left]
  const inside = (x, y, poly) => {
    let hit = false
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i, i += 1) {
      const [xi, yi] = poly[i]
      const [xj, yj] = poly[j]
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) hit = !hit
    }
    return hit
  }
  const shrink = (poly, k) => {
    const cx = poly.reduce((s, p) => s + p[0], 0) / poly.length
    const cy = poly.reduce((s, p) => s + p[1], 0) / poly.length
    return poly.map(([x, y]) => [cx + (x - cx) * k, cy + (y - cy) * k])
  }
  const inner = shrink(polygon, 0.72)
  const SS = 4
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      let outerHits = 0
      let innerHits = 0
      for (let sy = 0; sy < SS; sy += 1) {
        for (let sx = 0; sx < SS; sx += 1) {
          const px = x + (sx + 0.5) / SS
          const py = y + (sy + 0.5) / SS
          if (inside(px, py, polygon)) {
            outerHits += 1
            if (inside(px, py, inner)) innerHits += 1
          }
        }
      }
      if (outerHits === 0) continue
      const coverage = outerHits / (SS * SS)
      const fillShare = innerHits / outerHits
      const idx = (y * size + x) * 4
      for (let c = 0; c < 3; c += 1) data[idx + c] = Math.round(fill[c] * fillShare + stroke[c] * (1 - fillShare))
      data[idx + 3] = Math.round(255 * coverage)
    }
  }
  return { width: size, height: size, data }
}

export function ensureDirectionArrowImage(map) {
  if (!map?.addImage || map.hasImage?.(DIRECTION_ARROW_ICON_ID)) return
  map.addImage(DIRECTION_ARROW_ICON_ID, buildDirectionArrowIcon(), { pixelRatio: 1 })
}

/** Shared paint/layout for the arrow symbol at each corridor front. */
export function directionArrowLayout(visibility) {
  return {
    'icon-image': DIRECTION_ARROW_ICON_ID,
    'icon-rotate': ['coalesce', ['get', 'bearingDeg'], 0],
    'icon-rotation-alignment': 'map',
    'icon-pitch-alignment': 'map',
    'icon-allow-overlap': true,
    'icon-ignore-placement': true,
    'icon-offset': [0, -9],
    visibility,
  }
}
