import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import StatusDiagnosticsMenu from '../components/StatusDiagnosticsMenu'
import { EVENT_STREAM_STATE, TRANSPORT_MODE } from '../context/operationalEventsReducer'
import { OPERATIONAL_STATE } from '../context/operationalRefreshReducer'
import { SNAPSHOT_STATUS } from '../components/SnapshotStatusChip'

const noop = () => {}

/** A genuinely HEALTHY operational push transport -- the only inputs
 * `liveStatusLabel` (module-private) actually reads. Every test below
 * holds these fixed and varies only the SCIENTIFIC/historical-layer
 * props to prove the header label never reacts to them. */
const healthyOperationalProps = {
  operationalState: OPERATIONAL_STATE.CONNECTED,
  pushState: EVENT_STREAM_STATE.CONNECTED,
  pushTransportMode: TRANSPORT_MODE.PUSH,
  pushIsStale: false,
  lastGenuineUpdateAt: null,
}

function renderMenu(props) {
  return renderToStaticMarkup(
    React.createElement(StatusDiagnosticsMenu, {
      snapshotAsOfDate: undefined,
      onCheckForNewerSnapshot: noop,
      operationalLastRefreshedAt: null,
      onRefreshOperational: noop,
      ...healthyOperationalProps,
      ...props,
    }),
  )
}

function headerLabel(html) {
  const match = html.match(/font-medium uppercase tracking-wide">([^<]*)</)
  return match ? match[1] : null
}

describe('GEO-PAGE1-FINAL Section 19: RECONNECTING is reserved for the operational push-transport connection, never a slow scientific/risk fetch', () => {
  it('a healthy operational transport shows CONNECTED even while the scientific/historical layer is LOADING', () => {
    const html = renderMenu({ snapshotStatus: SNAPSHOT_STATUS.LOADING })
    expect(headerLabel(html)).toBe('CONNECTED')
  })

  it('a healthy operational transport shows CONNECTED even while the scientific/historical layer is UNAVAILABLE (errored)', () => {
    const html = renderMenu({ snapshotStatus: SNAPSHOT_STATUS.UNAVAILABLE })
    expect(headerLabel(html)).toBe('CONNECTED')
  })

  it('a healthy operational transport never shows RECONNECTING regardless of the origin-resolution trace (partial/failed origins)', () => {
    const html = renderMenu({
      snapshotStatus: SNAPSHOT_STATUS.LOADING,
      originResolutionStats: { expectedOriginCount: 16, resolvedOriginCount: 3, failedOriginCount: 1, expectedSourceRecordCount: 16, resolvedGeometryFeatureCount: 3, renderedFeatureCount: 3 },
    })
    expect(headerLabel(html)).not.toBe('RECONNECTING')
  })

  it('RECONNECTING only appears when the push transport itself is genuinely unhealthy -- proven by flipping ONLY the operational props, scientific layer held CONNECTED/idle throughout', () => {
    const healthyScience = renderMenu({ snapshotStatus: SNAPSHOT_STATUS.CONNECTED, pushState: EVENT_STREAM_STATE.CONNECTED, pushTransportMode: TRANSPORT_MODE.PUSH, pushIsStale: false })
    expect(headerLabel(healthyScience)).toBe('CONNECTED')

    const unhealthyPush = renderMenu({ snapshotStatus: SNAPSHOT_STATUS.CONNECTED, pushState: EVENT_STREAM_STATE.RECONNECTING, pushTransportMode: TRANSPORT_MODE.DELTA_REFRESH, pushIsStale: true })
    expect(headerLabel(unhealthyPush)).toBe('RECONNECTING')
  })

  it('structural guarantee: the label-computing function reads only operational/push fields -- national/focus/scientific state is not even in its parameter list', () => {
    const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'components', 'StatusDiagnosticsMenu.jsx'), 'utf-8')
    const start = src.indexOf('function liveStatusLabel(')
    const end = src.indexOf(')', start)
    const signature = src.slice(start, end)
    expect(signature).not.toMatch(/national|focus|riskStatus|snapshotStatus/)
  })
})
