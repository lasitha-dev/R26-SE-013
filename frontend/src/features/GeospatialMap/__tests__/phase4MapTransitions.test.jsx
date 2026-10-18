import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  buildMyAreaTimelineView,
  buildNationalTimelineLayers,
  TIER_TO_RISK_LEVEL,
  plateauNote,
  plateauStartIndex,
} from '../adapters/spatialTimelineView'
import CorridorPopup from '../components/CorridorPopup'
import {
  DIRECTION_ARROW_ICON_ID,
  EMPTY_FEATURE_COLLECTION,
  FLOW_DASH_SEQUENCE,
  buildDirectionArrowIcon,
  createRiskZoneCrossFader,
  directionArrowLayout,
  geometrySignature,
  lineLengthKm,
  revealCorridorStep,
  runCorridorReveal,
  scaledOpacity,
  sliceLineToFraction,
  startFlowDash,
} from '../components/mapFrameTransitions'
import TimelineControl from '../components/TimelineControl'
import mataraTimeline from './fixtures/spatialTimeline.matara.json'
import nationalTimeline from './fixtures/spatialTimeline.national.json'

// Fixtures: real Phase 2 engine output for two FICTIONAL test farms (see fixtures/README).
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const read = (...parts) => readFileSync(join(ROOT, ...parts), 'utf8')

/** Minimal MapLibre stand-in recording every source/paint call. */
function fakeMap(layerIds) {
  const data = new Map()
  const paint = new Map()
  const calls = []
  return {
    data,
    paint,
    calls,
    getLayer: (id) => (layerIds.includes(id) ? { id } : undefined),
    getSource: (id) => ({ setData: (value) => { data.set(id, value); calls.push(['setData', id, value]) } }),
    setPaintProperty: (id, property, value) => { paint.set(`${id}:${property}`, value); calls.push(['paint', id, property, value]) },
    getLayoutProperty: () => 'visible',
  }
}

/** Manual RAF clock: `step(ms)` advances time and runs the queued callbacks. */
function manualClock() {
  let time = 0
  let nextId = 1
  const queue = new Map()
  return {
    now: () => time,
    raf: (cb) => { const id = nextId; nextId += 1; queue.set(id, cb); return id },
    caf: (id) => { queue.delete(id) },
    pending: () => queue.size,
    step(ms) {
      time += ms
      const callbacks = [...queue.values()]
      queue.clear()
      for (const cb of callbacks) cb(time)
    },
  }
}

