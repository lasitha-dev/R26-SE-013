import React, { useState } from 'react'

import { EVENT_STREAM_STATE, TRANSPORT_MODE } from '../context/operationalEventsReducer'
import { OPERATIONAL_STATE } from '../context/operationalRefreshReducer'
import SnapshotStatusChip, { SNAPSHOT_STATUS } from './SnapshotStatusChip'
import OperationalStatusChip from './OperationalStatusChip'

/**
 * GEO29A Part 10/14/15, GEO30A Section 10/11: a real browser screenshot
 * showed `SnapshotStatusChip`/`OperationalStatusChip` always rendered
 * inline in the compact header row, wrapping onto multiple lines at
 * ordinary widths and visually colliding with each other ("LOADING
 * SNAPSHOT..." overlapping "Check for newer snapshot"). Neither chip's
 * own functionality is removed here -- both are unchanged, just
 * relocated from "always inline" to "one compact indicator, expandable
 * on demand".
 *
 * GEO-LIVE-UPDATE-RECOVERY-06 / GEO-HYBRID-LIVE-SYNC-08 Phase 10: the
 * always-visible label previously collapsed to "LIVE" whenever the
 * reconciliation POLL merely succeeded -- exactly the "SSE/socket
 * connected" != "genuine event rendered" confusion this checkpoint exists
 * to fix, even though it wasn't reading the push transport at all. It is
 * now honestly derived, driven by BOTH the real push-transport state
 * (`useVerifiedClinicalEvents.js`) and whether a genuine event/
 * reconciliation was actually just processed (`lastGenuineUpdateAt`, set
 * by `OutbreakMapPage.jsx`). Deterministic priority (Phase 10's own
 * recommended order, first match wins):
 *  1. LIVE UPDATE -- a real case was just verified/changed in the last
 *                    few seconds (via push OR the fallback reconciliation
 *                    cycle catching what push missed). A successful but
 *                    UNCHANGED snapshot never triggers this.
 *  2. RECONNECTING -- the push transport itself is unhealthy (not
 *                    connected, not genuinely push, or stale).
 *  3. SYNCING      -- push is healthy, but the operational reconciliation
 *                    fetch is actively loading/recovering right now.
 *  4. CONNECTED    -- stable push, reconciliation steady, no recent
 *                    applied change -- no claim about a specific event.
 * `LIVE DATA UNAVAILABLE` overrides all four when the operational fetch
 * itself has failed (401/403/404/error) -- neither transport is being
 * honest then. The scientific/historical snapshot's own diagnostic detail
 * still lives one click away in the expanded panel, unaffected by any of
 * this.
 */
const LIVE_UPDATE_DISPLAY_MS = 6000 // mirrors MapLibreCanvas.jsx's ARRIVAL_HIGHLIGHT_MS pulse window

const OPERATIONAL_FAILURE_STATES = new Set([
  OPERATIONAL_STATE.SESSION_REQUIRED,
  OPERATIONAL_STATE.FORBIDDEN,
  OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED,
  OPERATIONAL_STATE.ERROR,
])
const DOT_PRIORITY = {
  bad: 'bg-red-400',
  warn: 'bg-amber-400',
  ok: 'bg-primary',
}

function snapshotSeverity(status) {
  if (status === SNAPSHOT_STATUS.UNAVAILABLE) return 'bad'
  if (status === SNAPSHOT_STATUS.LOADING) return 'warn'
  return 'ok'
}

function operationalSeverity(state) {
  if (
    state === OPERATIONAL_STATE.SESSION_REQUIRED ||
    state === OPERATIONAL_STATE.FORBIDDEN ||
    state === OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED ||
    state === OPERATIONAL_STATE.ERROR
  ) {
    return 'bad'
  }
  if (state === OPERATIONAL_STATE.STALE || state === OPERATIONAL_STATE.LOADING || state === OPERATIONAL_STATE.IDLE) {
    return 'warn'
  }
  return 'ok'
}

/** GEO-HYBRID-LIVE-SYNC-08 Phase 10: the vet-facing label is about the
 * real operational (verified-clinical) connection specifically -- never a
 * blend with the scientific/historical snapshot state, which has its own
 * separate wording inside the expanded panel. See the module docstring
 * above for the exact priority-ordered contract. */
function liveStatusLabel({ operationalState, pushState, pushTransportMode, pushIsStale, lastGenuineUpdateAt, now }) {
  if (OPERATIONAL_FAILURE_STATES.has(operationalState)) return 'LIVE DATA UNAVAILABLE'

  if (lastGenuineUpdateAt != null && now - lastGenuineUpdateAt < LIVE_UPDATE_DISPLAY_MS) {
    return 'LIVE UPDATE'
  }

  const pushHealthy = pushState === EVENT_STREAM_STATE.CONNECTED && pushTransportMode === TRANSPORT_MODE.PUSH && !pushIsStale
  if (!pushHealthy) return 'RECONNECTING'

  const reconciliationRecovering = operationalState === OPERATIONAL_STATE.LOADING || operationalState === OPERATIONAL_STATE.STALE
  if (reconciliationRecovering) return 'SYNCING'

  return 'CONNECTED'
}

const SEVERITY_RANK = { bad: 2, warn: 1, ok: 0 }

/** Keeps the header dot's color honest against `liveStatusLabel`'s own
 * RECONNECTING/SYNCING tiers -- a healthy reconciliation fetch alone must
 * never show as fully "ok" while the label already admits push is down. */
