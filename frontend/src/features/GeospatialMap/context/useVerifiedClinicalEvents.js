/**
 * GEO-LIVE-05 Section 9: thin hook wiring `operationalEventsReducer.js`
 * (pure decision logic, fully unit-tested) to the real
 * `openOperationalEventStream` fetch/SSE call and a `requestAnimationFrame`
 * -driven reconnect tick -- mirrors `useOperationalContext.js`'s exact
 * shape (mount-once RAF loop, `AbortController`-aware, no
 * `setInterval`/`setTimeout` anywhere: this feature's structural test
 * `noAutoPolling.test.js` forbids both tokens repo-wide).
 *
 * Contains no state-transition decision of its own -- every decision is
 * delegated to the pure reducer.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { dataChangedReceived, flushIfDue, initialDataChangeState, readyReceived, sessionChanged } from './dataChangeReconciler'

import { hasTokenDisappeared, readAuthToken } from '../api/operationalApi'
import { OPERATIONAL_EVENTS_FETCH_STATUS, openOperationalEventStream } from '../api/operationalEventsApi'
import {
  connectionLost,
  connectionReady,
  dismissNotification,
  eventReceived,
  heartbeatReceived,
  initialEventStreamState,
  isStaleNow,
  markNotificationRead,
  nextReconnectDelayMs,
  shouldAttemptReconnect,
  streamDisconnectedByCaller,
} from './operationalEventsReducer'

export {
  EVENT_STREAM_STATE,
  TRANSPORT_MODE,
  deriveDisplayState,
  isLiveWordingHonest,
} from './operationalEventsReducer'

const STALE_THRESHOLD_MS = 45000
/** Section 9: a connected stream with no event/heartbeat for this long is
 * shown as stale/fallback rather than silently trusted as still live --
 * comfortably above the backend's 15s heartbeat cadence
 * (`_HEARTBEAT_INTERVAL_SECONDS` in `operational_events_router_factory.py`)
 * so one missed heartbeat tick alone never flips this. */

