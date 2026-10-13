import { describe, expect, it } from 'vitest'
import { PHASE, initialSnapshotState, isTransportUsable, snapshotAssemblyReducer } from '../state/snapshotAssembly'

const SNAPSHOT_ID = 'cc92c6f716b7c2d04a2f4c18a893e87757876611e1068d9b0c526ae8853e8598'
const REQ = 'req-1'
const ORIGIN = 'ORIGIN:Afghanistan:2022-05-29'

const CONTRACT_OK = Object.freeze({ status: 'PROTOCOL_COMPATIBLE', reasons: [] })
const CONTRACT_MISMATCH = Object.freeze({ status: 'SNAPSHOT_METADATA_CONTRACT_MISMATCH', reasons: ['runtime_data_mode mismatch'] })

function cellFeature(id, bearing) {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [70.05, 35.34] },
    properties: {
      scientific_cell_id: id,
      scientific_crs: 'EPSG:32642',
      risk: { raw_c0_score: 0.4, score_status: 'SCORED', semantics: 'RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY' },
      direction: { method_id: 'x', method_version: '8B.3', bearing_deg: bearing, directional_clarity: 1.0, directional_input_coverage: 1.0, direction_status: 'DIRECTIONAL_RESULTANT_DEFINED', direction_semantics: 'x' },
    },
  }
}

function beginFrame({ requestId = REQ, snapshotId = SNAPSHOT_ID, forecastOriginId = ORIGIN, nCells = 2, nChunks = 1, nSources = 1 } = {}) {
  return {
    type: 'snapshot_begin', request_id: requestId, snapshot_id: snapshotId, forecast_origin_id: forecastOriginId,
    active_api_protocol_hash_10a1: 'x', transport_protocol_hash_10b: 'x', active_transport_protocol_hash_10b1: 'x',
    runtime_data_mode: 'HISTORICAL_RETROSPECTIVE_REPLAY', live_operational_analysis_status: 'NOT_IMPLEMENTED_NO_ACTUAL_OPERATIONAL_AVAILABILITY_PIPELINE',
    n_sources: nSources, n_cells: nCells, cell_chunk_size: 500, n_cell_chunks: nChunks, cache_status: 'MISS_COMPUTED', generated_at_utc: '2026-01-01T00:00:00+00:00',
  }
}

/** Mirrors what `useGeospatialSnapshot.js` actually dispatches: the raw
 * frame plus the ALREADY-COMPUTED contract-compatibility result (Part 3).
 * Defaults to a passing contract so tests unrelated to Part 3 don't need
 * to think about it. */
function beginEvent(frameOverrides = {}, contractCompatibility = CONTRACT_OK) {
  return { type: 'WS_FRAME_SNAPSHOT_BEGIN', payload: { frame: beginFrame(frameOverrides), contractCompatibility } }
}

function summaryFrame({ requestId = REQ, snapshotId = SNAPSHOT_ID } = {}) {
  return { type: 'summary', request_id: requestId, snapshot_id: snapshotId, data: { analysis_metadata: {}, apparent_rate_context: {}, nominal_reach_by_day: [] } }
}

function sourcesFrame({ requestId = REQ, snapshotId = SNAPSHOT_ID, n = 1 } = {}) {
  const features = Array.from({ length: n }, (_, i) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [70.0, 35.0] }, properties: { source_id: `S${i}` } }))
  return { type: 'sources', request_id: requestId, snapshot_id: snapshotId, data: { type: 'FeatureCollection', features } }
}

function chunkFrame({ requestId = REQ, snapshotId = SNAPSHOT_ID, chunkIndex, nChunks = 1, features }) {
  return { type: 'cells_chunk', request_id: requestId, snapshot_id: snapshotId, chunk_index: chunkIndex, n_chunks: nChunks, features }
}