const BUFFERS = () => [
  { sourceId: 'risk-a', layers: [{ id: 'fill-a', property: 'fill-opacity', role: 'fill', base: ['get', 'o'] }, { id: 'line-a', property: 'line-opacity', role: 'line', base: 0.6 }] },
  { sourceId: 'risk-b', layers: [{ id: 'fill-b', property: 'fill-opacity', role: 'fill', base: ['get', 'o'] }, { id: 'line-b', property: 'line-opacity', role: 'line', base: 0.6 }] },
]
const LAYERS = ['fill-a', 'line-a', 'fill-b', 'line-b']
// Distinct backend collections per day (reach-limited zones) to exercise the
// generic cross-fader; the map's own risk zones are static and never fade.
const frameZones = (day) => ({
  type: 'FeatureCollection',
  features: nationalTimeline.frames[day].reach_limited_risk_zones.features.map((f) => ({ ...f, properties: { ...f.properties, riskLevel: TIER_TO_RISK_LEVEL[f.properties.tier] } })),
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('risk-zone cross-fade (exact backend polygons, opacity only)', () => {
  it('first frame is instant; the next frame cross-fades A -> B over the duration and settles', () => {
    const map = fakeMap(LAYERS)
    const clock = manualClock()
    const fader = createRiskZoneCrossFader({ map, buffers: BUFFERS(), durationMs: 400, ...clock })
    const day1 = frameZones(1)
    const day2 = frameZones(2)
    expect(fader.show(day1)).toBe('INSTANT')
    expect(map.data.get('risk-a')).toBe(day1) // the backend collection itself, untouched
    expect(fader.show(day2)).toBe('CROSSFADE')
    expect(map.data.get('risk-b')).toBe(day2)
    const seen = []
    for (let i = 0; i < 4; i += 1) {
      clock.step(100)
      seen.push(fader.debugState().alphas)
    }
    // incoming rises, outgoing falls, monotonically, and they finish at 1/0
    for (let i = 1; i < seen.length; i += 1) {
      expect(seen[i][1]).toBeGreaterThanOrEqual(seen[i - 1][1])
      expect(seen[i][0]).toBeLessThanOrEqual(seen[i - 1][0])
    }
    expect(fader.debugState()).toMatchObject({ alphas: [0, 1], active: 1, animating: false })
    expect(map.data.get('risk-a')).toBe(EMPTY_FEATURE_COLLECTION) // the faded-out buffer is released
    expect(map.paint.get('fill-b:fill-opacity')).toEqual(['get', 'o']) // full alpha = base expression untouched
  })

  it('every polygon ever handed to MapLibre is an exact backend frame (or empty)', () => {
    const map = fakeMap(LAYERS)
    const clock = manualClock()
    const fader = createRiskZoneCrossFader({ map, buffers: BUFFERS(), durationMs: 300, ...clock })
    const frames = [1, 2, 3, 4, 5].map(frameZones)
    for (const frame of frames) {
      fader.show(frame)
      clock.step(120)
    }
    clock.step(1000)
    const backend = new Set(frames)
    for (const [kind, , value] of map.calls) {
      if (kind === 'setData') expect(backend.has(value) || value === EMPTY_FEATURE_COLLECTION).toBe(true)
    }
  })

  it('a plateau frame (identical backend geometry) is left completely untouched', () => {
    expect(geometrySignature(frameZones(8))).toBe(geometrySignature(frameZones(14)))
    const map = fakeMap(LAYERS)
    const clock = manualClock()
    const fader = createRiskZoneCrossFader({ map, buffers: BUFFERS(), durationMs: 300, ...clock })
    fader.show(frameZones(7))
    clock.step(1000)
    const before = map.calls.length
    for (const day of [8, 9, 10, 11, 12, 13, 14]) expect(fader.show(frameZones(day))).toBe('UNCHANGED')
    expect(map.calls.length).toBe(before)
    expect(clock.pending()).toBe(0)
  })

  it('rapid scrubbing supersedes a running fade: one RAF, the stale buffer drops to 0, last frame wins', () => {
    const map = fakeMap(LAYERS)
    const clock = manualClock()
    const fader = createRiskZoneCrossFader({ map, buffers: BUFFERS(), durationMs: 400, ...clock })
    fader.show(frameZones(1))
    fader.show(frameZones(2))
    clock.step(100) // B partly visible
    fader.show(frameZones(5))
    fader.show(frameZones(6))
    expect(clock.pending()).toBe(1)
    clock.step(1000)
    const { active, alphas } = fader.debugState()
    expect(alphas[active]).toBe(1)
    expect(geometrySignature(map.data.get(active === 0 ? 'risk-a' : 'risk-b'))).toBe(geometrySignature(frameZones(6)))
    expect(map.data.get(active === 0 ? 'risk-b' : 'risk-a')).toBe(EMPTY_FEATURE_COLLECTION)
  })

  it('reduced motion applies every frame instantly with no animation frame', () => {
    const map = fakeMap(LAYERS)
    const clock = manualClock()
    let reduce = true
    const fader = createRiskZoneCrossFader({ map, buffers: BUFFERS(), durationMs: 400, reduceMotion: () => reduce, ...clock })
    fader.show(frameZones(1))
    expect(fader.show(frameZones(2))).toBe('INSTANT')
    expect(clock.pending()).toBe(0)
    reduce = false
    expect(fader.show(frameZones(3))).toBe('CROSSFADE')
  })

  it('destroy cancels a pending fade and ignores later frames (no leak after unmount)', () => {
    const map = fakeMap(LAYERS)
    const clock = manualClock()
    const fader = createRiskZoneCrossFader({ map, buffers: BUFFERS(), durationMs: 400, ...clock })
    fader.show(frameZones(1))
    fader.show(frameZones(2))
    expect(clock.pending()).toBe(1)
    fader.destroy()
    expect(clock.pending()).toBe(0)
    const before = map.calls.length
    expect(fader.show(frameZones(3))).toBe('UNCHANGED')
    expect(map.calls.length).toBe(before)
  })

  it('the ambient pulse multiplies the current fade alpha instead of overwriting it', () => {
    const map = fakeMap(LAYERS)
    const clock = manualClock()
    const fader = createRiskZoneCrossFader({ map, buffers: BUFFERS(), durationMs: 400, ...clock })
    fader.show(frameZones(1))
    fader.show(frameZones(2))
    clock.step(200)
    fader.setBase('fill', ['get', 'pulse'])
    const value = map.paint.get('fill-b:fill-opacity')
    expect(value[0]).toBe('*')
    expect(value[1]).toBeGreaterThan(0)
    expect(value[1]).toBeLessThan(1)
    expect(value[2]).toEqual(['get', 'pulse'])
    expect(scaledOpacity(0.5, 0.6)).toBe(0.3)
    expect(scaledOpacity(1, ['get', 'x'])).toEqual(['get', 'x'])
  })
})

describe('corridor reveal stays on the backend corridor', () => {
  const corridor = (day) => buildNationalTimelineLayers(nationalTimeline, day)

  it('a slice is a prefix of the backend vertices, ending on the backend line', () => {
    const geometry = corridor(3).paths.features[0].geometry
    const half = sliceLineToFraction(geometry, 0.5)
    const coords = half.coordinates
    for (const vertex of coords.slice(0, -1)) expect(geometry.coordinates).toContainEqual(vertex)
    expect(lineLengthKm(half)).toBeCloseTo(lineLengthKm(geometry) / 2, 3)
    expect(sliceLineToFraction(geometry, 1)).toBe(geometry)
  })

  it('grows from the previous day length to the exact next corridor; fronts ride the visible end', () => {
    const previous = corridor(3)
    const next = corridor(4)
    const start = revealCorridorStep(previous.paths, next.paths, next.fronts, 0)
    expect(lineLengthKm(start.paths.features[0].geometry)).toBeCloseTo(lineLengthKm(previous.paths.features[0].geometry), 1)
    const end = revealCorridorStep(previous.paths, next.paths, next.fronts, 1)
    expect(end.paths.features.map((f) => f.geometry)).toEqual(next.paths.features.map((f) => f.geometry))
    for (const step of [start, end]) {
      step.fronts.features.forEach((front, i) => expect(front.geometry.coordinates).toEqual(step.paths.features[i].geometry.coordinates.at(-1)))
    }
    // Going backwards retracts along the previous corridor and ends exactly on the earlier frame.
    const back = revealCorridorStep(next.paths, previous.paths, previous.fronts, 1)
    expect(back.paths.features.map((f) => f.geometry)).toEqual(previous.paths.features.map((f) => f.geometry))
  })

  it('runner: reduced motion applies the exact backend collections at once; cancel stops the RAF', () => {
    const apply = vi.fn()
    const next = corridor(5)
    runCorridorReveal({ previous: corridor(4), next, apply, reduceMotion: true })
    expect(apply).toHaveBeenCalledTimes(1)
    expect(apply.mock.calls[0][0].paths).toBe(next.paths)
    const clock = manualClock()
    const cancel = runCorridorReveal({ previous: corridor(4), next, apply, durationMs: 400, ...clock })
    expect(clock.pending()).toBe(1)
    cancel()
    expect(clock.pending()).toBe(0)
  })

  it('arrow direction: each corridor runs from its source along the backend bearing', () => {
    const layers = corridor(5)
    for (const path of layers.paths.features) {
      const [[lon0, lat0], [lon1, lat1]] = [path.geometry.coordinates[0], path.geometry.coordinates.at(-1)]
      const source = nationalTimeline.sources.find((s) => s.source_id === path.properties.sourceId)
      expect([lon0, lat0]).toEqual([source.longitude, source.latitude]) // origin connection
      const dx = (lon1 - lon0) * Math.cos((lat0 * Math.PI) / 180)
      const bearing = ((Math.atan2(dx, lat1 - lat0) * 180) / Math.PI + 360) % 360
      expect(Math.abs(bearing - path.properties.bearingDeg)).toBeLessThan(1.5)
    }
    const layout = directionArrowLayout('visible')
    expect(layout['icon-image']).toBe(DIRECTION_ARROW_ICON_ID)
    expect(layout['icon-rotate']).toEqual(['coalesce', ['get', 'bearingDeg'], 0])
    expect(layout['icon-rotation-alignment']).toBe('map')
  })

  it('the arrow icon points north (opaque tip at top centre, open notch below)', () => {
    const icon = buildDirectionArrowIcon(22)
    expect(icon.data).toHaveLength(22 * 22 * 4)
    const alpha = (x, y) => icon.data[(y * 22 + x) * 4 + 3]
    expect(alpha(11, 4)).toBeGreaterThan(200)
    expect(alpha(11, 20)).toBe(0)
    expect(alpha(1, 1)).toBe(0)
  })

  it('flow dash steps only while the map is available and stops cleanly', () => {
    const map = fakeMap(['flow'])
    const clock = manualClock()
    let available = false
    const stop = startFlowDash({ getMap: () => (available ? map : null), layerIds: ['flow'], ...clock })
    clock.step(100)
    expect(map.calls).toHaveLength(0)
    available = true
    clock.step(100)
    expect(map.calls.at(-1)).toEqual(['paint', 'flow', 'line-dasharray', FLOW_DASH_SEQUENCE[1]])
    stop()
    expect(clock.pending()).toBe(0)
  })
})

describe('plateau, origins and My Area layer split come from backend data', () => {
  it('plateau starts at Day 7 for both fixtures (geometry identical afterwards) and is labelled', () => {
    expect(plateauStartIndex(mataraTimeline)).toBe(7)
    expect(plateauStartIndex(nationalTimeline)).toBe(7)
    expect(plateauNote(mataraTimeline, 6)).toBeNull()
    expect(plateauNote(mataraTimeline, 12)).toBe('Reach covers scored area from Day 7')
    const growing = structuredClone(mataraTimeline)
    growing.frames[14].reach_limited_risk_zones.features = []
    expect(plateauStartIndex(growing)).toBeNull()
  })

  it('every backend source is an origin; an indeterminate direction keeps the origin but draws no corridor', () => {
    const indeterminate = structuredClone(nationalTimeline)
    indeterminate.source_directions[0].bearing_deg = null
    for (const frame of indeterminate.frames) {
      frame.source_corridors = frame.source_corridors.filter((c) => c.source_id !== indeterminate.source_directions[0].source_id)
    }
    const layers = buildNationalTimelineLayers(indeterminate, 5)
    expect(layers.origins.features).toHaveLength(indeterminate.sources.length)
    const origin = layers.origins.features.find((f) => f.properties.sourceId === indeterminate.source_directions[0].source_id)
    expect(origin.properties.directionStatus).toBe('NO_DIRECTIONAL_TENDENCY')
    expect(layers.paths.features.some((f) => f.properties.sourceId === origin.properties.sourceId)).toBe(false)
    expect(layers.fronts.features.some((f) => f.properties.sourceId === origin.properties.sourceId)).toBe(false)
  })

  it('My Area: static tiers stay in the context layer; the bright zones and red reach outline follow the day', () => {
    const day2 = buildMyAreaTimelineView(mataraTimeline, 2, 'Matara')
    const day9 = buildMyAreaTimelineView(mataraTimeline, 9, 'Matara')
    const staticContext = (view) => view.contextZones.features.filter((f) => f.properties.riskLevel !== 'reach')
    expect(staticContext(day2)).toEqual(staticContext(day9))
    const reach = (view) => view.contextZones.features.find((f) => f.properties.riskLevel === 'reach')
    expect(reach(day2).geometry).toEqual(mataraTimeline.frames[2].reach_envelope)
    expect(reach(day9).geometry).toEqual(mataraTimeline.frames[9].reach_envelope)
    expect(reach(day9).properties.label).toMatch(/^\d{1,2} [A-Z][a-z]{2} · \d+\.\d km reach$/)
    expect(day2.riskZones.features.every((f) => f.properties.layerRole === 'SCORED_LAND_WITHIN_NOMINAL_REACH' && f.properties.day === 2)).toBe(true)
    expect(day9.plateauNote).toBe('Reach covers scored area from Day 7')
  })
})

describe('timeline controls', () => {
  const dates = mataraTimeline.frames.map((f) => f.date)
  const renderTimeline = (props) => render(
    <TimelineControl presentationDates={dates} activeIndex={3} isPlaybackActive={false} datasetLabel="Relative spatial risk" onChangeSpeed={vi.fn()} playbackSpeed={1} {...props} />,
  )

  it('keyboard: arrows step, Home/End jump, Space toggles playback', () => {
    const onSelectDay = vi.fn()
    const onPlay = vi.fn()
    renderTimeline({ onSelectDay, onPlay, onPause: vi.fn() })
    const group = screen.getByRole('group', { name: 'Relative spatial risk timeline' })
    fireEvent.keyDown(group, { key: 'ArrowRight' })
    fireEvent.keyDown(group, { key: 'ArrowLeft' })
    fireEvent.keyDown(group, { key: 'End' })
    fireEvent.keyDown(group, { key: 'Home' })
    expect(onSelectDay.mock.calls.map(([index]) => index)).toEqual([4, 2, 14, 0])
    fireEvent.keyDown(group, { key: ' ' })
    expect(onPlay).toHaveBeenCalledTimes(1)
  })

  it('stops at the last frame: Play/Next disabled, "Timeline complete", plateau badge visible', () => {
    renderTimeline({ activeIndex: 14, onSelectDay: vi.fn(), onPlay: vi.fn(), onPause: vi.fn(), plateauLabel: plateauNote(mataraTimeline, 14) })
    expect(screen.getByRole('button', { name: 'Play' }).disabled).toBe(true)
    expect(screen.getByRole('button', { name: 'Next day' }).disabled).toBe(true)
    expect(screen.getByText('Timeline complete · 27 OCT 2026')).toBeTruthy()
    expect(screen.getByText('Reach covers scored area from Day 7')).toBeTruthy()
  })
})

describe('corridor tooltip', () => {
  it('shows source, disease, type, status, bearing, reach interval and limitations; indeterminate says so', () => {
    const path = buildNationalTimelineLayers(nationalTimeline, 9).paths.features[0].properties
    const { unmount } = render(<CorridorPopup corridor={path} onClose={vi.fn()} />)
    const text = document.body.textContent
    expect(text).toContain(path.sourceId)
    expect(text).toContain('Lumpy skin disease')
    expect(text).toContain('Vet-verified case')
    expect(text).toContain('Exploratory extension (Day 8–14)')
    expect(text).toMatch(/\d+° (N|NE|E|SE|S|SW|W|NW)/)
    expect(text).toMatch(/35\.5 km \(\d+\.\d–\d+\.\d\)/)
    expect(text).toContain('not a disease boundary')
    unmount()
    render(<CorridorPopup corridor={{ sourceId: 'HIST:1', bearingDeg: null, lengthKm: 4, day: 1 }} pinned={false} />)
    expect(document.body.textContent).toContain('No directional tendency')
    expect(document.body.textContent).toContain('Click to pin')
  })
})

describe('camera stability and cleanup (structural)', () => {
  const page1 = read('components', 'MapLibreCanvas.jsx')
  const myArea = read('components', 'MyAreaMapCanvas.jsx')
  const between = (source, start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)))

  it('frame-change effects never move the camera', () => {
    const page1Effect = between(page1, 'Page-1 timeline frame changes (Phase 4)', 'Selected-source emphasis')
    const myAreaEffect = between(myArea, 'Phase 4: static context set in place', '}, [areaForecastVisualization, showAreaImpact, mapLoaded])')
    for (const effect of [page1Effect, myAreaEffect]) {
      expect(effect.length).toBeGreaterThan(200)
      expect(effect).not.toMatch(/fitBounds|easeTo|flyTo|jumpTo|setCenter|setZoom|new maplibregl\.Map/)
    }
    expect(myArea.split('fitBounds(').length - 1).toBe(1)
  })

  it('every transition loop is cancelled on unmount', () => {
    expect(page1).toContain('page1RiskFaderRef.current?.destroy()')
    expect(page1).toContain('page1RevealCancelRef.current?.()')
    expect(myArea).toContain('riskFaderRef.current?.destroy()')
    expect(myArea).toContain('revealCancelRef.current?.()')
    // No travelling-dash loop is started any more (a geometric tendency is
    // not movement), so there is nothing to cancel for it.
    expect(page1).not.toContain('startFlowDash(')
    expect(myArea).not.toContain('startFlowDash(')
  })
})

describe('Analysis & Trends keeps its historical purpose (text clarification only)', () => {
  it('Forecast Horizon reads the shared backend spatial timeline (no map-only code on the page)', () => {
    const page = read('pages', 'AnalysisTrendsPage.jsx')
    expect(page).toContain('useSpatialTimeline(')
    expect(page).toContain('forecastHorizon(timeline.data)')
    expect(page).not.toMatch(/spatialTimelineView|mapFrameTransitions/)
  })
})
