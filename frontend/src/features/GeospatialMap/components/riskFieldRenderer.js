/**
 * Risk Zones surface: the backend's day-d practical risk field
 * (`adapters/riskFieldModel.js`) drawn as ONE continuous surface of the
 * display score B = 1 - exp(-F_d), coloured by the fixed display bands (red
 * high >= 0.70, orange elevated >= 0.40, yellow moderate >= 0.15, green low)
 * with thin contours at the band boundaries.
 *
 *  - Day d: every pixel on scored land (inside the backend cell footprints)
 *    takes the backend day-d raster score (bilinear between its ~1.65 km
 *    cells) -- a small zone around each farm on Day 0,
 *    then growing along each case's spread path at the evaluated 9C rate,
 *    stronger where cases overlap, gone once a case leaves the active
 *    window. Built on demand and cached per day.
 *  - A day change cross-fades between the two day surfaces; nothing is
 *    scaled or grown by the animation itself. No reach outline is drawn.
 *
 * Drawn into a MapLibre `canvas` source fixed over Sri Lanka, so it sits in
 * the normal layer order (under case markers). RAF runs only during a fade.
 */
import { bandOfScore, probeRiskField, rasterScoreAt, surfaceColour } from '../adapters/riskFieldModel'
import { mapAlive } from './stageLayers'

// Sri Lanka with margin [west, south, east, north] and pixel density (~0.45 km).
const BOUNDS = [79.4, 5.7, 82.1, 10.05]
const DEG_PER_PX = 0.004
const FADE_MS = 500
const BAND_INDEX = { low: 1, moderate: 2, elevated: 3, high: 4 }
const CONTOUR_RGBA = { 2: [161, 98, 7, 150], 3: [180, 83, 9, 200], 4: [159, 18, 57, 235] }

function mercY(lat) {
  const r = (lat * Math.PI) / 180
  return Math.log(Math.tan(Math.PI / 4 + r / 2))
}