function endFrame({ requestId = REQ, snapshotId = SNAPSHOT_ID, nSourcesSent = 1, nCellsSent = 2, nChunksSent = 1, verified = true } = {}) {
  return { type: 'snapshot_end', request_id: requestId, snapshot_id: snapshotId, n_sources_sent: nSourcesSent, n_cells_sent: nCellsSent, n_cell_chunks_sent: nChunksSent, scientific_content_hash_verified: verified }
}

function driveHappyPath(state, { requestId = REQ, snapshotId = SNAPSHOT_ID } = {}) {
  let s = snapshotAssemblyReducer(state, { type: 'SNAPSHOT_REQUEST_SENT', payload: { requestId, forecastOriginId: ORIGIN } })
  s = snapshotAssemblyReducer(s, beginEvent({ requestId, snapshotId }))
  s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame({ requestId, snapshotId }) })
  s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame({ requestId, snapshotId }) })
  s = snapshotAssemblyReducer(s, {
    type: 'WS_FRAME_CELLS_CHUNK',
    payload: chunkFrame({ requestId, snapshotId, chunkIndex: 0, features: [cellFeature('C1', 90.0), cellFeature('C2', null)] }),
  })
  s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ requestId, snapshotId }) })
  return s
}

function requestSent(state = initialSnapshotState, requestId = REQ) {
  return snapshotAssemblyReducer(state, { type: 'SNAPSHOT_REQUEST_SENT', payload: { requestId, forecastOriginId: ORIGIN } })
}

describe('11A-SNAPSHOT-01: all frame snapshot IDs must match', () => {
  it('commits a snapshot when every frame carries the same snapshot_id', () => {
    const final = driveHappyPath(initialSnapshotState)
    expect(final.phase).toBe(PHASE.SNAPSHOT_COMPLETE)
    expect(final.currentCommittedSnapshot.snapshotId).toBe(SNAPSHOT_ID)
    expect(final.currentCommittedSnapshot.cells).toHaveLength(2)
  })
})

describe('11A-SNAPSHOT-02: mixed snapshot IDs rejected', () => {
  it('errors when a summary frame carries a different snapshot_id than snapshot_begin', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent())
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame({ snapshotId: 'DIFFERENT_ID' }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('MIXED_SNAPSHOT_ID')
    expect(s.currentCommittedSnapshot).toBeNull()
  })
})

describe('11A-SNAPSHOT-03: out-of-order/missing/duplicate cell chunks cannot commit', () => {
  it('rejects a duplicate chunk index', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nChunks: 2 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, nChunks: 2, features: [cellFeature('C1', 0)] }) })
    // re-arriving at index 0 again (nextChunkIndex is now 1) is a duplicate, not a sequence skip
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, nChunks: 2, features: [cellFeature('C1-dup', 0)] }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('DUPLICATE_CHUNK_INDEX')
  })

  it('rejects snapshot_end when a chunk is missing', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nCells: 2, nChunks: 2 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, nChunks: 2, features: [cellFeature('ONLY', 0)] }) })
    // chunk_index 1 never arrives
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ nCellsSent: 2, nChunksSent: 2 }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('MISSING_CHUNK')
    expect(s.currentCommittedSnapshot).toBeNull()
  })

  it('rejects an out-of-range chunk index', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nChunks: 1 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 5, nChunks: 1, features: [] }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('INVALID_CHUNK_INDEX')
  })
})

describe('11A-SNAPSHOT-04: snapshot commits only after snapshot_end + integrity true', () => {
  it('never sets SNAPSHOT_COMPLETE before snapshot_end arrives', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent())
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, features: [cellFeature('C1', 0), cellFeature('C2', 0)] }) })
    expect(s.phase).toBe(PHASE.SNAPSHOT_STREAMING)
    expect(s.currentCommittedSnapshot).toBeNull()
  })

  it('rejects commit when scientific_content_hash_verified is false', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent())
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, features: [cellFeature('C1', 0), cellFeature('C2', 0)] }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ verified: false }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('SNAPSHOT_CONTENT_INTEGRITY_MISMATCH')
    expect(s.currentCommittedSnapshot).toBeNull()
  })
})

