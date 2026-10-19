/**
 * National Map "stage" layers -- one clear visual language per analysis mode,
 * all drawn from real data passed in by the page (`adapters/spatialStory.js`):
 *
 *  Cases       countrywide reported LSD/FMD cases (national surveillance):
 *              fill = report-date age (0-14 d red + pulse, 15-30 d brown,
 *              > 30 d not drawn, unknown white); outline = status
 *              (verified white, pending thick amber); a halo marks cases
 *              inside the focused district.
 *              The observed markers (not the halo) stay on in Risk Zones and
 *              Trajectory: cases exist whether or not a model frame does.
 *  Risk Zones  the backend's own scored 5 km cells for the selected day:
 *              bright where that day's nominal reach covers the cell, faint
 *              where it is scored but not yet reached. Day changes
 *              cross-fade between two buffers. Unscored land is never drawn
 *              (it is NOT "low risk").
 *  Trajectory  nominal-reach isochrones for every elapsed day + the selected
 *              day's envelope + a slow pulse on each source case.
 *
 * Visibility is decided ONLY by `applyStageVisibility(map, mode)`, so a mode
 * can never leak another mode's overlay.
 */
import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'
import { EMPTY_FEATURE_COLLECTION, createRiskZoneCrossFader } from './mapFrameTransitions'
import { page1RiskFillColorExpression, page1RiskLineColorExpression } from './mapLibreAdapter'
import { CASE_AGE_COLOR } from '../adapters/caseAge'
import { buildDirectionArrowImage } from './presentationIcons'

/** The north-pointing direction arrow recoloured deep blue for wind. */
function buildWindArrowImage(size = 28) {
  const image = buildDirectionArrowImage(size)
  const data = new Uint8ClampedArray(image.data)
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] > 0) { data[i] = 29; data[i + 1] = 78; data[i + 2] = 216 }
  }
  return { ...image, data }
}

export const STAGE_SOURCE = Object.freeze({
  BASELINE: 'geo-stage-baseline-score',
  CELLS_A: 'geo-stage-cells-a',
  CELLS_B: 'geo-stage-cells-b',
  HISTORY: 'geo-stage-reach-history',
  NATIONAL_CASES: 'geo-stage-national-cases',
  CLUSTERS: 'geo-stage-st-clusters',
  ENVIRONMENT: 'geo-stage-environment',
  ENV_PARTICLES: 'geo-stage-env-particles',
  TRAJECTORY_FLOW: 'geo-stage-trajectory-flow',
  ENV_AREA: 'geo-stage-env-area',
})

export const STAGE_LAYER = Object.freeze({
  BASELINE: 'stage-baseline-score',
  CELL_FILL_A: 'stage-cell-fill-a',
  CELL_LINE_A: 'stage-cell-line-a',
  CELL_FILL_B: 'stage-cell-fill-b',
  CELL_LINE_B: 'stage-cell-line-b',
  HISTORY_LINE: 'stage-reach-history-line',
  HISTORY_LABEL: 'stage-reach-history-label',
  CURRENT_FILL: 'stage-reach-current-fill',
  ORIGIN_PULSE: 'stage-origin-pulse',
  NATIONAL_CASE_HALO: 'stage-national-case-halo',
  NATIONAL_CASE: 'stage-national-case',
  NATIONAL_CASE_PULSE: 'stage-national-case-pulse',
  CLUSTER_HULL: 'stage-st-cluster-hull',
  CLUSTER_MEMBER: 'stage-st-cluster-member',
  CLUSTER_NOISE: 'stage-st-cluster-noise',
  ENV_RAIN: 'stage-env-rain',
  ENV_WIND: 'stage-env-wind',
  ENV_LABEL: 'stage-env-label',
  ENV_RAIN_RIPPLE: 'stage-env-rain-ripple',
  ENV_AREA: 'stage-env-area',
  ENV_HEAT: 'stage-env-heat',
  ENV_HEAT_SHIMMER: 'stage-env-heat-shimmer',
  ENV_WIND_FLOW: 'stage-env-wind-flow',
  TRAJECTORY_FLOW_GLOW: 'stage-trajectory-flow-glow',
  TRAJECTORY_FLOW: 'stage-trajectory-flow',
})

export const WIND_ARROW_ICON_ID = 'stage-wind-arrow'

const OBSERVED_CASE_LAYERS = [STAGE_LAYER.NATIONAL_CASE_PULSE, STAGE_LAYER.NATIONAL_CASE]

