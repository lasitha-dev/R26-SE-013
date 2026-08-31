/**
 * Checkpoint 11A Part 8-10: framework-independent WebSocket snapshot
 * state machine.
 *
 * Pure reducer -- no React, no DOM, no network. Every scientific value
 * that ends up in `currentCommittedSnapshot` is copied verbatim from
 * backend frames; nothing here computes C0/direction/rate/reach.
 *
 * `incomingSnapshotBuffer` accumulates ONE in-flight response;
 * `currentCommittedSnapshot` is only ever atomically REPLACED, in one
 * reducer step, after `snapshot_end` passes every validation below --
 * never partially updated, so the UI can never mix a summary from one
 * snapshot with cells from another (Part 8).
 *
 * Every WS frame carries the `request_id` the frontend generated for
 * its own `snapshot_request`/`snapshot_refresh` message. A frame whose
 * `request_id` does not match `state.currentRequestId` is a STALE frame
 * from a superseded request (e.g. the user clicked Refresh again before
 * the first response finished) and is silently ignored -- it can never
 * mutate `incomingSnapshotBuffer` or `currentCommittedSnapshot`
 * (Part 9, 11A-SNAPSHOT-05).
 */

export const PHASE = Object.freeze({
  IDLE: 'IDLE',
  PROTOCOL_CHECKING: 'PROTOCOL_CHECKING',
  PROTOCOL_READY: 'PROTOCOL_READY',
  CONNECTING: 'CONNECTING',
  TRANSPORT_READY: 'TRANSPORT_READY',
  SNAPSHOT_REQUESTED: 'SNAPSHOT_REQUESTED',
  SNAPSHOT_STREAMING: 'SNAPSHOT_STREAMING',
  SNAPSHOT_COMPLETE: 'SNAPSHOT_COMPLETE',
  ERROR: 'ERROR',
  INCOMPATIBLE_BACKEND_PROTOCOL: 'INCOMPATIBLE_BACKEND_PROTOCOL',
})

export const initialSnapshotState = Object.freeze({
  phase: PHASE.IDLE,
  protocol: null,
  currentRequestId: null,
  currentOriginId: null,
  incomingSnapshotBuffer: null,
  currentCommittedSnapshot: null,
  error: null,
  // Checkpoint 11A.1 Part 7: a non-fatal, non-phase-changing notice for
  // a request the UI attempted while the transport could not accept it
  // -- distinct from `error`, which reflects a backend/transport
  // failure. Cleared as soon as a request is actually sent.
  transportNotice: null,
})

// Checkpoint 11A.1 Part 5: `incomingSnapshotBuffer.stage` tracks where
// in the deterministic frame sequence
// (begin -> summary -> sources -> chunks[0..N-1] -> end) the in-flight
// response currently is. Every frame handler below requires the buffer
// to be in the exact stage that frame is allowed to arrive in --
// anything else is a FRAME_SEQUENCE_VIOLATION, never silently accepted
// or reordered.
const STAGE = Object.freeze({
  AWAITING_SUMMARY: 'AWAITING_SUMMARY',
  AWAITING_SOURCES: 'AWAITING_SOURCES',
  AWAITING_CHUNKS_OR_END: 'AWAITING_CHUNKS_OR_END',
})

/** True while the transport can accept an explicit user-triggered
 * snapshot request (Part 7) -- used both by the hook (real send guard)
 * and by the UI (button enablement), so the two never disagree. */
export function isTransportUsable(phase) {
  return (
    phase === PHASE.TRANSPORT_READY ||
    phase === PHASE.SNAPSHOT_REQUESTED ||
    phase === PHASE.SNAPSHOT_STREAMING ||
    phase === PHASE.SNAPSHOT_COMPLETE
  )
}

/** `n_cell_chunks` frozen at `snapshot_begin` (Part 4) -- must be a
 * non-negative integer; a zero-chunk (zero-cell) snapshot is a real,
 * backend-guaranteed possibility (`chunking_10b.py`: zero cells produce
 * zero chunks), never an invented frontend behavior. */
