/**
 * Checkpoint 11A: React hook wiring the pure `snapshotAssemblyReducer`
 * to a real `fetch`/`WebSocket`. No automatic scientific polling
 * anywhere in this file (Part 11) -- no `setInterval`, no timer-driven
 * refresh, no background origin polling. The only ways a new snapshot
 * is ever requested are: (1) the caller explicitly invokes
 * `requestSnapshot`/`refreshSnapshot`, both user-triggered.
 */
import { useCallback, useEffect, useReducer, useRef } from 'react'

import { fetchProtocol } from '../api/geospatialApi'
import {
  evaluateProtocolCompatibility,
  evaluateSnapshotBeginContract,
  evaluateWsParentContract,
  protocolCheckFailureOutcome,
} from '../api/geospatialContract'
import { geospatialWebSocketUrl } from '../api/apiConfig'
import { PHASE, initialSnapshotState, snapshotAssemblyReducer } from './snapshotAssembly'

let requestIdCounter = 0
function nextRequestId() {
  requestIdCounter += 1
  return `req-${Date.now()}-${requestIdCounter}`
}

export function useGeospatialSnapshot() {
  const [state, dispatch] = useReducer(snapshotAssemblyReducer, initialSnapshotState)
  const socketRef = useRef(null)
  const protocolRef = useRef(null)

  // Checkpoint 11A.1 Part 8: this resolves a STRUCTURED outcome on every
  // path -- including a backend-unreachable failure -- instead of
  // dispatching and then rethrowing. Rethrowing after already updating
  // state via dispatch left the caller's `.then()` (no `.catch()`)
  // exposed to an unhandled promise rejection in the browser for the
  // exact case (backend down) this checkpoint is meant to guard
  // against. `protocolCheckFailureOutcome` is a pure, independently
  // testable helper shaped identically to `evaluateProtocolCompatibility`'s
  // return value, so callers never need a separate error-shape branch.
  const runProtocolPreflight = useCallback(async () => {
    dispatch({ type: 'PROTOCOL_CHECK_START' })
    try {
      const protocolResponse = await fetchProtocol()
      const compatibility = evaluateProtocolCompatibility(protocolResponse)
      protocolRef.current = protocolResponse
      dispatch({ type: 'PROTOCOL_CHECK_SUCCESS', payload: { compatibility, protocolResponse } })
      return compatibility
    } catch (err) {
      const outcome = protocolCheckFailureOutcome(err.message)
      dispatch({ type: 'PROTOCOL_CHECK_FAILURE', payload: { message: outcome.reasons[0] } })
      return outcome
    }
  }, [])

  const connect = useCallback(() => {
    if (socketRef.current) return
    dispatch({ type: 'WS_CONNECTING' })
    const socket = new WebSocket(geospatialWebSocketUrl())
    socketRef.current = socket

    socket.onmessage = (event) => {
      let frame
      try {
        frame = JSON.parse(event.data)
      } catch {
        return // malformed frame from a misbehaving proxy/server -- never crash the UI
      }
      switch (frame.type) {
        case 'transport_ready': {
          const wsParentCompatibility = evaluateWsParentContract(frame, protocolRef.current)
          dispatch({ type: 'WS_FRAME_TRANSPORT_READY', payload: { frame, wsParentCompatibility } })
          break
        }
        case 'snapshot_begin': {
          const contractCompatibility = evaluateSnapshotBeginContract(frame, protocolRef.current)
          dispatch({ type: 'WS_FRAME_SNAPSHOT_BEGIN', payload: { frame, contractCompatibility } })
          break
        }
        case 'summary':
          dispatch({ type: 'WS_FRAME_SUMMARY', payload: frame })
          break
        case 'sources':
          dispatch({ type: 'WS_FRAME_SOURCES', payload: frame })
          break
        case 'cells_chunk':
          dispatch({ type: 'WS_FRAME_CELLS_CHUNK', payload: frame })
          break
        case 'snapshot_end':
          dispatch({ type: 'WS_FRAME_SNAPSHOT_END', payload: frame })
          break
        case 'error':
          dispatch({ type: 'WS_FRAME_ERROR', payload: frame })
          break
        case 'pong':
          dispatch({ type: 'WS_FRAME_PONG', payload: frame })
          break
        default:
          break // unrecognized frame type -- ignore rather than crash
      }
    }

    socket.onclose = () => {
      socketRef.current = null
      dispatch({ type: 'WS_DISCONNECTED' })
    }
    socket.onerror = () => {
      // onclose fires after onerror for browser WebSockets; no separate dispatch needed
    }
  }, [])

  // Checkpoint 11A.1 Part 7: a request attempted while the socket is
  // not open must never look, from the UI's perspective, like a load
  // that silently did nothing -- it dispatches an explicit
  // TRANSPORT_NOT_READY notice instead of just returning null.
  const sendSnapshotMessage = useCallback((type, forecastOriginId) => {
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      dispatch({ type: 'TRANSPORT_SEND_REJECTED' })
      return null
    }
    const requestId = nextRequestId()
    socket.send(JSON.stringify({ type, request_id: requestId, forecast_origin_id: forecastOriginId }))
    dispatch({ type: 'SNAPSHOT_REQUEST_SENT', payload: { requestId, forecastOriginId } })
    return requestId
  }, [])

  const requestSnapshot = useCallback(
    (forecastOriginId) => sendSnapshotMessage('snapshot_request', forecastOriginId),
    [sendSnapshotMessage],
  )

  const refreshSnapshot = useCallback(
    (forecastOriginId) => sendSnapshotMessage('snapshot_refresh', forecastOriginId),
    [sendSnapshotMessage],
  )

  const ping = useCallback(() => {
    const socket = socketRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) return
    socket.send(JSON.stringify({ type: 'ping', request_id: nextRequestId() }))
  }, [])

  useEffect(() => {
    return () => {
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [])

  return { state, PHASE, runProtocolPreflight, connect, requestSnapshot, refreshSnapshot, ping }
}
