/**
 * Pure reconciliation of the SSE `geospatial_data_changed` / `ready.data_version`
 * signals (GEOSPATIAL_FRONTEND_API_CONTRACT.md §6) into one debounced
 * `token` that data hooks use as a refetch trigger.
 *
 * - A data-change event, or a `ready` whose `data_version` differs from the
 *   last version seen (a reconnect after missed changes), schedules a refetch.
 * - Bursts are coalesced: the refetch fires DEBOUNCE_MS after the last
 *   signal, but never later than MAX_WAIT_MS after the first one.
 * - The first `ready` of a session only records the version (data was just
 *   fetched on mount), and a session change resets everything.
 *
 * The backend detects changes by polling every ~15 s, so updates are "near
 * real time", never instant.
 */

export const DATA_CHANGE_DEBOUNCE_MS = 1200
export const DATA_CHANGE_MAX_WAIT_MS = 5000

export const DATA_CHANGE_KINDS = ['CREATED', 'VERIFIED', 'UNVERIFIED', 'RECLASSIFIED', 'CORRECTED', 'DELETED']

export const initialDataChangeState = Object.freeze({
  dataVersion: null,
  dueAt: null,
  firstPendingAt: null,
  token: 0,
  pendingChanges: [],
  lastApplied: null,
})

function schedule(state, nowMs, change) {
  const firstPendingAt = state.firstPendingAt ?? nowMs
  const dueAt = Math.min(nowMs + DATA_CHANGE_DEBOUNCE_MS, firstPendingAt + DATA_CHANGE_MAX_WAIT_MS)
  return { ...state, dueAt, firstPendingAt, pendingChanges: [...state.pendingChanges, change].slice(-20) }
}

export function readyReceived(state, dataVersion, nowMs) {
  if (!dataVersion) return state
  if (state.dataVersion == null) return { ...state, dataVersion }
  if (state.dataVersion === dataVersion) return state
  return schedule({ ...state, dataVersion }, nowMs, { change: 'RECONNECT_VERSION_CHANGED', disease: null, record_key: null })
}

export function dataChangedReceived(state, event, nowMs) {
  if (!event || !DATA_CHANGE_KINDS.includes(event.change)) return state
  const next = event.data_version ? { ...state, dataVersion: event.data_version } : state
  return schedule(next, nowMs, {
    change: event.change,
    disease: event.disease ?? null,
    previous_disease: event.previous_disease ?? null,
    record_key: event.record_key ?? null,
  })
}

/** Returns the same object when nothing is due (cheap to call every frame). */
export function flushIfDue(state, nowMs) {
  if (state.dueAt == null || nowMs < state.dueAt) return state
  return {
    ...state,
    dueAt: null,
    firstPendingAt: null,
    token: state.token + 1,
    pendingChanges: [],
    lastApplied: { at: Date.now(), changes: state.pendingChanges },
  }
}

export function sessionChanged() {
  return { ...initialDataChangeState }
}