const MODE_LAYERS = Object.freeze({
  [ANALYSIS_MODE.CASES]: [STAGE_LAYER.NATIONAL_CASE_HALO, ...OBSERVED_CASE_LAYERS],
  // No faint full-surface baseline: Risk Zones shows only what the selected
  // day's reach covers (riskFieldRenderer.js); unreached scored land is not drawn.
  [ANALYSIS_MODE.RISK_ZONES]: [STAGE_LAYER.CELL_FILL_A, STAGE_LAYER.CELL_LINE_A, STAGE_LAYER.CELL_FILL_B, STAGE_LAYER.CELL_LINE_B, ...OBSERVED_CASE_LAYERS],
  // Paths only: no large nominal-reach rings around them (they read as a
  // spread area); the reach itself is shown in Risk Zones.
  [ANALYSIS_MODE.TRAJECTORY]: [STAGE_LAYER.TRAJECTORY_FLOW_GLOW, STAGE_LAYER.TRAJECTORY_FLOW, STAGE_LAYER.ORIGIN_PULSE, ...OBSERVED_CASE_LAYERS],
  // EXPLORATORY runtime ST-DBSCAN (backend /st-clusters): hull, members, noise.
  [ANALYSIS_MODE.CLUSTERS]: [STAGE_LAYER.CLUSTER_HULL, STAGE_LAYER.CLUSTER_NOISE, STAGE_LAYER.CLUSTER_MEMBER],
  // Real ERA5 observations for the selected day: rain circle, wind arrow, values.
  [ANALYSIS_MODE.ENV]: [STAGE_LAYER.ENV_AREA, STAGE_LAYER.ENV_HEAT, STAGE_LAYER.ENV_HEAT_SHIMMER, STAGE_LAYER.ENV_RAIN, STAGE_LAYER.ENV_RAIN_RIPPLE, STAGE_LAYER.ENV_WIND, STAGE_LAYER.ENV_WIND_FLOW, STAGE_LAYER.ENV_LABEL, ...OBSERVED_CASE_LAYERS],
})

/** True while the MapLibre map still has a style (false after map.remove(),
 * when getSource/getLayer would throw). Every RAF loop checks it each frame. */
export function mapAlive(map) {
  return Boolean(map && map.style && !map._removed)
}

const MODE_SCOPED_LAYERS = Object.freeze(Object.values(STAGE_LAYER))

export const NATIONAL_CASE_LAYER_ID = STAGE_LAYER.NATIONAL_CASE

export const RISK_CELL_LAYER_IDS = Object.freeze([STAGE_LAYER.CELL_FILL_A, STAGE_LAYER.CELL_FILL_B])

// Clear bands: in-reach cells are solid enough to read at national zoom;
// scored-but-not-reached cells stay a faint footprint.
// Only cells that hold a current case or lie inside the selected day's reach
// are in the frame (spatialStory.buildRiskCells), so the surface grows with
// the timeline. Thin, faint edges keep it reading as one surface.
// The visible surface is the animated risk field (riskFieldRenderer.js);
// these cell layers stay transparent so a click still opens the cell card.
const CELL_FILL_OPACITY = 0
const CELL_LINE_OPACITY = 0

const PULSE_CYCLE_MS = 2200

// One marker per farm location (the adapter stacks same-farm reports).
const CASE_AGE = ['get', 'ageClass']
const CASE_VERIFIED = ['get', 'verified']

// Observed case marker: fill = report-date age class, outline = status.
const CASE_FILL_COLOR = ['match', CASE_AGE, 'RECENT', CASE_AGE_COLOR.RECENT, 'OLDER', CASE_AGE_COLOR.OLDER, CASE_AGE_COLOR.DATE_UNKNOWN]
const CASE_STROKE_COLOR = ['case', CASE_VERIFIED, ['match', CASE_AGE, 'RECENT', '#ffffff', 'OLDER', '#f8fafc', '#334155'], '#d97706']

function addLayerIfMissing(map, layer, beforeId) {
  if (map.getLayer(layer.id)) return
  if (beforeId && map.getLayer(beforeId)) map.addLayer(layer, beforeId)
  else map.addLayer(layer)
}

function ensureSources(map) {
  for (const id of Object.values(STAGE_SOURCE)) {
    if (map.getSource(id)) continue
    map.addSource(id, { type: 'geojson', data: EMPTY_FEATURE_COLLECTION })
  }
}


/** Adds every mode stage source/layer (all hidden). Call once, after the
 * base cells layer and before the Page-1 corridor/origin layers. Returns the
 * cross-fader driving the per-day risk cells. */