describe('11A-SNAPSHOT-05: new request cannot accidentally commit stale previous-request frames', () => {
  it('ignores frames from a superseded request_id and does not touch the new buffer', () => {
    // request A begins streaming
    let s = requestSent(initialSnapshotState, 'req-A')
    s = snapshotAssemblyReducer(s, beginEvent({ requestId: 'req-A', snapshotId: 'SNAP_A' }))
    // user clicks Refresh before A finishes -> request B supersedes it
    s = requestSent(s, 'req-B')
    expect(s.incomingSnapshotBuffer).toBeNull()
    // a stale frame from request A arrives late
    const before = s
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame({ requestId: 'req-A', snapshotId: 'SNAP_A' }) })
    expect(s).toBe(before) // reducer returned the identical state object -- proves the stale frame was a true no-op
    expect(s.incomingSnapshotBuffer).toBeNull()

    // request B completes normally and commits correctly
    s = driveHappyPath(s, { requestId: 'req-B', snapshotId: 'SNAP_B' })
    expect(s.phase).toBe(PHASE.SNAPSHOT_COMPLETE)
    expect(s.currentCommittedSnapshot.snapshotId).toBe('SNAP_B')
  })

  it('a bad snapshot never overwrites a previously committed good snapshot', () => {
    let s = driveHappyPath(initialSnapshotState, { requestId: 'req-1', snapshotId: 'GOOD' })
    expect(s.currentCommittedSnapshot.snapshotId).toBe('GOOD')

    s = requestSent(s, 'req-2')
    s = snapshotAssemblyReducer(s, beginEvent({ requestId: 'req-2', snapshotId: 'BAD' }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame({ requestId: 'req-2', snapshotId: 'BAD' }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame({ requestId: 'req-2', snapshotId: 'BAD' }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ requestId: 'req-2', snapshotId: 'BAD', verified: false }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.currentCommittedSnapshot.snapshotId).toBe('GOOD') // untouched
  })
})

// ---------------------------------------------------------------------
// Checkpoint 11A.1
// ---------------------------------------------------------------------

describe('11A1-ORIGIN: snapshot_begin origin binding', () => {
  it('11A1-ORIGIN-01: requested A + begin A -> accepted', () => {
    let s = requestSent(initialSnapshotState, REQ)
    s = snapshotAssemblyReducer(s, beginEvent({ forecastOriginId: ORIGIN }))
    expect(s.phase).toBe(PHASE.SNAPSHOT_STREAMING)
    expect(s.incomingSnapshotBuffer).not.toBeNull()
  })

  it('11A1-ORIGIN-02: requested A + begin B -> ERROR and no buffer', () => {
    let s = requestSent(initialSnapshotState, REQ)
    s = snapshotAssemblyReducer(s, beginEvent({ forecastOriginId: 'ORIGIN:SomewhereElse:2022-05-29' }))
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('FORECAST_ORIGIN_ID_MISMATCH')
    expect(s.incomingSnapshotBuffer).toBeNull()
  })

  it('11A1-ORIGIN-03: wrong-origin begin can never overwrite an already committed good snapshot', () => {
    let s = driveHappyPath(initialSnapshotState, { requestId: 'req-1', snapshotId: 'GOOD' })
    expect(s.currentCommittedSnapshot.snapshotId).toBe('GOOD')

    s = requestSent(s, 'req-2')
    s = snapshotAssemblyReducer(s, beginEvent({ requestId: 'req-2', forecastOriginId: 'ORIGIN:SomewhereElse:2022-05-29' }))
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('FORECAST_ORIGIN_ID_MISMATCH')
    expect(s.currentCommittedSnapshot.snapshotId).toBe('GOOD') // untouched
  })
})

