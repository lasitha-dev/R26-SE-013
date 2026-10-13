import React from 'react'

import { OPERATIONAL_STATE } from '../context/operationalRefreshReducer'
import {
  ACTION_REFRESH_OPERATIONAL_CONTEXT,
  LABEL_OPERATIONAL_STATUS_CONNECTED,
  LABEL_OPERATIONAL_STATUS_FORBIDDEN,
  LABEL_OPERATIONAL_STATUS_HOST_COMPOSITION_REQUIRED,
  LABEL_OPERATIONAL_STATUS_LOADING,
  LABEL_OPERATIONAL_STATUS_SESSION_REQUIRED,
  LABEL_OPERATIONAL_STATUS_STALE,
  LABEL_OPERATIONAL_STATUS_UNAVAILABLE,
} from '../semanticLabels'

/**
 * GEO-INT-03 Section 20: a small, honest operational-context status
 * presentation docked near the existing header controls -- mirrors
 * `SnapshotStatusChip.jsx`'s exact visual language (dot + mono label +
 * inline action), never renders "LIVE" (Section 14: the transport is
 * plain HTTP request/response, not push).
 */
const DOT_CLASS = {
  [OPERATIONAL_STATE.CONNECTED]: 'bg-primary',
  [OPERATIONAL_STATE.STALE]: 'bg-amber-400',
  [OPERATIONAL_STATE.LOADING]: 'bg-amber-400',
}

function formatClock(msOrIso) {
  if (!msOrIso) return null
  const date = new Date(msOrIso)
  if (Number.isNaN(date.getTime())) return null
  try {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return null
  }
}

function labelFor(state, clock) {
  switch (state) {
    case OPERATIONAL_STATE.CONNECTED:
      return clock ? `${LABEL_OPERATIONAL_STATUS_CONNECTED} · Updated ${clock}` : LABEL_OPERATIONAL_STATUS_CONNECTED
    case OPERATIONAL_STATE.STALE:
      return clock ? `${LABEL_OPERATIONAL_STATUS_STALE} · last updated ${clock}` : LABEL_OPERATIONAL_STATUS_STALE
    case OPERATIONAL_STATE.LOADING:
    case OPERATIONAL_STATE.IDLE:
      return LABEL_OPERATIONAL_STATUS_LOADING
    case OPERATIONAL_STATE.SESSION_REQUIRED:
      return LABEL_OPERATIONAL_STATUS_SESSION_REQUIRED
    case OPERATIONAL_STATE.FORBIDDEN:
      return LABEL_OPERATIONAL_STATUS_FORBIDDEN
    case OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED:
      return LABEL_OPERATIONAL_STATUS_HOST_COMPOSITION_REQUIRED
    default:
      return LABEL_OPERATIONAL_STATUS_UNAVAILABLE
  }
}

export default function OperationalStatusChip({ state, lastRefreshedAt, onRefresh }) {
  const clock = formatClock(lastRefreshedAt)
  const dotClass = DOT_CLASS[state] ?? 'bg-on-surface-variant/40'
  const isLoading = state === OPERATIONAL_STATE.LOADING

  return (
    <div className="flex items-center gap-2 rounded-full border border-outline-variant/30 bg-surface-container/70 px-3 py-1 text-xs">
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
      <span className="text-on-surface-variant">{labelFor(state, clock)}</span>
      <button
        type="button"
        onClick={onRefresh}
        disabled={isLoading}
        aria-label="Refresh operational context"
        title={ACTION_REFRESH_OPERATIONAL_CONTEXT}
        className="ml-1 text-on-surface-variant hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-40"
      >
        {ACTION_REFRESH_OPERATIONAL_CONTEXT}
      </button>
    </div>
  )
}