export function addStageLayers(map, { reduceMotion }) {
  ensureSources(map)
  const hidden = { visibility: 'none' }
  addLayerIfMissing(map, {
    id: STAGE_LAYER.BASELINE, type: 'fill', source: STAGE_SOURCE.BASELINE,
    layout: hidden,
    paint: { 'fill-color': page1RiskFillColorExpression(), 'fill-opacity': 0.055 },
  })
  const buffers = [
    { sourceId: STAGE_SOURCE.CELLS_A, fillId: STAGE_LAYER.CELL_FILL_A, lineId: STAGE_LAYER.CELL_LINE_A },
    { sourceId: STAGE_SOURCE.CELLS_B, fillId: STAGE_LAYER.CELL_FILL_B, lineId: STAGE_LAYER.CELL_LINE_B },
  ]
  for (const buffer of buffers) {
    addLayerIfMissing(map, {
      id: buffer.fillId,
      type: 'fill',
      source: buffer.sourceId,
      layout: hidden,
      paint: { 'fill-color': page1RiskFillColorExpression(), 'fill-opacity': CELL_FILL_OPACITY, 'fill-opacity-transition': { duration: 0 } },
    })
    addLayerIfMissing(map, {
      id: buffer.lineId,
      type: 'line',
      source: buffer.sourceId,
      layout: { ...hidden, 'line-join': 'round' },
      paint: { 'line-color': page1RiskLineColorExpression(), 'line-width': 0.6, 'line-opacity': CELL_LINE_OPACITY, 'line-opacity-transition': { duration: 0 } },
    })
  }
  const cellFader = createRiskZoneCrossFader({
    map,
    reduceMotion,
    buffers: buffers.map((buffer) => ({
      sourceId: buffer.sourceId,
      layers: [
        { id: buffer.fillId, property: 'fill-opacity', role: 'fill', base: CELL_FILL_OPACITY },
        { id: buffer.lineId, property: 'line-opacity', role: 'line', base: CELL_LINE_OPACITY },
      ],
    })),
  })

  addLayerIfMissing(map, {
    id: STAGE_LAYER.CURRENT_FILL,
    type: 'fill',
    source: STAGE_SOURCE.HISTORY,
    filter: ['==', ['get', 'isCurrent'], true],
    layout: hidden,
    paint: { 'fill-color': '#8b5cf6', 'fill-opacity': 0.05 },
  })
  addLayerIfMissing(map, {
    id: STAGE_LAYER.HISTORY_LINE,
    type: 'line',
    source: STAGE_SOURCE.HISTORY,
    layout: { ...hidden, 'line-join': 'round' },
    paint: {
      // Selected day's reach = solid red (how far); earlier days fade out.
      'line-color': ['case', ['get', 'isCurrent'], '#7c3aed', ['get', 'exploratory'], '#c4b5fd', '#a78bfa'],
      'line-width': ['case', ['get', 'isCurrent'], 2, 0.8],
      'line-dasharray': [3, 2],
      'line-opacity': ['interpolate', ['linear'], ['get', 'age'], 0, 1, 1, 0.42, 6, 0.14, 14, 0.06],
    },
  })
  // "Day N · X km" written along the selected day's reach ring.
  if (map.getStyle?.()?.glyphs) {
    addLayerIfMissing(map, {
      id: STAGE_LAYER.HISTORY_LABEL,
      type: 'symbol',
      source: STAGE_SOURCE.HISTORY,
      filter: ['==', ['get', 'isCurrent'], true],
      layout: {
        ...hidden,
        'symbol-placement': 'line',
        'symbol-spacing': 320,
        'text-field': ['get', 'label'],
        'text-font': ['Noto Sans Bold'],
        'text-size': 11.5,
        'text-keep-upright': true,
      },
      paint: { 'text-color': '#f5f3ff', 'text-halo-color': '#4c1d95', 'text-halo-width': 1.8 },
    })
  }

  return { cellFader }
}

/** Countrywide case markers (Cases mode). Added after the cells so they sit
 * above risk geometry; the vet-scope operational icons stay on top. */
export function addNationalCaseLayers(map) {
  ensureSources(map)
  addLayerIfMissing(map, {
    id: STAGE_LAYER.NATIONAL_CASE_HALO,
    type: 'circle',
    source: STAGE_SOURCE.NATIONAL_CASES,
    filter: ['==', ['get', 'inDistrict'], true],
    layout: { visibility: 'none' },
    paint: { 'circle-radius': 13, 'circle-color': '#10b981', 'circle-opacity': 0.22, 'circle-stroke-color': '#10b981', 'circle-stroke-width': 1.5, 'circle-stroke-opacity': 0.8 },
  })
  addLayerIfMissing(map, {
    id: STAGE_LAYER.NATIONAL_CASE,
    type: 'circle',
    source: STAGE_SOURCE.NATIONAL_CASES,
    layout: { visibility: 'none' },
    paint: {
      // Small, clean core marker -- never a number bubble.
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 5, 10, 7.5],
      'circle-color': CASE_FILL_COLOR,
      'circle-opacity': ['case', CASE_VERIFIED, 1, 0.6],
      'circle-stroke-color': CASE_STROKE_COLOR,
      'circle-stroke-width': ['case', CASE_VERIFIED, 1.6, 2.6],
    },
  })
  // Runtime ST-DBSCAN (exploratory): dashed hull/line joining a cluster's
  // real member locations, violet members, hollow grey noise points.
  addLayerIfMissing(map, {
    id: STAGE_LAYER.CLUSTER_HULL,
    type: 'line',
    source: STAGE_SOURCE.CLUSTERS,
    filter: ['==', ['get', 'kind'], 'hull'],
    layout: { visibility: 'none' },
    paint: { 'line-color': '#8b5cf6', 'line-width': 3, 'line-dasharray': [2, 1.5], 'line-opacity': 0.9 },
  })
  addLayerIfMissing(map, {
    id: STAGE_LAYER.CLUSTER_NOISE,
    type: 'circle',
    source: STAGE_SOURCE.CLUSTERS,
    filter: ['==', ['get', 'kind'], 'noise'],
    layout: { visibility: 'none' },
    paint: { 'circle-radius': 6, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#64748b', 'circle-stroke-width': 2 },
  })
  addLayerIfMissing(map, {
    id: STAGE_LAYER.CLUSTER_MEMBER,
    type: 'circle',
    source: STAGE_SOURCE.CLUSTERS,
    filter: ['==', ['get', 'kind'], 'member'],
    layout: { visibility: 'none' },
    paint: { 'circle-radius': 8, 'circle-color': '#8b5cf6', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.8 },
  })
  // Recent (<=14 d) cases: a soft red ring that expands and fades (animated
  // by startCasePulse). Display only -- its radius is not a spread distance.
  addLayerIfMissing(map, {
    id: STAGE_LAYER.NATIONAL_CASE_PULSE,
    type: 'circle',
    source: STAGE_SOURCE.NATIONAL_CASES,
    filter: ['==', ['get', 'ageClass'], 'RECENT'],
    layout: { visibility: 'none' },
    paint: { 'circle-radius': 8, 'circle-color': '#ef4444', 'circle-opacity': 0.35, 'circle-blur': 0.5, 'circle-stroke-color': '#ef4444', 'circle-stroke-width': 1.5, 'circle-stroke-opacity': 0.5 },
  }, STAGE_LAYER.NATIONAL_CASE)
}