export function createRiskFieldRenderer(map, { sourceId, layerId, beforeId = null, reduceMotion = () => false, document: doc = globalThis.document } = {}) {
  const width = Math.round((BOUNDS[2] - BOUNDS[0]) / DEG_PER_PX)
  const yTop = mercY(BOUNDS[3])
  const ySpan = yTop - mercY(BOUNDS[1])
  const height = Math.round(width * (ySpan / (((BOUNDS[2] - BOUNDS[0]) * Math.PI) / 180)))
  const makeCanvas = () => {
    const c = doc.createElement('canvas')
    c.width = width
    c.height = height
    return c
  }
  const canvas = makeCanvas()
  const ctx = canvas.getContext('2d')
  const px = ([lon, lat]) => [((lon - BOUNDS[0]) / (BOUNDS[2] - BOUNDS[0])) * width, ((yTop - mercY(lat)) / ySpan) * height]
  const lonAt = (x) => BOUNDS[0] + ((x + 0.5) / width) * (BOUNDS[2] - BOUNDS[0])
  const latAt = (y) => {
    const m = yTop - ((y + 0.5) / height) * ySpan
    return (Math.atan(Math.sinh(m)) * 180) / Math.PI
  }

  map.addSource(sourceId, {
    type: 'canvas',
    canvas,
    animate: false,
    coordinates: [[BOUNDS[0], BOUNDS[3]], [BOUNDS[2], BOUNDS[3]], [BOUNDS[2], BOUNDS[1]], [BOUNDS[0], BOUNDS[1]]],
  })
  const layer = { id: layerId, type: 'raster', source: sourceId, layout: { visibility: 'none' }, paint: { 'raster-opacity': 1, 'raster-resampling': 'linear', 'raster-fade-duration': 0 } }
  if (beforeId && map.getLayer(beforeId)) map.addLayer(layer, beforeId)
  else map.addLayer(layer)

  let model = null
  let land = null // scored land of `model`: { x0, y0, w, h, inside: Uint8Array (mask alpha) }
  const daySurfaces = new Map() // day -> canvas, for `model`
  let current = null // the selected day's surface
  let previous = null // the surface being faded out
  let day = 0
  let fade = 1
  let startedAt = 0
  let frameId = null
  let visible = false

  function traceGeometry(target, geometry) {
    const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.type === 'MultiPolygon' ? geometry.coordinates : []
    target.beginPath()
    for (const rings of polygons) {
      for (const ring of rings) {
        ring.forEach((point, k) => {
          const [x, y] = px(point)
          if (k === 0) target.moveTo(x, y)
          else target.lineTo(x, y)
        })
        target.closePath()
      }
    }
  }

  /** Scored land of one snapshot: the backend cell footprints (once per snapshot). */
  function buildLand(next) {
    if (!next?.cells?.length) return null
    const mask = makeCanvas()
    const mctx = mask.getContext('2d')
    mctx.fillStyle = '#000'
    // Soft ~1 km edge so a 5 km cell or the coast never reads as a hard square.
    mctx.filter = 'blur(2px)'
    for (const cell of next.cells) {
      traceGeometry(mctx, cell.geometry)
      mctx.fill('evenodd')
    }
    mctx.filter = 'none'
    let x0 = width; let y0 = height; let x1 = 0; let y1 = 0
    for (const cell of next.cells) {
      const [x, y] = px(cell.centroid)
      x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y)
    }
    const pad = 16
    x0 = Math.max(0, Math.floor(x0 - pad)); y0 = Math.max(0, Math.floor(y0 - pad))
    x1 = Math.min(width - 1, Math.ceil(x1 + pad)); y1 = Math.min(height - 1, Math.ceil(y1 + pad))
    const w = x1 - x0 + 1
    const h = y1 - y0 + 1
    const data = mctx.getImageData(x0, y0, w, h).data
    const inside = new Uint8Array(w * h)
    for (let k = 0; k < inside.length; k += 1) inside[k] = data[k * 4 + 3]
    return { x0, y0, w, h, inside }
  }

  /** The day-d surface: the backend raster, interpolated per pixel, on scored land only. */
  function buildDay(d) {
    const out = makeCanvas()
    const raster = model?.rasterFor?.(d)
    if (!land || !raster) return out
    const { x0, y0, w, h, inside } = land
    const lons = Float64Array.from({ length: w }, (_, i) => lonAt(x0 + i))
    const lats = Float64Array.from({ length: h }, (_, j) => latAt(y0 + j))
    const octx = out.getContext('2d')
    const image = octx.createImageData(w, h)
    const bandIndex = new Uint8Array(w * h)
    for (let k = 0; k < w * h; k += 1) {
      if (inside[k] < 8) continue
      const score = rasterScoreAt(raster, model.grid, lons[k % w], lats[Math.floor(k / w)])
      const rgba = surfaceColour(score, model.bands, model.grid.min_score)
      if (!rgba) continue
      bandIndex[k] = BAND_INDEX[bandOfScore(score, model.bands)] ?? 0
      image.data[k * 4] = rgba[0]
      image.data[k * 4 + 1] = rgba[1]
      image.data[k * 4 + 2] = rgba[2]
      // The blurred land mask gives the coast and the domain edge a soft rim.
      image.data[k * 4 + 3] = Math.round(rgba[3] * inside[k])
    }
    // Band contours: between two drawn neighbours of different bands, the
    // pixel on the higher-band side takes that band's contour colour.
    for (let j = 0; j < h; j += 1) {
      for (let i = 0; i < w; i += 1) {
        const k = j * w + i
        const t = bandIndex[k]
        if (!t) continue
        for (const n of [i + 1 < w ? k + 1 : -1, j + 1 < h ? k + w : -1]) {
          if (n < 0 || !bandIndex[n] || bandIndex[n] === t) continue
          const [hi, at] = bandIndex[n] > t ? [bandIndex[n], n] : [t, k]
          if (hi >= 2 && inside[at] > 128) image.data.set(CONTOUR_RGBA[hi], at * 4)
        }
      }
    }
    octx.putImageData(image, x0, y0)
    return out
  }

  function surfaceFor(d) {
    if (!daySurfaces.has(d)) daySurfaces.set(d, buildDay(d))
    return daySurfaces.get(d)
  }

  function draw() {
    ctx.clearRect(0, 0, width, height)
    if (previous && fade < 1) {
      ctx.globalAlpha = 1 - fade
      ctx.drawImage(previous, 0, 0)
    }
    if (current) {
      ctx.globalAlpha = fade
      ctx.drawImage(current, 0, 0)
    }
    ctx.globalAlpha = 1
  }

  function upload() {
    if (!mapAlive(map)) return
    const source = map.getSource(sourceId)
    if (!source) return
    source.play?.()
    map.triggerRepaint?.()
    // One rendered frame is enough to upload the new texture.
    requestAnimationFrame(() => { if (mapAlive(map)) map.getSource(sourceId)?.pause?.() })
  }

  function render() {
    draw()
    upload()
  }

  function tick(now) {
    if (!mapAlive(map)) { frameId = null; return }
    fade = Math.min(1, (now - startedAt) / FADE_MS)
    render()
    frameId = fade < 1 ? requestAnimationFrame(tick) : null
    if (fade >= 1) previous = null
  }

  const clampDay = (d) => Math.max(0, Math.min((model?.frameCount ?? 1) - 1, Number.isFinite(d) ? d : 0))

  /** Show day `d`: the old surface fades out while the new one fades in. */
  function showDay(d, { animate = true } = {}) {
    day = clampDay(d)
    previous = animate ? current : null
    current = model ? surfaceFor(day) : null
    if (frameId != null) cancelAnimationFrame(frameId)
    frameId = null
    if (reduceMotion() || !visible || !previous) {
      fade = 1
      previous = null
      render()
      return
    }
    fade = 0
    startedAt = performance.now()
    frameId = requestAnimationFrame(tick)
  }

  return {
    /** New snapshot (or none) and selected day. Same snapshot: only the day changes. */
    setModel(next, index = 0) {
      if (next?.key === model?.key) {
        if (clampDay(index) !== day) showDay(index)
        return
      }
      model = next
      land = buildLand(next)
      daySurfaces.clear()
      showDay(index, { animate: false })
    },
    setIndex(index) {
      if (clampDay(index) !== day) showDay(index)
    },
    setVisible(next) {
      visible = Boolean(next)
      if (mapAlive(map) && map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none')
      if (visible) render()
    },
    /** Hover details at a point on the shown day (`probeRiskField`), or null. */
    probe(lon, lat) {
      return visible ? probeRiskField(model, day, lon, lat) : null
    },
    destroy() {
      if (frameId != null) cancelAnimationFrame(frameId)
      frameId = null
      daySurfaces.clear()
    },
  }
}
