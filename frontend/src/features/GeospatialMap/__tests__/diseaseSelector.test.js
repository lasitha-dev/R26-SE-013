import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import DiseaseSelector from '../components/DiseaseSelector'
import { DISEASE_CODE } from '../disease/diseaseRegistry'

describe('LSD-PAGE1-HARDENING: DiseaseSelector honesty (plan Section 9/11)', () => {
  it('LSD renders as a real, clickable, pressed control when selected', () => {
    const html = renderToStaticMarkup(React.createElement(DiseaseSelector, { selected: DISEASE_CODE.LSD, onSelect: () => {} }))
    expect(html).toContain('LSD')
    expect(html).toMatch(/aria-pressed="true"[^>]*>LSD/)
  })
})

describe('FMD-10C: DiseaseSelector unlocks FMD once it has a real capability (historicalOrigins)', () => {
  // FMD-10C: FMD has real, live historical origins + a real scalar risk
  // score now (confirmed against the running backend, 2026-08-28), so
  // it must be a real, clickable option here -- the OLD "aria-disabled,
  // model not ready" rendering was correct only while FMD had genuinely
  // nothing real to show at all (pre-FMD-10C). Page 1's own
  // `!diseaseReady` banner still communicates the separate, still-true
  // fact that FMD's full LSD-shaped spatial model is not ready.
  it('FMD renders as a real, clickable button -- never aria-disabled', () => {
    const html = renderToStaticMarkup(React.createElement(DiseaseSelector, { selected: DISEASE_CODE.LSD, onSelect: () => {} }))
    expect(html).toMatch(/<button[^>]*>FMD<\/button>/)
    expect(html).not.toMatch(/aria-disabled="true"[^>]*>FMD/)
  })

  it('FMD is aria-pressed=true once selected (a genuine successful switch)', () => {
    const html = renderToStaticMarkup(React.createElement(DiseaseSelector, { selected: DISEASE_CODE.FMD, onSelect: () => {} }))
    expect(html).toMatch(/aria-pressed="true"[^>]*>FMD/)
  })
})