/** Optional text labels (only when the basemap provides glyphs; the map
 * works without them). Kept here so MapLibreCanvas.jsx stays glyph-free. */
export const CORRIDOR_LABEL_LAYER_ID = 'page1-forecast-path-label'

/** The logged-in vet's district name over its highlighted polygon. */
export function addDistrictLabelLayer(map, sourceId) {
  if (!map.getStyle?.()?.glyphs) return
  addLayerIfMissing(map, {
    id: 'my-district-label',
    type: 'symbol',
    source: sourceId,
    layout: {
      'text-field': ['concat', ['upcase', ['coalesce', ['get', 'shapeName'], ['get', 'name'], '']], '\nYOUR DISTRICT'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 11,
      'text-letter-spacing': 0.08,
      'text-allow-overlap': false,
    },
    paint: { 'text-color': '#d1fae5', 'text-halo-color': '#064e3b', 'text-halo-width': 1.6 },
  })
}

/** "Day N · X km" along each backend direction corridor (where and how far). */
export function addCorridorLabelLayer(map, sourceId, visible) {
  if (!map.getStyle?.()?.glyphs) return
  addLayerIfMissing(map, {
    id: CORRIDOR_LABEL_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    layout: {
      visibility: visible ? 'visible' : 'none',
      'symbol-placement': 'line-center',
      'text-field': ['coalesce', ['get', 'pathLabel'], ''],
      'text-font': ['Noto Sans Bold'],
      'text-size': 11,
      'text-offset': [0, -0.9],
      'text-keep-upright': true,
    },
    paint: { 'text-color': '#f5f3ff', 'text-halo-color': '#4c1d95', 'text-halo-width': 1.8 },
  })
}

/** Trajectory "Day N · near <place>" labels (trajectoryLabels.js): at each
 * path front, and "Insufficient directional evidence" under a source without one. */
export function addTrajectoryLabelLayer(map, { id, sourceId, visibility }) {
  if (!map.getStyle?.()?.glyphs) return
  addLayerIfMissing(map, {
    id,
    type: 'symbol',
    source: sourceId,
    layout: {
      visibility,
      'text-field': ['get', 'label'],
      'text-font': ['Noto Sans Bold'],
      'text-size': 11.5,
      // Several cases close together each keep their own label: MapLibre tries
      // these anchors in turn until the label no longer collides.
      'text-variable-anchor': ['bottom', 'top', 'left', 'right', 'bottom-left', 'bottom-right', 'top-left', 'top-right'],
      'text-radial-offset': 1.1,
      'text-allow-overlap': false,
      'text-padding': 4,
    },
    paint: { 'text-color': '#f5f3ff', 'text-halo-color': '#3b0764', 'text-halo-width': 2 },
  })
}

/** Env mode: rain as a blue circle scaled by the reported millimetres, wind
 * as an arrow pointing where the air moves, and the values as text. */
export function addEnvironmentLayers(map) {
  ensureSources(map)
  if (!map.hasImage?.(WIND_ARROW_ICON_ID)) map.addImage?.(WIND_ARROW_ICON_ID, buildWindArrowImage())
  addLayerIfMissing(map, {
    id: STAGE_LAYER.ENV_RAIN,
    type: 'circle',
    source: STAGE_SOURCE.ENVIRONMENT,
    // Only a day with measurable rain gets the rain circle (0.0 mm = dry).
    filter: ['all', ['==', ['get', 'hasRain'], true], ['>', ['coalesce', ['get', 'rainMm'], 0], 0.2]],
    layout: { visibility: 'none' },
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['get', 'rainMm'], 0, 8, 5, 18, 15, 32, 40, 48],
      'circle-color': '#38bdf8',
      'circle-opacity': ['interpolate', ['linear'], ['get', 'rainMm'], 0, 0.12, 15, 0.38],
      'circle-stroke-color': '#7dd3fc',
      'circle-stroke-width': 1.2,
    },
  })
  // The district tinted by the selected day's condition (rain blue, sun warm,
  // wind cyan); RAF gently pulses it (startEnvironmentAnimation).
  addLayerIfMissing(map, {
    id: STAGE_LAYER.ENV_AREA,
    type: 'fill',
    source: STAGE_SOURCE.ENV_AREA,
    layout: { visibility: 'none' },
    paint: {
      'fill-color': ['match', ['get', 'condition'], 'RAIN', '#2563eb', 'STORM', '#1e3a8a', 'WINDY', '#06b6d4', 'CLOUDY', '#94a3b8', 'SUNNY', '#f59e0b', '#f59e0b'],
      'fill-opacity': ['get', 'tint'],
    },
  })
  // Hot, dry day (forecast high >= 30 C, < 1 mm rain; weatherForecast.heatIntensity):
  // a warm orange glow over the area plus soft heat-haze blobs rising through it.
  // Static strength here; startEnvironmentAnimation makes it breathe.
  addLayerIfMissing(map, {
    id: STAGE_LAYER.ENV_HEAT,
    type: 'fill',
    source: STAGE_SOURCE.ENV_AREA,
    filter: ['>', ['coalesce', ['get', 'heat'], 0], 0],
    layout: { visibility: 'none' },
    paint: { 'fill-color': '#f97316', 'fill-opacity': ['*', ['coalesce', ['get', 'heat'], 0], HEAT_GLOW_MAX_OPACITY] },
  })
  addLayerIfMissing(map, {
    id: STAGE_LAYER.ENV_HEAT_SHIMMER,
    type: 'circle',
    source: STAGE_SOURCE.ENV_PARTICLES,
    filter: ['==', ['get', 'kind'], 'heat'],
    layout: { visibility: 'none' },
    paint: { 'circle-radius': ['get', 'r'], 'circle-color': '#fb923c', 'circle-blur': 1, 'circle-opacity': ['get', 'o'] },
  })
  // Animated rain: rings pulse out of each observation, stronger with more
  // reported rainfall. The ring radius/opacity are per-frame DATA in the
  // particle source (startEnvironmentAnimation) -- a per-frame data-driven
  // setPaintProperty would make MapLibre reload the observation source every
  // frame, so it never finished loading and the rain/wind/label vanished.
  addLayerIfMissing(map, {
    id: STAGE_LAYER.ENV_RAIN_RIPPLE,
    type: 'circle',
    source: STAGE_SOURCE.ENV_PARTICLES,
    filter: ['==', ['get', 'kind'], 'ripple'],
    layout: { visibility: 'none' },
    paint: { 'circle-radius': ['get', 'r'], 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#7dd3fc', 'circle-stroke-width': 2, 'circle-stroke-opacity': ['get', 'o'] },
  })
  // Animated wind: small arrows drifting downwind, faster with stronger wind.
  addLayerIfMissing(map, {
    id: STAGE_LAYER.ENV_WIND_FLOW,
    type: 'symbol',
    source: STAGE_SOURCE.ENV_PARTICLES,
    filter: ['!', ['has', 'kind']], // wind particles only (ripples and heat blobs carry a kind)
    layout: {
      visibility: 'none',
      'icon-image': WIND_ARROW_ICON_ID,
      'icon-rotate': ['get', 'towardDeg'],
      'icon-rotation-alignment': 'map',
      'icon-size': 0.55,
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
    paint: { 'icon-opacity': ['get', 'fade'] },
  })
  addLayerIfMissing(map, {
    id: STAGE_LAYER.ENV_WIND,
    type: 'symbol',
    source: STAGE_SOURCE.ENVIRONMENT,
    filter: ['==', ['get', 'hasWind'], true],
    layout: {
      visibility: 'none',
      'icon-image': WIND_ARROW_ICON_ID,
      'icon-rotate': ['get', 'windTowardDeg'],
      'icon-rotation-alignment': 'map',
      'icon-size': ['interpolate', ['linear'], ['coalesce', ['get', 'windSpeed'], 0], 0, 0.7, 4, 1.1, 10, 1.6],
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
  })
  if (map.getStyle?.()?.glyphs) {
    addLayerIfMissing(map, {
      id: STAGE_LAYER.ENV_LABEL,
      type: 'symbol',
      source: STAGE_SOURCE.ENVIRONMENT,
      layout: {
        visibility: 'none',
        'text-field': ['get', 'label'],
        'text-font': ['Noto Sans Bold'],
        'text-size': 11,
        'text-offset': [0, 2.4],
        'text-allow-overlap': true,
      },
      paint: { 'text-color': '#e0f2fe', 'text-halo-color': '#0c4a6e', 'text-halo-width': 1.6 },
    })
  }
}

const RAIN_RIPPLE_CYCLE_MS = 1800
const ERA5_CELL_DEG = 0.25
const WIND_SEEDS_PER_SIDE = 6
const HEAT_GLOW_MAX_OPACITY = 0.75 // stays orange over the green district highlight
const HEAT_CYCLE_MS = 4200
const HEAT_BLOBS = 34

/** Env animation from the REAL values of the selected date: rain ripples
 * (intensity from the reported millimetres) and arrows drifting along the
 * reported wind direction at a pace scaled by the reported speed. RAF-driven
 * (this feature allows no timers). Returns a stop function. */
export function startEnvironmentAnimation(map, getEnvironment, { now = () => performance.now(), raf = (cb) => requestAnimationFrame(cb), caf = (id) => cancelAnimationFrame(id) } = {}) {
  let frameId = null
  const start = now()
  const tick = () => {
    if (!mapAlive(map) || !map.getLayer(STAGE_LAYER.ENV_RAIN_RIPPLE)) return
    const elapsed = now() - start
    const phase = (elapsed % RAIN_RIPPLE_CYCLE_MS) / RAIN_RIPPLE_CYCLE_MS
    const particles = []
    let heat = 0
    for (const feature of getEnvironment?.()?.features ?? []) {
      const p = feature.properties ?? {}
      const h = Number(p.heat)
      if (h > 0) {
        // Heat haze: blobs spread over the area, slowly rising and fading
        // (a constant set of seeds, so the pattern is calm, not random noise).
        heat = Math.max(heat, h)
        const [lon, lat] = feature.geometry.coordinates
        const span = Number(p.spanDeg) > 0 ? Number(p.spanDeg) : ERA5_CELL_DEG
        const blobs = Math.round(HEAT_BLOBS * (0.5 + 0.5 * h))
        for (let i = 0; i < blobs; i += 1) {
          const angle = i * 2.399963 // golden angle: even spread
          const radius = (span / 2) * Math.sqrt((i + 0.5) / blobs)
          const cycle = ((elapsed / HEAT_CYCLE_MS) + i * 0.137) % 1
          particles.push({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [lon + radius * Math.cos(angle), lat + radius * Math.sin(angle) + cycle * span * 0.08] },
            properties: { kind: 'heat', r: 16 + 20 * h, o: Math.sin(cycle * Math.PI) * (0.16 + 0.24 * h) },
          })
        }
      }
      const rain = Number(p.rainMm)
      if (p.hasRain && Number.isFinite(rain) && rain > 0.2) {
        // Ring size/strength from the reported millimetres (0 -> 15 mm).
        const k = Math.min(1, rain / 15)
        particles.push({ type: 'Feature', geometry: feature.geometry, properties: { kind: 'ripple', r: 10 + 16 * k + phase * 24, o: (1 - phase) * (0.15 + 0.8 * k) } })
      }
      if (!p.hasWind || !Number.isFinite(p.windTowardDeg)) continue
      const [lon, lat] = feature.geometry.coordinates
      const rad = (p.windTowardDeg * Math.PI) / 180
      const dx = Math.sin(rad)
      const dy = Math.cos(rad)
      // Seeds spread over the observation's own 0.25° ERA5 cell (the area the
      // value represents); each drifts downwind and wraps inside the cell.
      // Area the value represents: the ERA5 cell, or the whole district for a forecast.
      const span = Number(p.spanDeg) > 0 ? Number(p.spanDeg) : ERA5_CELL_DEG
      const seeds = Math.min(16, Math.max(WIND_SEEDS_PER_SIDE, Math.round((span / ERA5_CELL_DEG) * WIND_SEEDS_PER_SIDE * 0.6)))
      const pace = 0.00004 * Math.max(0.5, Number(p.windSpeed) || 0) * (ERA5_CELL_DEG / span)
      const half = span / 2
      for (let i = 0; i < seeds; i += 1) {
        for (let j = 0; j < seeds; j += 1) {
          const jitter = ((i * 7 + j * 13) % 10) / 10
          const along = ((elapsed * pace + jitter) % 1) * span - half
          const sx = ((i + 0.5) / seeds) * span - half
          const sy = ((j + 0.5) / seeds) * span - half
          const wrap = (v) => ((((v + half) % span) + span) % span) - half
          const x = wrap(sx + dx * along)
          const y = wrap(sy + dy * along)
          particles.push({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [lon + x, lat + y] },
            properties: { towardDeg: p.windTowardDeg, fade: Math.max(0, 1 - Math.max(Math.abs(x), Math.abs(y)) / half) * 0.9 },
          })
        }
      }
    }
    map.getSource(STAGE_SOURCE.ENV_PARTICLES)?.setData({ type: 'FeatureCollection', features: particles })
    // The glow breathes with a CONSTANT opacity value (one area feature): a
    // constant paint value never makes MapLibre reload the source.
    if (map.getLayer(STAGE_LAYER.ENV_HEAT) && heat > 0) map.setPaintProperty(STAGE_LAYER.ENV_HEAT, 'fill-opacity', heat * HEAT_GLOW_MAX_OPACITY * (0.78 + 0.22 * Math.sin(elapsed / 700)))
    frameId = raf(tick)
  }
  frameId = raf(tick)
  return () => {
    if (frameId != null) caf(frameId)
    frameId = null
    if (!mapAlive(map)) return
    map.getSource(STAGE_SOURCE.ENV_PARTICLES)?.setData(EMPTY_FEATURE_COLLECTION)
    if (map.getLayer(STAGE_LAYER.ENV_HEAT)) map.setPaintProperty(STAGE_LAYER.ENV_HEAT, 'fill-opacity', ['*', ['coalesce', ['get', 'heat'], 0], HEAT_GLOW_MAX_OPACITY])
  }
}

