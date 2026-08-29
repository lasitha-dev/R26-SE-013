import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import CellDetailPanel from '../components/CellDetailPanel'
import { computeRiskColorStats } from '../components/mapLibreAdapter'
import MapLegend from '../components/MapLegend'
import ProtocolStatusBadge from '../components/ProtocolStatusBadge'
import { FORBIDDEN_WORDING } from '../semanticLabels'
import { PHASE } from '../state/snapshotAssembly'

// react-dom/server's renderToStaticMarkup runs pure Node -> Node, no
// DOM/jsdom required -- this keeps 11B's component-level checks on the
// same "no heavy browser test framework" footing as every other test in
// this feature (Part 22).

function cellFeature(id, { score = 0.4, bearing = null } = {}) {
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [70.0, 35.0] },
    properties: {
      scientific_cell_id: id,
      risk: { raw_c0_score: score, score_status: 'SCORED', semantics: 'RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY' },
      direction: { bearing_deg: bearing, directional_clarity: 0.7, direction_status: 'DIRECTIONAL_RESULTANT_DEFINED' },
    },
  }
}

function renderText(element) {
  return renderToStaticMarkup(element).replace(/<[^>]+>/g, ' ')
}

describe('11B-RISK-05: legend explicitly states colors are not cross-snapshot comparable', () => {
  it('MapLegend renders the non-comparability disclaimer text', () => {
    const stats = computeRiskColorStats([cellFeature('C1', { score: 0.2 }), cellFeature('C2', { score: 0.8 })])
    const text = renderText(React.createElement(MapLegend, { stats }))
    expect(text).toMatch(/not directly comparable between different snapshots/i)
  })
})

describe('11B-A11Y-01: the legend communicates layer meaning textually, not only through color', () => {
  it('MapLegend names every layer with a word ("Scientific cells", "Eligible outbreak sources", direction arrow)', () => {
    const stats = computeRiskColorStats([cellFeature('C1')])
    const text = renderText(React.createElement(MapLegend, { stats }))
    expect(text).toMatch(/Scientific cells/)
    expect(text).toMatch(/Eligible outbreak sources/)
    expect(text).toMatch(/Direction arrow/)
  })
})

describe('11B-DIR-04: directional clarity is never named confidence (component output)', () => {
  it('CellDetailPanel never renders the word "confidence" for directional_clarity', () => {
    const cell = cellFeature('C1', { bearing: 12.5 })
    const text = renderText(React.createElement(CellDetailPanel, { cell }))
    expect(text.toLowerCase()).not.toContain('confidence')
    expect(text).toContain('directional_clarity')
  })
})

describe('11B-SEM: rendered legend/detail-panel text never affirmatively contains forbidden wording', () => {
  it('MapLegend output', () => {
    const stats = computeRiskColorStats([cellFeature('C1', { score: 0.3 }), cellFeature('C2', { score: 0.3 })])
    const text = renderText(React.createElement(MapLegend, { stats })).toLowerCase()
    for (const phrase of FORBIDDEN_WORDING) {
      if (text.includes(phrase)) {
        const idx = text.indexOf(phrase)
        const window = text.slice(Math.max(0, idx - 20), idx)
        expect(/\b(not|never|no)\b/.test(window), `"${phrase}" appears without negation in legend text`).toBe(true)
      }
    }
  })

  it('CellDetailPanel output', () => {
    const text = renderText(React.createElement(CellDetailPanel, { cell: cellFeature('C1', { score: 0.5, bearing: 0.0 }) })).toLowerCase()
    for (const phrase of FORBIDDEN_WORDING) {
      expect(text.includes(phrase)).toBe(false)
    }
  })
})

describe('11B-SEM-01: risk is never called probability/accuracy in rendered legend text', () => {
  it('MapLegend contains the risk disclaimer and no affirmative probability/accuracy claim', () => {
    const stats = computeRiskColorStats([cellFeature('C1', { score: 0.3 }), cellFeature('C2', { score: 0.9 })])
    const text = renderText(React.createElement(MapLegend, { stats })).toLowerCase()
    expect(text).toContain('not infection probability')
    // every occurrence of the phrase must be preceded by a negation word
    let searchFrom = 0
    while (true) {
      const idx = text.indexOf('infection probability', searchFrom)
      if (idx === -1) break
      const window = text.slice(Math.max(0, idx - 20), idx)
      expect(/\b(not|never|no)\b/.test(window)).toBe(true)
      searchFrom = idx + 1
    }
  })
})

describe('11B-SEM-02: direction is never called a predicted spread direction in rendered legend text', () => {
  it('MapLegend states the C0-derived-local-geometric-tendency disclaimer', () => {
    const stats = computeRiskColorStats([cellFeature('C1')])
    const text = renderText(React.createElement(MapLegend, { stats }))
    expect(text).toContain('C0-derived local geometric tendency')
    expect(text).toContain('not a predicted disease-spread direction')
  })
})

describe('11B-SEM-03: historical-replay / live-not-implemented status is visible without opening diagnostics', () => {
  it('ProtocolStatusBadge renders the historical-replay disclaimer unconditionally (not inside a collapsible element)', () => {
    const text = renderToStaticMarkup(React.createElement(ProtocolStatusBadge, { phase: PHASE.SNAPSHOT_COMPLETE, protocol: null, error: null }))
    expect(text).not.toMatch(/<details/)
    expect(text).toMatch(/Historical retrospective replay/)
    expect(text).toMatch(/live operational forecasting is not implemented/i)
  })
})

describe('CellDetailPanel: raw values displayed verbatim, never rounded-then-overwritten', () => {
  it('shows the exact raw_c0_score and bearing_deg values passed in', () => {
    const cell = cellFeature('C1', { score: 0.123456789, bearing: 271.5 })
    const text = renderText(React.createElement(CellDetailPanel, { cell }))
    expect(text).toContain('0.123456789')
    expect(text).toContain('271.5')
  })

  it('a null bearing renders an explicit "undefined direction" label, never a bare 0/blank', () => {
    const cell = cellFeature('C1', { bearing: null })
    const text = renderText(React.createElement(CellDetailPanel, { cell }))
    expect(text).toMatch(/null \(undefined direction\)/)
  })

  it('an unavailable (null) raw_c0_score is never displayed as 0 or "low"', () => {
    const cell = cellFeature('C1', { score: null })
    const text = renderText(React.createElement(CellDetailPanel, { cell }))
    expect(text).toContain('unavailable')
    expect(text).not.toMatch(/raw_c0_score:\s*0(?!\.)/)
  })
})
