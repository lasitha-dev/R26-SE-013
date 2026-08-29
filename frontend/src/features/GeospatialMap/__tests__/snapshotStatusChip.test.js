import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import SnapshotStatusChip, { SNAPSHOT_STATUS } from '../components/SnapshotStatusChip'

describe('LSD-UI-03: SnapshotStatusChip never claims LIVE (plan Section 9)', () => {
  it('none of the three real statuses renders the word LIVE anywhere', () => {
    for (const status of Object.values(SNAPSHOT_STATUS)) {
      const html = renderToStaticMarkup(React.createElement(SnapshotStatusChip, { status }))
      expect(html.toUpperCase()).not.toMatch(/\bLIVE\b/)
    }
  })

  it('CONNECTED renders the honest "Snapshot connected" label', () => {
    const html = renderToStaticMarkup(React.createElement(SnapshotStatusChip, { status: SNAPSHOT_STATUS.CONNECTED }))
    expect(html).toContain('Snapshot connected')
  })

  it('renders "Check for newer snapshot" only when a handler is supplied (existing refresh mechanism, no auto-polling)', () => {
    const withHandler = renderToStaticMarkup(React.createElement(SnapshotStatusChip, { status: SNAPSHOT_STATUS.CONNECTED, onCheckForNewer: () => {} }))
    expect(withHandler).toContain('Check for newer snapshot')
    const withoutHandler = renderToStaticMarkup(React.createElement(SnapshotStatusChip, { status: SNAPSHOT_STATUS.CONNECTED }))
    expect(withoutHandler).not.toContain('Check for newer snapshot')
  })

  it('an unknown status falls back to the honest UNAVAILABLE label, never a blank/crash', () => {
    const html = renderToStaticMarkup(React.createElement(SnapshotStatusChip, { status: 'not-a-real-status' }))
    expect(html).toContain('Snapshot unavailable')
  })
})