describe('11A1-METADATA: snapshot_begin contract metadata validated independently', () => {
  it('rejects with SNAPSHOT_METADATA_CONTRACT_MISMATCH and creates no buffer when the precomputed contract check fails', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({}, CONTRACT_MISMATCH))
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('SNAPSHOT_METADATA_CONTRACT_MISMATCH')
    expect(s.incomingSnapshotBuffer).toBeNull()
  })

  it('a metadata-contract-mismatched begin never overwrites an already committed good snapshot', () => {
    let s = driveHappyPath(initialSnapshotState, { requestId: 'req-1', snapshotId: 'GOOD' })
    s = requestSent(s, 'req-2')
    s = snapshotAssemblyReducer(s, beginEvent({ requestId: 'req-2' }, CONTRACT_MISMATCH))
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.currentCommittedSnapshot.snapshotId).toBe('GOOD')
  })
})

describe('11A1-CHUNKCOUNT: chunk count is frozen at snapshot_begin, never rewritten', () => {
  it('a cells_chunk whose own n_chunks disagrees with snapshot_begin.n_cell_chunks is rejected, not adopted', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nCells: 2, nChunks: 2 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    // frame claims n_chunks=5, disagreeing with the frozen begin.n_cell_chunks=2
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, nChunks: 5, features: [cellFeature('A', 0)] }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('CHUNK_COUNT_MISMATCH')
  })

  it('rejects a non-integer/negative n_cell_chunks at snapshot_begin itself', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nChunks: -1 }))
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('CHUNK_COUNT_MISMATCH')
    expect(s.incomingSnapshotBuffer).toBeNull()
  })
})

describe('11A1-SEQUENCE: deterministic frame/chunk sequence enforced', () => {
  it('11A1-SEQUENCE-01: correct order commits', () => {
    const s = driveHappyPath(initialSnapshotState)
    expect(s.phase).toBe(PHASE.SNAPSHOT_COMPLETE)
  })

  it('11A1-SEQUENCE-02: sources-before-summary rejected', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent())
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('FRAME_SEQUENCE_VIOLATION')
  })

  it('11A1-SEQUENCE-03: cells-before-sources rejected', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent())
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, features: [cellFeature('C1', 0)] }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('FRAME_SEQUENCE_VIOLATION')
  })

  it('11A1-SEQUENCE-04: duplicate summary rejected', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent())
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('FRAME_SEQUENCE_VIOLATION')
  })

  it('11A1-SEQUENCE-05: duplicate sources rejected', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent())
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('FRAME_SEQUENCE_VIOLATION')
  })

  it('11A1-SEQUENCE-06: chunk 1 before chunk 0 rejected', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nCells: 2, nChunks: 2 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 1, nChunks: 2, features: [cellFeature('SECOND', 0)] }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('FRAME_SEQUENCE_VIOLATION')
  })

  it('11A1-SEQUENCE-07: valid 0..N-1 sequence commits', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nCells: 3, nChunks: 3 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, nChunks: 3, features: [cellFeature('A', 0)] }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 1, nChunks: 3, features: [cellFeature('B', 0)] }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 2, nChunks: 3, features: [cellFeature('C', 0)] }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ nCellsSent: 3, nChunksSent: 3 }) })
    expect(s.phase).toBe(PHASE.SNAPSHOT_COMPLETE)
    expect(s.currentCommittedSnapshot.cells.map((c) => c.properties.scientific_cell_id)).toEqual(['A', 'B', 'C'])
  })

  it('a zero-chunk (zero-cell) snapshot is a real backend contract, not invented: sources -> end directly commits', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nCells: 0, nChunks: 0, nSources: 0 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame({ n: 0 }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ nCellsSent: 0, nChunksSent: 0, nSourcesSent: 0 }) })
    expect(s.phase).toBe(PHASE.SNAPSHOT_COMPLETE)
    expect(s.currentCommittedSnapshot.cells).toEqual([])
  })
})