/** Trajectory flow (prototype "glowing particles flowing outward"): dots
 * travelling from each source along the backend's own land-clipped direction
 * line for the selected date. Added above the direction lines. */
export function addTrajectoryFlowLayers(map) {
  ensureSources(map)
  addLayerIfMissing(map, {
    id: STAGE_LAYER.TRAJECTORY_FLOW_GLOW,
    type: 'circle',
    source: STAGE_SOURCE.TRAJECTORY_FLOW,
    layout: { visibility: 'none' },
    paint: { 'circle-radius': 9, 'circle-color': '#a78bfa', 'circle-blur': 1, 'circle-opacity': ['*', 0.55, ['get', 'fade']] },
  })
  addLayerIfMissing(map, {
    id: STAGE_LAYER.TRAJECTORY_FLOW,
    type: 'circle',
    source: STAGE_SOURCE.TRAJECTORY_FLOW,
    layout: { visibility: 'none' },
    paint: { 'circle-radius': 3.4, 'circle-color': '#6d28d9', 'circle-stroke-color': '#ede9fe', 'circle-stroke-width': 1, 'circle-opacity': ['get', 'fade'], 'circle-stroke-opacity': ['get', 'fade'] },
  })
}

function lineCoordinates(geometry) {
  if (geometry?.type === 'LineString') return [geometry.coordinates]
  if (geometry?.type === 'MultiLineString') return geometry.coordinates
  return []
}

