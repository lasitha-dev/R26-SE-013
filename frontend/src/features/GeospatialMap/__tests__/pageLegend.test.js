import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import PageLegend from '../components/PageLegend'
import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'

describe('LSD-PAGE1-HARDENING: PageLegend (plan Section 8/14/15/21/22)', () => {
  it('is collapsed by default -- only the toggle button renders, not the panel content', () => {
    const html = renderToStaticMarkup(React.createElement(PageLegend, { analysisMode: ANALYSIS_MODE.CASES, riskStats: null }))
    expect(html).toContain('aria-expanded="false"')
    expect(html).not.toContain('Relative spatial')
  })

  it('Cases mode never mentions risk/probability wording', () => {
    const html = renderToStaticMarkup(React.createElement(PageLegend, { analysisMode: ANALYSIS_MODE.CASES, riskStats: null }))
    expect(html.toLowerCase()).not.toContain('probability')
    expect(html.toLowerCase()).not.toContain('risk score')
  })

  it('Risk Zones legend content (rendered open) uses the vetted relative-score wording, never a probability/percentage framing', () => {
    const html = renderToStaticMarkup(
      React.createElement(PageLegend, {
        analysisMode: ANALYSIS_MODE.RISK_ZONES,
        riskStats: { min: 0.2, max: 0.82, hasVariation: true, hasUnavailable: false, allUnavailable: false },
        initialOpen: true,
      }),
    )
    expect(html).toContain('Relative spatial risk score')
    expect(html).toContain('not infection probability')
    expect(html).toContain('Static T0 spatial ranking context')
    expect(html.toLowerCase()).not.toContain('82% infection')
    expect(html.toLowerCase()).not.toContain('82% risk')
    expect(html).toContain('aria-label="Hide map legend"')
  })

  it('Risk Zones legend never converts a raw score into a percentage claim (0.82 stays 0.82, not "82%")', () => {
    const html = renderToStaticMarkup(
      React.createElement(PageLegend, {
        analysisMode: ANALYSIS_MODE.RISK_ZONES,
        riskStats: { min: 0.2, max: 0.82, hasVariation: true, hasUnavailable: false, allUnavailable: false },
        initialOpen: true,
      }),
    )
    expect(html).toContain('0.82')
    expect(html).not.toMatch(/\d+%/)
  })
})