function isValidChunkCount(value) {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function freshBuffer(beginFrame) {
  return {
    requestId: beginFrame.request_id,
    snapshotId: beginFrame.snapshot_id,
    forecastOriginId: beginFrame.forecast_origin_id,
    meta: beginFrame,
    summary: null,
    sources: null,
    nChunksExpected: beginFrame.n_cell_chunks,
    nextChunkIndex: 0,
    chunksByIndex: new Map(),
    stage: STAGE.AWAITING_SUMMARY,
  }
}

function errorState(state, status, message) {
  return { ...state, phase: PHASE.ERROR, error: { status, message }, incomingSnapshotBuffer: null }
}

/** True if `frame.request_id` matches the currently in-flight request. */
function isCurrentRequest(state, frame) {
  return state.currentRequestId !== null && frame && frame.request_id === state.currentRequestId
}

/** True if `frame.snapshot_id` matches the buffer being assembled. */
function matchesBufferSnapshot(buffer, frame) {
  return buffer !== null && frame && frame.snapshot_id === buffer.snapshotId
}

export function snapshotAssemblyReducer(state, event) {
  switch (event.type) {
    case 'PROTOCOL_CHECK_START':
      return { ...state, phase: PHASE.PROTOCOL_CHECKING, error: null }

    case 'PROTOCOL_CHECK_SUCCESS': {
      const { compatibility, protocolResponse } = event.payload
      if (compatibility.status !== 'PROTOCOL_COMPATIBLE') {
        return {
          ...state,
          phase: PHASE.INCOMPATIBLE_BACKEND_PROTOCOL,
          protocol: protocolResponse,
          error: { status: 'INCOMPATIBLE_BACKEND_PROTOCOL', message: 'Geospatial frontend/backend contract mismatch.' },
        }
      }
      return { ...state, phase: PHASE.PROTOCOL_READY, protocol: protocolResponse, error: null }
    }

    case 'PROTOCOL_CHECK_FAILURE':
      return errorState(state, 'PROTOCOL_CHECK_FAILED', event.payload?.message || 'Could not reach the geospatial backend.')

    case 'WS_CONNECTING':
      return { ...state, phase: PHASE.CONNECTING }

    case 'WS_FRAME_TRANSPORT_READY': {
      const compatibility = event.payload.wsParentCompatibility
      if (compatibility.status !== 'PROTOCOL_COMPATIBLE') {
        return {
          ...state,
          phase: PHASE.INCOMPATIBLE_BACKEND_PROTOCOL,
          error: { status: 'INCOMPATIBLE_BACKEND_PROTOCOL', message: 'Geospatial frontend/backend contract mismatch.' },
        }
      }
      return { ...state, phase: PHASE.TRANSPORT_READY, error: null }
    }

    case 'WS_DISCONNECTED':
      // Never fabricate a "fresher" scientific result on reconnect --
      // the last committed snapshot (if any) is preserved untouched.
      if (state.phase === PHASE.ERROR || state.phase === PHASE.INCOMPATIBLE_BACKEND_PROTOCOL) {
        return state
      }
      return { ...state, phase: PHASE.CONNECTING, incomingSnapshotBuffer: null }

    case 'SNAPSHOT_REQUEST_SENT':
      return {
        ...state,
        phase: PHASE.SNAPSHOT_REQUESTED,
        currentRequestId: event.payload.requestId,
        currentOriginId: event.payload.forecastOriginId,
        incomingSnapshotBuffer: null,
        error: null,
        transportNotice: null,
      }

    // Checkpoint 11A.1 Part 7: a request the transport could not accept
    // (socket not open) is never a silent no-op -- it surfaces a
    // non-fatal, non-phase-changing notice instead.
    case 'TRANSPORT_SEND_REJECTED':
      return {
        ...state,
        transportNotice: { status: 'TRANSPORT_NOT_READY', message: 'A snapshot request was attempted while the transport was not ready.' },
      }

    case 'WS_FRAME_SNAPSHOT_BEGIN': {
      const { frame, contractCompatibility } = event.payload
      if (!isCurrentRequest(state, frame)) return state // stale frame from a superseded request

      // Part 2: snapshot_begin must describe the SAME origin the
      // frontend actually requested -- never trust the backend to have
      // routed the request correctly without checking.
      if (frame.forecast_origin_id !== state.currentOriginId) {
        return errorState(
          state, 'FORECAST_ORIGIN_ID_MISMATCH',
          `snapshot_begin.forecast_origin_id=${frame.forecast_origin_id} != requested origin=${state.currentOriginId}.`,
        )
      }

      // Part 3: snapshot_begin carries its own copy of the scientific/
      // transport identity fields -- validated independently of the
      // earlier transport_ready check, never assumed still true.
      if (contractCompatibility && contractCompatibility.status !== 'PROTOCOL_COMPATIBLE') {
        return errorState(state, contractCompatibility.status, contractCompatibility.reasons.join('; '))
      }

      // Part 4: the chunk count is frozen HERE and never rewritten by a
      // later cells_chunk frame.
      if (!isValidChunkCount(frame.n_cell_chunks)) {
        return errorState(state, 'CHUNK_COUNT_MISMATCH', `snapshot_begin.n_cell_chunks=${frame.n_cell_chunks} is not a valid non-negative integer.`)
      }

      return { ...state, phase: PHASE.SNAPSHOT_STREAMING, incomingSnapshotBuffer: freshBuffer(frame) }
    }

    case 'WS_FRAME_SUMMARY': {
      const frame = event.payload
      if (!isCurrentRequest(state, frame)) return state
      const buffer = state.incomingSnapshotBuffer
      if (!matchesBufferSnapshot(buffer, frame)) {
        return errorState(state, 'MIXED_SNAPSHOT_ID', 'Received a summary frame for a different snapshot_id than snapshot_begin.')
      }
      if (buffer.stage !== STAGE.AWAITING_SUMMARY) {
        return errorState(state, 'FRAME_SEQUENCE_VIOLATION', `summary frame arrived while buffer stage was ${buffer.stage} (duplicate or out-of-order summary).`)
      }
      return { ...state, incomingSnapshotBuffer: { ...buffer, summary: frame.data, stage: STAGE.AWAITING_SOURCES } }
    }

    case 'WS_FRAME_SOURCES': {
      const frame = event.payload
      if (!isCurrentRequest(state, frame)) return state
      const buffer = state.incomingSnapshotBuffer
      if (!matchesBufferSnapshot(buffer, frame)) {
        return errorState(state, 'MIXED_SNAPSHOT_ID', 'Received a sources frame for a different snapshot_id than snapshot_begin.')
      }
      if (buffer.stage !== STAGE.AWAITING_SOURCES) {
        return errorState(state, 'FRAME_SEQUENCE_VIOLATION', `sources frame arrived while buffer stage was ${buffer.stage} (before summary, or duplicate sources).`)
      }
      return { ...state, incomingSnapshotBuffer: { ...buffer, sources: frame.data, stage: STAGE.AWAITING_CHUNKS_OR_END } }
    }

    case 'WS_FRAME_CELLS_CHUNK': {
      const frame = event.payload
      if (!isCurrentRequest(state, frame)) return state
      const buffer = state.incomingSnapshotBuffer
      if (!matchesBufferSnapshot(buffer, frame)) {
        return errorState(state, 'MIXED_SNAPSHOT_ID', 'Received a cells_chunk frame for a different snapshot_id than snapshot_begin.')
      }
      if (buffer.stage !== STAGE.AWAITING_CHUNKS_OR_END) {
        return errorState(state, 'FRAME_SEQUENCE_VIOLATION', `cells_chunk arrived while buffer stage was ${buffer.stage} (before summary/sources).`)
      }
      const { chunk_index: chunkIndex, n_chunks: nChunks, features } = frame
      // Part 4: the frame's own n_chunks must still agree with the
      // count frozen at snapshot_begin -- never re-adopted from here.
      if (nChunks !== buffer.nChunksExpected) {
        return errorState(state, 'CHUNK_COUNT_MISMATCH', `cells_chunk.n_chunks=${nChunks} != snapshot_begin.n_cell_chunks=${buffer.nChunksExpected}.`)
      }
      if (chunkIndex < 0 || chunkIndex >= buffer.nChunksExpected) {
        return errorState(state, 'INVALID_CHUNK_INDEX', `cells_chunk index ${chunkIndex} out of range [0, ${buffer.nChunksExpected}).`)
      }
      if (chunkIndex < buffer.nextChunkIndex) {
        return errorState(state, 'DUPLICATE_CHUNK_INDEX', `cells_chunk index ${chunkIndex} received more than once.`)
      }
      // Part 5: chunks must arrive in strict ascending order -- a chunk
      // that skips ahead of the next expected index is a protocol-order
      // violation, never silently buffered/reordered.
      if (chunkIndex !== buffer.nextChunkIndex) {
        return errorState(state, 'FRAME_SEQUENCE_VIOLATION', `cells_chunk index ${chunkIndex} arrived before expected index ${buffer.nextChunkIndex}.`)
      }
      const chunksByIndex = new Map(buffer.chunksByIndex)
      chunksByIndex.set(chunkIndex, features)
      return { ...state, incomingSnapshotBuffer: { ...buffer, chunksByIndex, nextChunkIndex: buffer.nextChunkIndex + 1 } }
    }

    case 'WS_FRAME_SNAPSHOT_END': {
      const frame = event.payload
      if (!isCurrentRequest(state, frame)) return state
      const buffer = state.incomingSnapshotBuffer
      if (!matchesBufferSnapshot(buffer, frame)) {
        return errorState(state, 'MIXED_SNAPSHOT_ID', 'Received snapshot_end for a different snapshot_id than snapshot_begin.')
      }
      if (buffer.stage !== STAGE.AWAITING_CHUNKS_OR_END) {
        return errorState(state, 'FRAME_SEQUENCE_VIOLATION', `snapshot_end arrived while buffer stage was ${buffer.stage} (before summary/sources).`)
      }
      if (frame.scientific_content_hash_verified !== true) {
        return errorState(state, 'SNAPSHOT_CONTENT_INTEGRITY_MISMATCH', 'Backend did not confirm scientific_content_hash_verified.')
      }

      const nChunks = buffer.nChunksExpected
      if (buffer.nextChunkIndex !== nChunks) {
        return errorState(state, 'MISSING_CHUNK', `expected ${nChunks} chunks, only received indices 0..${buffer.nextChunkIndex - 1}.`)
      }
      if (buffer.chunksByIndex.size !== nChunks) {
        return errorState(state, 'UNEXPECTED_CHUNK_COUNT', `expected ${nChunks} chunks, tracked ${buffer.chunksByIndex.size}.`)
      }
      // Part 6: snapshot_end.n_cell_chunks_sent must agree with both
      // the frozen expected count and the actual number received.
      if (frame.n_cell_chunks_sent !== nChunks) {
        return errorState(state, 'CHUNK_COUNT_MISMATCH', `snapshot_end.n_cell_chunks_sent=${frame.n_cell_chunks_sent} != snapshot_begin.n_cell_chunks=${nChunks}.`)
      }

      const cells = []
      for (let i = 0; i < nChunks; i += 1) {
        cells.push(...buffer.chunksByIndex.get(i))
      }

      if (cells.length !== frame.n_cells_sent) {
        return errorState(state, 'CELL_COUNT_MISMATCH', `assembled ${cells.length} cells but snapshot_end reports n_cells_sent=${frame.n_cells_sent}.`)
      }
      if (buffer.meta.n_cells !== frame.n_cells_sent) {
        return errorState(state, 'CELL_COUNT_MISMATCH', `snapshot_begin.n_cells=${buffer.meta.n_cells} != snapshot_end.n_cells_sent=${frame.n_cells_sent}.`)
      }
      const nSources = buffer.sources?.features?.length ?? null
      if (nSources !== frame.n_sources_sent) {
        return errorState(state, 'SOURCE_COUNT_MISMATCH', `assembled ${nSources} sources but snapshot_end reports n_sources_sent=${frame.n_sources_sent}.`)
      }
      if (buffer.meta.n_sources !== frame.n_sources_sent) {
        return errorState(state, 'SOURCE_COUNT_MISMATCH', `snapshot_begin.n_sources=${buffer.meta.n_sources} != snapshot_end.n_sources_sent=${frame.n_sources_sent}.`)
      }
      if (!buffer.summary || !buffer.sources) {
        return errorState(state, 'INCOMPLETE_SNAPSHOT', 'snapshot_end arrived before summary/sources were received.')
      }

      // Atomic commit -- one reducer step replaces the whole committed
      // snapshot; nothing partial is ever exposed as SNAPSHOT_COMPLETE.
      const committedSnapshot = {
        snapshotId: buffer.snapshotId,
        forecastOriginId: buffer.forecastOriginId,
        meta: buffer.meta,
        summary: buffer.summary,
        sources: buffer.sources,
        cells,
      }
      return {
        ...state,
        phase: PHASE.SNAPSHOT_COMPLETE,
        currentCommittedSnapshot: committedSnapshot,
        incomingSnapshotBuffer: null,
        error: null,
      }
    }

    case 'WS_FRAME_ERROR': {
      const frame = event.payload
      if (!isCurrentRequest(state, frame) && frame.request_id !== null) return state
      return errorState(state, frame.status, frame.message)
    }

    case 'WS_FRAME_PONG':
      return state // transport health only, no phase change

    case 'RESET':
      return initialSnapshotState

    default:
      return state
  }
}
