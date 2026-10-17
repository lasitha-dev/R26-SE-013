import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ANALYSIS_BASIS, buildAnalysisBasisOptions, selectedBasisOption } from '../adapters/spatialStory'
import { openOperationalEventStream } from '../api/operationalEventsApi'
import {
  DATA_CHANGE_DEBOUNCE_MS,
  DATA_CHANGE_KINDS,
  DATA_CHANGE_MAX_WAIT_MS,
  dataChangedReceived,
  flushIfDue,
  initialDataChangeState,
  readyReceived,
  sessionChanged,
} from '../context/dataChangeReconciler'
import { nationalCasesEventKey } from '../context/useNationalCases'

const change = (kind, version, extra = {}) => ({ change: kind, record_key: 'CASE:abc', disease: 'LSD', previous_disease: null, verified: true, data_version: version, refetch: ['spatial-timeline'], ...extra })

describe('realtime data change: SSE dispatch', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window
  beforeEach(() => {
    global.window = { localStorage: { getItem: vi.fn().mockReturnValue('tok') } }
  })
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('routes geospatial_data_changed frames to onDataChanged (never to onEvent)', async () => {
    const encoder = new TextEncoder()
    const frames = [
      'event: ready\ndata: {"transport":"delta_refresh","data_version":"ds_1"}\n\n',
      ...DATA_CHANGE_KINDS.map((kind, i) => `event: geospatial_data_changed\ndata: ${JSON.stringify(change(kind, `ds_${i + 2}`))}\n\n`),
    ]
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: new ReadableStream({ start(c) { frames.forEach((f) => c.enqueue(encoder.encode(f))); c.close() } }),
    })
    const ready = []
    const changes = []
    const events = []
    await openOperationalEventStream({ onReady: (d) => ready.push(d), onDataChanged: (d) => changes.push(d.change), onEvent: (e) => events.push(e) })
    expect(ready).toEqual([{ transport: 'delta_refresh', data_version: 'ds_1' }])
    expect(changes).toEqual(['CREATED', 'VERIFIED', 'UNVERIFIED', 'RECLASSIFIED', 'CORRECTED', 'DELETED'])
    expect(events).toEqual([])
  })
})

describe('realtime data change: reconciler (pure)', () => {
  it('first ready only records the version; same version on reconnect does nothing', () => {
    let s = readyReceived(initialDataChangeState, 'ds_1', 0)
    expect(s.dataVersion).toBe('ds_1')
    expect(s.dueAt).toBeNull()
    s = readyReceived(s, 'ds_1', 10)
    expect(s.dueAt).toBeNull()
    expect(flushIfDue(s, 1e9).token).toBe(0)
  })

  it('a changed version on reconnect schedules one refetch', () => {
    let s = readyReceived(initialDataChangeState, 'ds_1', 0)
    s = readyReceived(s, 'ds_2', 100)
    expect(s.dataVersion).toBe('ds_2')
    expect(flushIfDue(s, 100 + DATA_CHANGE_DEBOUNCE_MS - 1)).toBe(s)
    expect(flushIfDue(s, 100 + DATA_CHANGE_DEBOUNCE_MS).token).toBe(1)
  })

  it('every change kind schedules a refetch; bursts are debounced into one token', () => {
    let s = readyReceived(initialDataChangeState, 'ds_1', 0)
    DATA_CHANGE_KINDS.forEach((kind, i) => { s = dataChangedReceived(s, change(kind, `ds_${i + 2}`), i * 100) })
    expect(s.dataVersion).toBe('ds_7')
    expect(s.pendingChanges.map((c) => c.change)).toEqual(DATA_CHANGE_KINDS)
    const flushed = flushIfDue(s, 500 + DATA_CHANGE_DEBOUNCE_MS)
    expect(flushed.token).toBe(1)
    expect(flushed.lastApplied.changes).toHaveLength(6)
    expect(flushIfDue(flushed, 1e9)).toBe(flushed) // nothing left pending
  })

  it('a continuous stream of changes still refetches within the max wait', () => {
    let s = initialDataChangeState
    for (let t = 0; t <= DATA_CHANGE_MAX_WAIT_MS; t += 500) s = dataChangedReceived(s, change('CREATED', `v${t}`), t)
    expect(s.dueAt).toBeLessThanOrEqual(DATA_CHANGE_MAX_WAIT_MS)
  })

  it('ignores unknown kinds and malformed frames', () => {
    expect(dataChangedReceived(initialDataChangeState, { change: 'SOMETHING' }, 0)).toBe(initialDataChangeState)
    expect(dataChangedReceived(initialDataChangeState, null, 0)).toBe(initialDataChangeState)
    expect(readyReceived(initialDataChangeState, undefined, 0)).toBe(initialDataChangeState)
  })

  it('a session change drops the version history and pending work', () => {
    let s = dataChangedReceived(readyReceived(initialDataChangeState, 'ds_1', 0), change('DELETED', 'ds_2'), 0)
    s = sessionChanged(s)
    expect(s).toEqual(initialDataChangeState)
  })

  it('national cases refetch key changes on a data change and stays null when idle', () => {
    expect(nationalCasesEventKey({ lastEvent: null, dataChangeToken: 0 })).toBeNull()
    expect(nationalCasesEventKey({ lastEvent: null, dataChangeToken: 2 })).toBe('|2')
    expect(nationalCasesEventKey({ lastEvent: { event_id: 'e1' }, dataChangeToken: 2 })).toBe('e1|2')
  })
})

describe('analysis date: vet-chosen past date (districts without own cases)', () => {
  it('is offered only when allowed, defaults to today and never borrows another district', () => {
    expect(buildAnalysisBasisOptions().map((o) => o.id)).toEqual([ANALYSIS_BASIS.LIVE])
    const options = buildAnalysisBasisOptions({ allowCustom: true, today: '2026-10-15' })
    const custom = selectedBasisOption(options, ANALYSIS_BASIS.CUSTOM)
    expect(custom.asOf).toBe('2026-10-15')
    expect(custom.label).toBe('Choose a date…')
  })

  it('uses the chosen date as the backend as_of', () => {
    const options = buildAnalysisBasisOptions({ allowCustom: true, customDate: '2026-08-31', today: '2026-10-15' })
    const custom = selectedBasisOption(options, ANALYSIS_BASIS.CUSTOM)
    expect(custom.asOf).toBe('2026-08-31')
    expect(custom.label).toMatch(/^Chosen date · /)
  })
})