/** Point at fraction t (0..1) along a polyline, by planar length. */
export function pointAlong(coords, t) {
  if (!Array.isArray(coords) || coords.length < 2) return coords?.[0] ?? null
  const lengths = []
  let total = 0
  for (let i = 1; i < coords.length; i += 1) {
    const d = Math.hypot(coords[i][0] - coords[i - 1][0], coords[i][1] - coords[i - 1][1])
    lengths.push(d)
    total += d
  }
  let target = Math.max(0, Math.min(1, t)) * total
  for (let i = 0; i < lengths.length; i += 1) {
    if (target <= lengths[i] || i === lengths.length - 1) {
      const f = lengths[i] ? Math.min(1, target / lengths[i]) : 0
      return [coords[i][0] + (coords[i + 1][0] - coords[i][0]) * f, coords[i][1] + (coords[i + 1][1] - coords[i][1]) * f]
    }
    target -= lengths[i]
  }
  return coords.at(-1)
}

const FLOW_DOTS_PER_LINE = 4
const FLOW_CYCLE_MS = 2600

/** RAF-driven flow along the current direction lines. Returns a stop fn. */
export function startTrajectoryFlow(map, getPaths, { sourceId = STAGE_SOURCE.TRAJECTORY_FLOW, now = () => performance.now(), raf = (cb) => requestAnimationFrame(cb), caf = (id) => cancelAnimationFrame(id) } = {}) {
  let frameId = null
  const start = now()
  const tick = () => {
    if (!mapAlive(map) || !map.getSource(sourceId)) return
    const phase = ((now() - start) % FLOW_CYCLE_MS) / FLOW_CYCLE_MS
    const dots = []
    for (const feature of getPaths?.()?.features ?? []) {
      for (const coords of lineCoordinates(feature.geometry)) {
        for (let k = 0; k < FLOW_DOTS_PER_LINE; k += 1) {
          const t = (phase + k / FLOW_DOTS_PER_LINE) % 1
          const point = pointAlong(coords, t)
          if (point) dots.push({ type: 'Feature', geometry: { type: 'Point', coordinates: point }, properties: { fade: Math.sin(t * Math.PI) } })
        }
      }
    }
    map.getSource(sourceId).setData({ type: 'FeatureCollection', features: dots })
    frameId = raf(tick)
  }
  frameId = raf(tick)
  return () => {
    if (frameId != null) caf(frameId)
    frameId = null
    if (!mapAlive(map)) return
    map.getSource(sourceId)?.setData(EMPTY_FEATURE_COLLECTION)
  }
}