function pushSeverity(pushState, pushTransportMode, pushIsStale) {
  if (pushState === EVENT_STREAM_STATE.SESSION_REQUIRED || pushState === EVENT_STREAM_STATE.FORBIDDEN) return 'bad'
  if (pushState === EVENT_STREAM_STATE.CONNECTED && pushTransportMode === TRANSPORT_MODE.PUSH && !pushIsStale) return 'ok'
  return 'warn'
}

export default function StatusDiagnosticsMenu({
  snapshotStatus,
  snapshotAsOfDate,
  onCheckForNewerSnapshot,
  operationalState,
  operationalLastRefreshedAt,
  onRefreshOperational,
  pushState,
  pushTransportMode,
  pushIsStale,
  lastGenuineUpdateAt,
  // GEO-VISUAL-POLISH-02 Section 2/10: an honest, non-blocking trace of
  // the real database -> forecast-origin -> per-origin-geometry ->
  // rendered-marker pipeline (`OutbreakMapPage.jsx` computes every field
  // from real counts -- `useNationalOutbreaks.js`'s own state plus the
  // actual FeatureCollections handed to MapLibre -- never a guess).
  // Optional so every existing caller/test that omits it renders exactly
  // as before.
  originResolutionStats,
}) {
  const [expanded, setExpanded] = useState(false)

  const worst = [snapshotSeverity(snapshotStatus), operationalSeverity(operationalState), pushSeverity(pushState, pushTransportMode, pushIsStale)].sort(
    (a, b) => SEVERITY_RANK[b] - SEVERITY_RANK[a],
  )[0]

  const label = liveStatusLabel({
    operationalState,
    pushState,
    pushTransportMode,
    pushIsStale,
    lastGenuineUpdateAt,
    now: Date.now(),
  })

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label="Live surveillance connection status -- show diagnostics"
        title="Live surveillance connection status -- click for details"
        className="flex items-center gap-1.5 rounded-md border border-outline-variant/30 bg-surface-container-high/60 px-2.5 py-1 text-xs text-on-surface-variant hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${DOT_PRIORITY[worst]}`} />
        <span className="font-medium uppercase tracking-wide">{label}</span>
        <span aria-hidden="true" className="material-symbols-outlined text-[16px] text-on-surface-variant/60">
          {expanded ? 'expand_less' : 'expand_more'}
        </span>
      </button>

      {expanded && (
        <div className="absolute right-0 top-full z-30 mt-2 flex w-72 flex-col gap-2 rounded-lg border border-outline-variant/30 bg-surface-container p-2 shadow-xl">
          <SnapshotStatusChip status={snapshotStatus} asOfDate={snapshotAsOfDate} onCheckForNewer={onCheckForNewerSnapshot} />
          <OperationalStatusChip state={operationalState} lastRefreshedAt={operationalLastRefreshedAt} onRefresh={onRefreshOperational} />
          {originResolutionStats && <OriginResolutionTrace stats={originResolutionStats} />}
        </div>
      )}
    </div>
  )
}

/**
 * GEO-VISUAL-POLISH-02 Section 1/2/10: the four stages reported
 * separately and honestly, never conflated into one "X of Y rendered"
 * claim --
 *  1. forecast origins (`/origins` -- a grouped, per-country-day unit;
 *     NOT the same thing as stage 2);
 *  2. underlying real trigger/source records those origins bundle
 *     (`trigger_source_count` summed across origins);
 *  3. real source geometries actually resolved (each origin's own
 *     `/analysis/{id}/sources` or `/origins/{id}/trigger-sources`
 *     response, summed) -- can be LESS than stage 2 if an individual
 *     source lacks a stored coordinate (dropped server-side, never
 *     fabricated) or an origin's request failed outright;
 *  4. marker FEATURES actually handed to the MapLibre national-sources
 *     source -- can be LESS than stage 3 because co-located real records
 *     collapse into one stacked marker (`nationalSourcePresentation.js`),
 *     never because anything was hidden/dropped silently.
 * `failedOriginCount` names the real, already-documented backend
 * condition (one origin's geometry request can take >30s / fail
 * outright) rather than letting it read as "fewer real origins exist".
 */
function OriginResolutionTrace({ stats }) {
  const { expectedOriginCount, resolvedOriginCount, failedOriginCount, expectedSourceRecordCount, resolvedGeometryFeatureCount, renderedFeatureCount } = stats
  return (
    <div className="rounded-md border border-outline-variant/20 bg-surface-container-low/60 px-2 py-1.5 text-[11px] text-on-surface-variant">
      <div className="mb-1 font-semibold uppercase tracking-wide text-on-surface-variant/70">Outbreak data trace</div>
      <div className="flex items-center justify-between gap-2">
        <span>Origins resolved</span>
        <span className="font-mono text-on-surface">
          {resolvedOriginCount}/{expectedOriginCount}
          {failedOriginCount > 0 ? ` (${failedOriginCount} unavailable)` : ''}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span>Underlying source records</span>
        <span className="font-mono text-on-surface">{expectedSourceRecordCount}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span>Geometries resolved</span>
        <span className="font-mono text-on-surface">{resolvedGeometryFeatureCount}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span>Markers rendered</span>
        <span className="font-mono text-on-surface">{renderedFeatureCount}</span>
      </div>
      {failedOriginCount > 0 && (
        <div className="mt-1 text-amber-300">
          {failedOriginCount} origin{failedOriginCount === 1 ? '' : 's'} could not be resolved (slow/unavailable backend response) -- already-resolved origins above remain shown.
        </div>
      )}
    </div>
  )
}
