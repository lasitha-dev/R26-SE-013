import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import PageLegend from '../components/PageLegend'
import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'

// GEO-VISUAL-POLISH-03: a real, varied `riskTierStats` fixture -- matches
// `computeRiskTierStats`'s own real return shape (quartile breakpoints +
// real per-tier counts), never the old continuous min/max shape.
const VARIED_TIER_STATS = {
  q1: 0.2,
  median: 0.4,
  q3: 0.6,
  hasVariation: true,
  hasUnavailable: false,
  allUnavailable: false,
  validCount: 8,
  counts: { highest: 2, high: 2, moderate: 2, lower: 2 },
}

describe('LSD-PAGE1-HARDENING: PageLegend (plan Section 8/14/15/21/22)', () => {
  it('is collapsed by default -- only the toggle button renders, not the panel content', () => {
    const html = renderToStaticMarkup(React.createElement(PageLegend, { analysisMode: ANALYSIS_MODE.CASES, riskTierStats: null }))
    expect(html).toContain('aria-expanded="false"')
    expect(html).not.toContain('Relative spatial')
  })

  it('Cases mode never mentions risk/probability wording', () => {
    const html = renderToStaticMarkup(React.createElement(PageLegend, { analysisMode: ANALYSIS_MODE.CASES, riskTierStats: null }))
    expect(html.toLowerCase()).not.toContain('probability')
    expect(html.toLowerCase()).not.toContain('risk score')
  })

  it('Risk Zones legend content (rendered open) uses the vetted relative-score wording, never a probability/percentage framing', () => {
    const html = renderToStaticMarkup(
      React.createElement(PageLegend, {
        analysisMode: ANALYSIS_MODE.RISK_ZONES,
        riskTierStats: VARIED_TIER_STATS,
        initialOpen: true,
      }),
    )
    expect(html).toContain('Relative spatial risk score')
    // The ONLY appearance of "infection" anywhere in this legend is
    // inside the negated disclaimer sentence itself -- never an
    // affirmative "X% infection" claim.
    expect(html).toContain('not infection probability')
    expect(html.match(/infection/gi)?.length).toBe(1)
    expect(html).toContain('Static T0 spatial ranking context')
    expect(html).toContain('aria-label="Hide map legend"')
  })

  it('Risk Zones legend shows the four discrete relative tiers with REAL per-tier counts, never a percentage', () => {
    const html = renderToStaticMarkup(
      React.createElement(PageLegend, {
        analysisMode: ANALYSIS_MODE.RISK_ZONES,
        riskTierStats: VARIED_TIER_STATS,
        initialOpen: true,
      }),
    )
    expect(html).toContain('Highest relative risk')
    expect(html).toContain('Elevated relative risk')
    expect(html).toContain('Moderate relative risk')
    expect(html).toContain('Lower relative risk')
    // Real counts (2 cells in each tier of the fixture above) appear as
    // plain integers, never a "%" anywhere in the rendered legend.
    expect(html).not.toMatch(/\d+%/)
    expect((html.match(/>2</g) || []).length).toBeGreaterThanOrEqual(4)
  })

  it('an all-equal-score snapshot falls back to the honest neutral single-color message, never a fabricated 4-tier split', () => {
    const html = renderToStaticMarkup(
      React.createElement(PageLegend, {
        analysisMode: ANALYSIS_MODE.RISK_ZONES,
        riskTierStats: { q1: 0.4, median: 0.4, q3: 0.4, hasVariation: false, hasUnavailable: false, allUnavailable: false, validCount: 3, counts: { highest: 0, high: 0, moderate: 0, lower: 0 } },
        initialOpen: true,
      }),
    )
    expect(html.toLowerCase()).toContain('no tiers in this snapshot')
    expect(html).not.toContain('Highest relative risk')
  })

  it('an all-unavailable snapshot is stated honestly, never a fabricated tier count', () => {
    const html = renderToStaticMarkup(
      React.createElement(PageLegend, {
        analysisMode: ANALYSIS_MODE.RISK_ZONES,
        riskTierStats: { q1: null, median: null, q3: null, hasVariation: false, hasUnavailable: true, allUnavailable: true, validCount: 0, counts: { highest: 0, high: 0, moderate: 0, lower: 0 } },
        initialOpen: true,
      }),
    )
    expect(html.toLowerCase()).toContain('unavailable')
    expect(html).not.toContain('Highest relative risk')
  })
})