describe('11A1-END: snapshot_end counts fully verified', () => {
  it('11A1-END-01: wrong n_cell_chunks_sent rejected', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nCells: 2, nChunks: 2 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, nChunks: 2, features: [cellFeature('A', 0)] }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 1, nChunks: 2, features: [cellFeature('B', 0)] }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ nCellsSent: 2, nChunksSent: 1 }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('CHUNK_COUNT_MISMATCH')
  })

  it('11A1-END-02: wrong n_cells_sent rejected', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nCells: 2, nChunks: 1 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, nChunks: 1, features: [cellFeature('A', 0), cellFeature('B', 0)] }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ nCellsSent: 99, nChunksSent: 1 }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('CELL_COUNT_MISMATCH')
  })

  it('11A1-END-03: wrong n_sources_sent rejected', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nCells: 1, nChunks: 1 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame({ n: 1 }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, nChunks: 1, features: [cellFeature('A', 0)] }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ nCellsSent: 1, nChunksSent: 1, nSourcesSent: 99 }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('SOURCE_COUNT_MISMATCH')
  })

  it('11A1-END-04: integrity false rejected', () => {
    let s = requestSent()
    s = snapshotAssemblyReducer(s, beginEvent({ nCells: 1, nChunks: 1 }))
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SUMMARY', payload: summaryFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SOURCES', payload: sourcesFrame() })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_CELLS_CHUNK', payload: chunkFrame({ chunkIndex: 0, nChunks: 1, features: [cellFeature('A', 0)] }) })
    s = snapshotAssemblyReducer(s, { type: 'WS_FRAME_SNAPSHOT_END', payload: endFrame({ nCellsSent: 1, nChunksSent: 1, verified: false }) })
    expect(s.phase).toBe(PHASE.ERROR)
    expect(s.error.status).toBe('SNAPSHOT_CONTENT_INTEGRITY_MISMATCH')
  })

  it('11A1-END-05: all exact -> atomic commit', () => {
    const s = driveHappyPath(initialSnapshotState)
    expect(s.phase).toBe(PHASE.SNAPSHOT_COMPLETE)
    expect(s.currentCommittedSnapshot.snapshotId).toBe(SNAPSHOT_ID)
  })
})

describe('11A1-TRANSPORT: transport-not-ready send is never silent', () => {
  it('TRANSPORT_SEND_REJECTED sets a non-fatal transportNotice without changing phase or clearing the committed snapshot', () => {
    const committed = driveHappyPath(initialSnapshotState)
    const s = snapshotAssemblyReducer(committed, { type: 'TRANSPORT_SEND_REJECTED' })
    expect(s.transportNotice.status).toBe('TRANSPORT_NOT_READY')
    expect(s.phase).toBe(PHASE.SNAPSHOT_COMPLETE)
    expect(s.currentCommittedSnapshot).toBe(committed.currentCommittedSnapshot)
  })

  it('a real SNAPSHOT_REQUEST_SENT clears a previous transportNotice', () => {
    let s = snapshotAssemblyReducer(initialSnapshotState, { type: 'TRANSPORT_SEND_REJECTED' })
    expect(s.transportNotice).not.toBeNull()
    s = requestSent(s)
    expect(s.transportNotice).toBeNull()
  })

  it('isTransportUsable is true only while a request could actually be accepted', () => {
    expect(isTransportUsable(PHASE.IDLE)).toBe(false)
    expect(isTransportUsable(PHASE.CONNECTING)).toBe(false)
    expect(isTransportUsable(PHASE.ERROR)).toBe(false)
    expect(isTransportUsable(PHASE.INCOMPATIBLE_BACKEND_PROTOCOL)).toBe(false)
    expect(isTransportUsable(PHASE.TRANSPORT_READY)).toBe(true)
    expect(isTransportUsable(PHASE.SNAPSHOT_COMPLETE)).toBe(true)
  })
})