const CASE_PULSE_CYCLE_MS = 1800

/** Red pulse for recent cases: ring grows 6 -> 22 px and fades, repeating.
 * RAF only (no timers). Returns a stop function. */
export function startCasePulse(map, { now = () => performance.now(), raf = (cb) => requestAnimationFrame(cb), caf = (id) => cancelAnimationFrame(id) } = {}) {
  let frameId = null
  const start = now()
  const tick = () => {
    if (!mapAlive(map) || !map.getLayer(STAGE_LAYER.NATIONAL_CASE_PULSE)) return
    const phase = ((now() - start) % CASE_PULSE_CYCLE_MS) / CASE_PULSE_CYCLE_MS
    map.setPaintProperty(STAGE_LAYER.NATIONAL_CASE_PULSE, 'circle-radius', 6 + phase * 16)
    map.setPaintProperty(STAGE_LAYER.NATIONAL_CASE_PULSE, 'circle-opacity', 0.38 * (1 - phase))
    map.setPaintProperty(STAGE_LAYER.NATIONAL_CASE_PULSE, 'circle-stroke-opacity', 0.7 * (1 - phase))
    frameId = raf(tick)
  }
  frameId = raf(tick)
  return () => {
    if (frameId != null) caf(frameId)
    frameId = null
  }
}

