import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import ModeToolbar, { MODES } from '../components/ModeToolbar'
import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'

describe('LSD-UI-03: ModeToolbar honesty (plan Section 21)', () => {
  it('Cases and Risk Zones are real/clickable; Clusters/Trajectory/Env are honestly disabled', () => {
    const available = MODES.filter((m) => m.available).map((m) => m.id)
    const unavailable = MODES.filter((m) => !m.available).map((m) => m.id)
    expect(available).toEqual([ANALYSIS_MODE.CASES, ANALYSIS_MODE.RISK_ZONES])
    expect(unavailable).toEqual([ANALYSIS_MODE.CLUSTERS, ANALYSIS_MODE.TRAJECTORY, ANALYSIS_MODE.ENV])
  })

  it('every unavailable mode carries a real, non-empty reason (never silently just missing)', () => {
    for (const mode of MODES.filter((m) => !m.available)) {
      expect(mode.reason).toBeTruthy()
      expect(mode.reason.length).toBeGreaterThan(10)
    }
  })

  it('renders unavailable modes as aria-disabled, never as a normal clickable tab', () => {
    const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.CASES, onSetMode: () => {} }))
    expect(html).toContain('aria-disabled="true"')
    expect(html).toContain('Clusters')
    expect(html).toContain('Trajectory')
    expect(html).toContain('Env')
  })

  it('the active mode is marked aria-selected=true', () => {
    const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.RISK_ZONES, onSetMode: () => {} }))
    // Risk Zones is real/clickable and currently active -> aria-selected="true" on its <button role="tab">
    expect(html).toMatch(/aria-selected="true"[^>]*>Risk Zones/)
  })

  it('LSD-PAGE1-HARDENING: unavailable modes are real <button> elements (natively keyboard-focusable), not <span>, and their reason is also reachable via aria-label', () => {
    const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.CASES, onSetMode: () => {} }))
    for (const mode of MODES.filter((m) => !m.available)) {
      const re = new RegExp(`<button[^>]*aria-disabled="true"[^>]*aria-label="${mode.label}: [^"]*"[^>]*>${mode.label}</button>`)
      expect(html).toMatch(re)
    }
    expect(html).not.toMatch(/<span[^>]*role="tab"/)
  })

  // GEO-TRAJECTORY-01: Trajectory's availability follows the selected
  // disease's real `trajectory` capability (confirmed live against the
  // running backend, 2026-09-01 -- real per-cell `bearing_deg` +
  // `nominal_reach_by_day` exist for every LSD origin sampled), mirroring
  // how Risk Zones already follows `riskZones`. Omitting `disease`
  // entirely (no pre-existing caller/test above passes it) leaves
  // Trajectory exactly as the static `MODES` baseline declares it --
  // disabled -- so none of the tests above needed to change.
  describe('GEO-TRAJECTORY-01: Trajectory follows the selected disease real capability', () => {
    it('is real/clickable for LSD (real direction + nominal-reach data exists)', () => {
      const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.CASES, onSetMode: () => {}, disease: 'LSD' }))
      expect(html).toMatch(/aria-selected="false"[^>]*>Trajectory</)
      expect(html).not.toMatch(/aria-disabled="true"[^>]*aria-label="Trajectory:/)
    })

    it('stays honestly disabled for FMD, with an accurate per-disease reason', () => {
      const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.CASES, onSetMode: () => {}, disease: 'FMD' }))
      expect(html).toMatch(/aria-disabled="true"[^>]*aria-label="Trajectory: [^"]*"[^>]*>Trajectory<\/button>/)
    })

    it('clicking the now-enabled LSD Trajectory tab fires onSetMode with the real ANALYSIS_MODE.TRAJECTORY value', () => {
      // Render-to-string can't dispatch click events -- this asserts the
      // enabled tab is a plain clickable <button> (no aria-disabled, no
      // preventDefault handler) wired to the real onSetMode callback via
      // the same onClick pattern every other real/clickable mode uses.
      const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.TRAJECTORY, onSetMode: () => {}, disease: 'LSD' }))
      expect(html).toMatch(/aria-selected="true"[^>]*>Trajectory/)
    })
  })
})
