import React, { useEffect, useState } from 'react'

import { fetchAnalysisCells, fetchAnalysisSources } from './api/geospatialApi'
import DiagnosticsPanel from './components/DiagnosticsPanel'
import MapView from './components/MapView'
import OriginSelector from './components/OriginSelector'
import ProtocolStatusBadge from './components/ProtocolStatusBadge'
import SummaryPanel from './components/SummaryPanel'
import { errorStatusMessage } from './semanticLabels'
import { PHASE, isTransportUsable } from './state/snapshotAssembly'
import { useGeospatialSnapshot } from './state/useGeospatialSnapshot'

/**
 * Checkpoint 11A/11B: top-level feature orchestrator. Uses the
 * WebSocket transport for the full scientific snapshot (summary/
 * sources/cells); HTTP `/summary`/`/cells`/`/sources` remain available
 * for direct inspection/debugging but are not required by this
 * component -- WebSocket alone provides byte-identical content
 * (Checkpoint 10B/10B.1a HTTP<->WS equivalence guarantee).
 *
 * Checkpoint 11B Part 17 layout: HEADER (title + protocol/runtime
 * status, historical-replay limitation always visible -- Part 15) ->
 * LEFT control panel (origin selection/transport) -> CENTER map
 * (`MapView`, a pure view over `state.currentCommittedSnapshot` only)
 * -> RIGHT scientific panel (rate/reach/disclaimers) -> collapsible
 * transport diagnostics at the bottom.
 */
export default function GeospatialMapFeature() {
  const { state, runProtocolPreflight, connect, requestSnapshot, refreshSnapshot } = useGeospatialSnapshot()
  const [selectedOriginId, setSelectedOriginId] = useState('')

  // Checkpoint 11A.1 Part 8: `runProtocolPreflight` now always resolves
  // (never rejects, even on a backend-unreachable failure -- see its
  // definition), so this `.then()` can no longer produce an unhandled
  // promise rejection; no `.catch()` is needed.
  useEffect(() => {
    runProtocolPreflight().then((compatibility) => {
      if (compatibility.status === 'PROTOCOL_COMPATIBLE') {
        connect()
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleLoad = () => {
    if (!selectedOriginId) return
    requestSnapshot(selectedOriginId)
  }

  const handleRefresh = () => {
    if (!selectedOriginId) return
    refreshSnapshot(selectedOriginId)
  }

  const snapshot = state.currentCommittedSnapshot
  const isStreaming = state.phase === PHASE.SNAPSHOT_REQUESTED || state.phase === PHASE.SNAPSHOT_STREAMING
  const transportReady = isTransportUsable(state.phase)

  return (
    <div className="space-y-3 p-4">
      <header className="space-y-1">
        <h2 className="text-lg font-semibold">Geospatial Outbreak Research Map</h2>
        <ProtocolStatusBadge phase={state.phase} protocol={state.protocol} error={state.error} />
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr_320px]">
        <aside className="space-y-4" aria-label="Map controls">
          <OriginSelector
            selectedOriginId={selectedOriginId}
            onSelect={setSelectedOriginId}
            onRequest={handleLoad}
            transportReady={transportReady}
          />
          <button
            type="button"
            disabled={!snapshot || !transportReady}
            onClick={handleRefresh}
            className="w-full rounded border px-3 py-1 text-sm disabled:opacity-40"
          >
            Refresh (explicit)
          </button>
          <div className="text-xs text-gray-500">
            Transport: {transportReady ? 'ready' : 'not ready'} {isStreaming && '· streaming…'}
          </div>
          {state.transportNotice && (
            <div className="rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
              {errorStatusMessage(state.transportNotice.status)}
            </div>
          )}
        </aside>

        <main aria-label="Geographic map">
          {state.phase === PHASE.INCOMPATIBLE_BACKEND_PROTOCOL && (
            <div className="rounded border border-red-300 bg-red-50 p-4 text-red-800">{state.error?.message}</div>
          )}
          {state.phase === PHASE.ERROR && (
            <div className="rounded border border-red-300 bg-red-50 p-4 text-red-800">{errorStatusMessage(state.error?.status)}</div>
          )}
          {isStreaming && <div className="p-4 text-sm text-gray-500">Loading scientific snapshot…</div>}
          {!snapshot && !isStreaming && state.phase !== PHASE.ERROR && state.phase !== PHASE.INCOMPATIBLE_BACKEND_PROTOCOL && (
            <div className="p-4 text-sm text-gray-500">Select a forecast origin and click Load snapshot.</div>
          )}
          {snapshot && <MapView snapshot={snapshot} />}
        </main>

        <aside aria-label="Scientific summary">{snapshot && <SummaryPanel summary={snapshot.summary} />}</aside>
      </div>

      {snapshot && (
        <DiagnosticsPanel metadata={snapshot.summary.analysis_metadata} snapshotId={snapshot.snapshotId} generatedAtUtc={snapshot.summary.generated_at_utc} />
      )}
    </div>
  )
}

// Kept for direct HTTP inspection/debugging tooling -- not used by the
// primary WS-driven flow above.
export async function debugFetchCellsAndSources(forecastOriginId) {
  const [cells, sources] = await Promise.all([fetchAnalysisCells(forecastOriginId), fetchAnalysisSources(forecastOriginId)])
  return { cells, sources }
}