/** Slow pulse under each source-case ring (Trajectory only). */
export function addOriginPulseLayer(map, { sourceId, beforeId }) {
  addLayerIfMissing(
    map,
    {
      id: STAGE_LAYER.ORIGIN_PULSE,
      type: 'circle',
      source: sourceId,
      layout: { visibility: 'none' },
      paint: {
        'circle-radius': 8,
        'circle-color': '#2dd4bf',
        'circle-opacity': 0,
        'circle-blur': 0.4,
        'circle-radius-transition': { duration: 0 },
        'circle-opacity-transition': { duration: 0 },
      },
    },
    beforeId,
  )
}

/** Pushes one stage view model (selected day) into the map sources. */
export function updateStageData(map, stage, cellFader) {
  if (!mapAlive(map)) return
  map.getSource(STAGE_SOURCE.BASELINE)?.setData(stage?.baselineZones ?? EMPTY_FEATURE_COLLECTION)
  map.getSource(STAGE_SOURCE.NATIONAL_CASES)?.setData(stage?.nationalCases ?? EMPTY_FEATURE_COLLECTION)
  map.getSource(STAGE_SOURCE.HISTORY)?.setData(stage?.reachHistory ?? EMPTY_FEATURE_COLLECTION)
  map.getSource(STAGE_SOURCE.CLUSTERS)?.setData(stage?.clusters ?? EMPTY_FEATURE_COLLECTION)
  map.getSource(STAGE_SOURCE.ENVIRONMENT)?.setData(stage?.environment ?? EMPTY_FEATURE_COLLECTION)
  map.getSource(STAGE_SOURCE.ENV_AREA)?.setData(stage?.environmentArea ?? EMPTY_FEATURE_COLLECTION)
  cellFader?.show(stage?.monitoringZones ?? stage?.riskCells ?? EMPTY_FEATURE_COLLECTION)
}

/** The ONLY place mode-scoped stage-layer visibility is decided. */
export function applyStageVisibility(map, mode) {
  if (!mapAlive(map)) return
  const visible = new Set(MODE_LAYERS[mode] ?? [])
  for (const id of MODE_SCOPED_LAYERS) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible.has(id) ? 'visible' : 'none')
  }
}

/** RAF-driven pulse (no timers: this feature forbids them). Returns a stop fn. */
export function startOriginPulse(map, { now = () => performance.now(), raf = (cb) => requestAnimationFrame(cb), caf = (id) => cancelAnimationFrame(id) } = {}) {
  let frameId = null
  const start = now()
  const tick = () => {
    if (!mapAlive(map) || !map.getLayer(STAGE_LAYER.ORIGIN_PULSE)) return
    const phase = ((now() - start) % PULSE_CYCLE_MS) / PULSE_CYCLE_MS
    map.setPaintProperty(STAGE_LAYER.ORIGIN_PULSE, 'circle-radius', 8 + phase * 18)
    map.setPaintProperty(STAGE_LAYER.ORIGIN_PULSE, 'circle-opacity', 0.45 * (1 - phase))
    frameId = raf(tick)
  }
  frameId = raf(tick)
  return () => {
    if (frameId != null) caf(frameId)
    frameId = null
    if (!mapAlive(map)) return
    if (map.getLayer(STAGE_LAYER.ORIGIN_PULSE)) map.setPaintProperty(STAGE_LAYER.ORIGIN_PULSE, 'circle-opacity', 0)
  }
}