export function useVerifiedClinicalEvents() {
  const [state, setState] = useState(initialEventStreamState)

  const abortControllerRef = useRef(null)
  const mountedRef = useRef(true)
  const rafRef = useRef(null)
  const reconnectAtRef = useRef(null)
  const connectingRef = useRef(false)
  const lastKnownTokenRef = useRef(null)
  // Realtime data invalidation (contract §6). The reconciler state lives in
  // a ref (updated per SSE frame / RAF tick); only the debounced refetch
  // token and its summary are React state, so idle frames never re-render.
  const dataChangeRef = useRef(initialDataChangeState)
  const [dataChange, setDataChange] = useState({ token: 0, dataVersion: null, lastApplied: null })

  const connect = useCallback(() => {
    if (connectingRef.current) return
    connectingRef.current = true
    lastKnownTokenRef.current = readAuthToken()
    const controller = new AbortController()
    abortControllerRef.current = controller

    openOperationalEventStream({
      signal: controller.signal,
      onReady: ({ transport, data_version: dataVersion } = {}) => {
        if (!mountedRef.current) return
        dataChangeRef.current = readyReceived(dataChangeRef.current, dataVersion, performance.now())
        setState((prev) => connectionReady(prev, { transportMode: transport }, Date.now()))
      },
      onHeartbeat: () => {
        if (!mountedRef.current) return
        setState((prev) => heartbeatReceived(prev, Date.now()))
      },
      onEvent: (event) => {
        if (!mountedRef.current) return
        setState((prev) => eventReceived(prev, event, Date.now()))
      },
      onDataChanged: (event) => {
        if (!mountedRef.current) return
        dataChangeRef.current = dataChangedReceived(dataChangeRef.current, event, performance.now())
        setState((prev) => heartbeatReceived(prev, Date.now()))
      },
    })
      .then(() => {
        // Section 8 "tolerate reconnect": a clean stream end (server
        // closed it) is treated the same as a transient failure -- the
        // vet's browser keeps trying, it never silently stops watching.
        // Only the CURRENT connection may release the guard: a stale,
        // aborted stream settling late must not clobber a newer one.
        if (abortControllerRef.current === controller) connectingRef.current = false
        if (!mountedRef.current || controller.signal.aborted) return
        setState((prev) => {
          const next = connectionLost(prev, null)
          if (shouldAttemptReconnect(next.state)) {
            reconnectAtRef.current = performance.now() + nextReconnectDelayMs(prev.reconnectAttempt)
          }
          return next
        })
      })
      .catch((err) => {
        if (abortControllerRef.current === controller) connectingRef.current = false
        if (!mountedRef.current || err?.name === 'AbortError') return
        const reason = err?.operationalEventsStatus ?? OPERATIONAL_EVENTS_FETCH_STATUS.NETWORK_ERROR
        setState((prev) => {
          const next = connectionLost(prev, reason)
          if (shouldAttemptReconnect(next.state)) {
            reconnectAtRef.current = performance.now() + nextReconnectDelayMs(prev.reconnectAttempt)
          }
          return next
        })
      })
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()

    const tick = () => {
      // Section 7 "logout/token disappearance": checked before the
      // reconnect-timer branch so a logout mid-backoff-wait is caught
      // immediately too, not only while a connection is actively open.
      if (hasTokenDisappeared(lastKnownTokenRef.current, readAuthToken())) {
        lastKnownTokenRef.current = null
        reconnectAtRef.current = null
        abortControllerRef.current?.abort()
        setState((prev) => connectionLost(prev, 'SESSION_REQUIRED'))
      } else {
        const now = performance.now()
        const currentToken = readAuthToken()
        if (lastKnownTokenRef.current && currentToken && currentToken !== lastKnownTokenRef.current) {
          // A different session (another account signed in, e.g. in another
          // tab): drop the version history and reconnect as the new identity.
          dataChangeRef.current = sessionChanged()
          setDataChange({ token: 0, dataVersion: null, lastApplied: null })
          abortControllerRef.current?.abort()
          connectingRef.current = false
          reconnectAtRef.current = null
          connect()
        }
        const flushed = flushIfDue(dataChangeRef.current, now)
        if (flushed !== dataChangeRef.current) {
          dataChangeRef.current = flushed
          setDataChange({ token: flushed.token, dataVersion: flushed.dataVersion, lastApplied: flushed.lastApplied })
        }
        if (reconnectAtRef.current != null && now >= reconnectAtRef.current && !connectingRef.current) {
          reconnectAtRef.current = null
          connect()
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)

    return () => {
      mountedRef.current = false
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      abortControllerRef.current?.abort()
      // Release the guard: React StrictMode (dev) unmounts and remounts this
      // effect, and the remount's connect() must not be skipped as "already
      // connecting" -- that left the stream never connected (stuck chip).
      connectingRef.current = false
      abortControllerRef.current = null
    }
    // Intentionally mount-once, mirroring useOperationalContext.js.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const dismiss = useCallback((eventId) => {
    setState((prev) => dismissNotification(prev, eventId))
  }, [])

  const markRead = useCallback((eventId) => {
    setState((prev) => markNotificationRead(prev, eventId))
  }, [])

  const disconnect = useCallback(() => {
    abortControllerRef.current?.abort()
    setState((prev) => streamDisconnectedByCaller(prev))
  }, [])

  const isStale = isStaleNow(state.lastActivityAt, Date.now(), STALE_THRESHOLD_MS)
  const lastEvent = state.notifications[0]?.event ?? null

  return {
    ...state,
    isStale,
    lastEvent,
    dismiss,
    markRead,
    disconnect,
    dataChangeToken: dataChange.token,
    dataVersion: dataChange.dataVersion ?? dataChangeRef.current.dataVersion,
    lastDataChange: dataChange.lastApplied,
  }
}
