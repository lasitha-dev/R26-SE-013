import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import SourcePopup from '../components/SourcePopup'
import { REAL_SOURCES_20200928 } from './fixtures/realLsdOriginFixture'

describe('LSD-UI-04: SourcePopup (plan Section 19) -- only real API-backed fields', () => {
  const feature = REAL_SOURCES_20200928.features[0]

  it('renders the real source_id, gps_quality, availability_quality and coordinates verbatim', () => {
    const html = renderToStaticMarkup(React.createElement(SourcePopup, { feature, onViewSpatialContext: () => {}, onClose: () => {} }))
    expect(html).toContain('WAHIS_PDF:Event_3473.pdf:002409')
    expect(html).toContain('EXACT')
    expect(html).toContain('EVENT_DATE_PROXY')
    expect(html).toContain('9.6735') // lat.toFixed(4)
  })

  it('never renders a fabricated "Confirmed" badge, farm name, district, or case count -- none of these exist on the real source response', () => {
    const html = renderToStaticMarkup(React.createElement(SourcePopup, { feature, onViewSpatialContext: () => {}, onClose: () => {} }))
    expect(html).not.toContain('Confirmed')
    expect(html).toContain('Historical source') // the honest label instead
  })

  it('renders nothing for a null feature (no popup when nothing is selected)', () => {
    expect(renderToStaticMarkup(React.createElement(SourcePopup, { feature: null, onViewSpatialContext: () => {}, onClose: () => {} }))).toBe('')
  })
})
