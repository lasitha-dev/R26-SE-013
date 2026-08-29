import React from 'react'

import { ACTION_CHECK_FOR_NEWER_SNAPSHOT, LABEL_SNAPSHOT_CONNECTED, LABEL_SNAPSHOT_LOADING, LABEL_SNAPSHOT_UNAVAILABLE } from '../semanticLabels'

/**
 * LSD-UI-03/09: plan Section 9's non-negotiable rule -- the real
 * transport is `HISTORICAL_RETROSPECTIVE_REPLAY_SNAPSHOT_TRANSPORT`
 * (confirmed live against `/api/geospatial/protocol`, 2026-08-27), never
 * true live server push, so this NEVER renders "LIVE". Three honest
 * states only (centralized in `semanticLabels.js`, per this feature's
 * wording-firewall convention), plus the existing no-auto-polling
 * `refreshSnapshot` mechanism exposed as an explicit user action.
 */
export const SNAPSHOT_STATUS = {
  CONNECTED: 'connected',
  LOADING: 'loading',
  UNAVAILABLE: 'unavailable',
}

const CONFIG = {
  [SNAPSHOT_STATUS.CONNECTED]: { dot: 'bg-emerald-400', text: 'text-emerald-300', label: LABEL_SNAPSHOT_CONNECTED },
  [SNAPSHOT_STATUS.LOADING]: { dot: 'bg-amber-400', text: 'text-amber-300', label: LABEL_SNAPSHOT_LOADING },
  [SNAPSHOT_STATUS.UNAVAILABLE]: { dot: 'bg-slate-500', text: 'text-slate-400', label: LABEL_SNAPSHOT_UNAVAILABLE },
}

export default function SnapshotStatusChip({ status, asOfDate, onCheckForNewer }) {
  const config = CONFIG[status] ?? CONFIG[SNAPSHOT_STATUS.UNAVAILABLE]
  return (
    <div className="flex items-center gap-2 rounded-full border border-white/10 bg-slate-900/70 px-3 py-1 text-xs">
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
      <span className={`font-mono uppercase tracking-wide ${config.text}`}>{config.label}</span>
      {asOfDate && <span className="text-slate-400">· historical replay, {asOfDate}</span>}
      {onCheckForNewer && (
        <button type="button" onClick={onCheckForNewer} className="ml-1 text-slate-300 underline decoration-dotted hover:text-white">
          {ACTION_CHECK_FOR_NEWER_SNAPSHOT}
        </button>
      )}
    </div>
  )
}
