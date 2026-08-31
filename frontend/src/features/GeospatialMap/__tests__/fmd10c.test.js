import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { getOutbreakAdapter } from '../adapters/index'
import { FmdModelNotReadyError, mapOriginsToOutbreakSummaries as fmdMapOrigins } from '../adapters/fmdOutbreakAdapter'
import FmdOriginPanel from '../components/FmdOriginPanel'
import ModeToolbar from '../components/ModeToolbar'
import { ANALYSIS_MODE, initialOutbreakSelectionState, outbreakSelectionReducer } from '../context/outbreakSelectionReducer'
import { FMD_RISK_STATUS } from '../context/useFmdOriginRisk'
import { CAPABILITY, DISEASE_CODE, hasCapability } from '../disease/diseaseRegistry'
import { LABEL_RELATIVE_ORIGIN_SPATIAL_SCORE } from '../semanticLabels'

/**
 * FMD-10C: this file's hook-adjacent tests deliberately assert the exact
 * capability-gate booleans `useNationalOutbreaks.js`/
 * `useSelectedOutbreakFrames.js`/`useFmdOriginRisk.js` consult in their
 * guard clauses, rather than rendering the hooks themselves -- this
 * repo's Vitest environment is Node-only (no DOM/`act`), the same
 * constraint `MapLibreCanvas.jsx`'s own header comment documents, so a
 * `useEffect`-driven hook cannot be reliably exercised here. Pure
 * logic (reducers, adapters, capability config, static-markup
 * component rendering) is unit-tested directly instead, matching every
 * other test file in this feature.
 */

describe('FMD-10C: disease capability configuration', () => {
  it('FMD supports historicalOrigins/scalarOriginRisk/analysisHistorical only', () => {
    expect(hasCapability(DISEASE_CODE.FMD, CAPABILITY.HISTORICAL_ORIGINS)).toBe(true)
    expect(hasCapability(DISEASE_CODE.FMD, CAPABILITY.SCALAR_ORIGIN_RISK)).toBe(true)
    expect(hasCapability(DISEASE_CODE.FMD, CAPABILITY.ANALYSIS_HISTORICAL)).toBe(true)
  })

  it('FMD does NOT support any spatial/forecast-frame capability', () => {
    for (const capability of [
      CAPABILITY.SPATIAL_CELLS,
      CAPABILITY.RISK_ZONES,
      CAPABILITY.TRAJECTORY,
      CAPABILITY.DIRECTION,
      CAPABILITY.APPARENT_RATE,
      CAPABILITY.NOMINAL_REACH,
      CAPABILITY.ENVIRONMENTAL_VECTORS,
      CAPABILITY.FORECAST_FRAMES,
    ]) {
      expect(hasCapability(DISEASE_CODE.FMD, capability)).toBe(false)
    }
  })

  it('LSD keeps its full pre-existing capability set (non-regression)', () => {
    expect(hasCapability(DISEASE_CODE.LSD, CAPABILITY.HISTORICAL_ORIGINS)).toBe(true)
    expect(hasCapability(DISEASE_CODE.LSD, CAPABILITY.SPATIAL_CELLS)).toBe(true)
    expect(hasCapability(DISEASE_CODE.LSD, CAPABILITY.RISK_ZONES)).toBe(true)
    expect(hasCapability(DISEASE_CODE.LSD, CAPABILITY.DIRECTION)).toBe(true)
    expect(hasCapability(DISEASE_CODE.LSD, CAPABILITY.APPARENT_RATE)).toBe(true)
    expect(hasCapability(DISEASE_CODE.LSD, CAPABILITY.NOMINAL_REACH)).toBe(true)
    expect(hasCapability(DISEASE_CODE.LSD, CAPABILITY.FORECAST_FRAMES)).toBe(true)
    // LSD has no scalar origin-level endpoint -- it has a per-cell
    // spatial rank surface instead, a materially different shape.
    expect(hasCapability(DISEASE_CODE.LSD, CAPABILITY.SCALAR_ORIGIN_RISK)).toBe(false)
  })
})

describe('FMD-10C: useNationalOutbreaks / useSelectedOutbreakFrames gating (guard-clause equivalence)', () => {
  it('historical-origin listing is allowed for FMD (the exact gate useNationalOutbreaks.js checks)', () => {
    expect(hasCapability(DISEASE_CODE.FMD, CAPABILITY.HISTORICAL_ORIGINS)).toBe(true)
  })

  it('the per-origin sources/cells/summary snapshot fetch is refused for FMD -- no /summary, /cells, or /sources request is ever attempted', () => {
    // useSelectedOutbreakFrames.js and useNationalOutbreaks.js both gate
    // their fetchAnalysisSummary/fetchAnalysisCells/fetchAnalysisSources
    // calls on exactly this capability; false here means those calls
    // structurally never fire for FMD.
    expect(hasCapability(DISEASE_CODE.FMD, CAPABILITY.SPATIAL_CELLS)).toBe(false)
  })

  it('the scalar FMD risk-score fetch is allowed for FMD -- the exact gate useFmdOriginRisk.js checks', () => {
    expect(hasCapability(DISEASE_CODE.FMD, CAPABILITY.SCALAR_ORIGIN_RISK)).toBe(true)
  })

  it('LSD has no scalar-risk fetch path at all (useFmdOriginRisk stays IDLE for LSD)', () => {
    expect(hasCapability(DISEASE_CODE.LSD, CAPABILITY.SCALAR_ORIGIN_RISK)).toBe(false)
  })
})

describe('FMD-10C: fmdOutbreakAdapter.mapOriginsToOutbreakSummaries is real; every other function still throws', () => {
  const REAL_FMD_ORIGINS_RESPONSE = {
    origins: [
      { forecast_origin_id: 'ORIGIN:Sri Lanka:2009-09-09', country: 'Sri Lanka', t0: '2009-09-09', trigger_source_count: 1 },
      { forecast_origin_id: 'ORIGIN:Sri Lanka:2010-01-13', country: 'Sri Lanka', t0: '2010-01-13', trigger_source_count: 1 },
    ],
    n_origins: 2,
  }

  it('maps real /origins?disease=fmd response items to the same summary shape lsdOutbreakAdapter produces', () => {
    const summaries = fmdMapOrigins(REAL_FMD_ORIGINS_RESPONSE)
    expect(summaries).toEqual([
      { outbreakId: 'ORIGIN:Sri Lanka:2009-09-09', country: 'Sri Lanka', t0: '2009-09-09', sourceCount: 1 },
      { outbreakId: 'ORIGIN:Sri Lanka:2010-01-13', country: 'Sri Lanka', t0: '2010-01-13', sourceCount: 1 },
    ])
  })

  it('getAvailableForecastDays/buildForecastFrame/computeRelevantOrigins still throw FmdModelNotReadyError (unchanged -- no spatial/forecast-frame data exists for FMD)', () => {
    const adapter = getOutbreakAdapter(DISEASE_CODE.FMD)
    expect(() => adapter.getAvailableForecastDays()).toThrow(FmdModelNotReadyError)
    expect(() => adapter.buildForecastFrame()).toThrow(FmdModelNotReadyError)
    expect(() => adapter.computeRelevantOrigins()).toThrow(FmdModelNotReadyError)
  })
})

describe('FMD-10C: ModeToolbar disables Risk Zones for a disease without the riskZones capability', () => {
  it('Risk Zones is aria-disabled when disease="FMD"', () => {
    const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.CASES, onSetMode: () => {}, disease: DISEASE_CODE.FMD }))
    expect(html).toMatch(/aria-disabled="true"[^>]*>Risk Zones/)
  })

  it('Cases stays a real, clickable, selected tab for FMD', () => {
    const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.CASES, onSetMode: () => {}, disease: DISEASE_CODE.FMD }))
    expect(html).toMatch(/aria-selected="true"[^>]*>Cases/)
  })

  it('Risk Zones stays real/clickable for LSD (non-regression, matches the pre-existing modeToolbar.test.js expectation)', () => {
    const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.CASES, onSetMode: () => {}, disease: DISEASE_CODE.LSD }))
    expect(html).not.toMatch(/aria-disabled="true"[^>]*>Risk Zones/)
  })

  it('omitting the disease prop entirely leaves Risk Zones exactly as MODES declares it (backward compatible)', () => {
    const html = renderToStaticMarkup(React.createElement(ModeToolbar, { analysisMode: ANALYSIS_MODE.CASES, onSetMode: () => {} }))
    expect(html).not.toMatch(/aria-disabled="true"[^>]*>Risk Zones/)
  })
})

describe('FMD-10C: disease switching resets an unsupported analysis mode to Cases', () => {
  it('Trajectory -> FMD resets to Cases', () => {
    const withTrajectory = { ...initialOutbreakSelectionState, analysisMode: ANALYSIS_MODE.TRAJECTORY }
    const next = outbreakSelectionReducer(withTrajectory, { type: 'SELECT_DISEASE', payload: { disease: DISEASE_CODE.FMD } })
    expect(next.analysisMode).toBe(ANALYSIS_MODE.CASES)
  })

  it('Risk Zones -> FMD resets to Cases (FMD has no nominal-reach ring to draw)', () => {
    const withRiskZones = { ...initialOutbreakSelectionState, analysisMode: ANALYSIS_MODE.RISK_ZONES }
    const next = outbreakSelectionReducer(withRiskZones, { type: 'SELECT_DISEASE', payload: { disease: DISEASE_CODE.FMD } })
    expect(next.analysisMode).toBe(ANALYSIS_MODE.CASES)
  })

  it('Cases -> FMD stays on Cases (already supported, never touched)', () => {
    const next = outbreakSelectionReducer(initialOutbreakSelectionState, { type: 'SELECT_DISEASE', payload: { disease: DISEASE_CODE.FMD } })
    expect(next.analysisMode).toBe(ANALYSIS_MODE.CASES)
  })

  it('Risk Zones -> LSD is left untouched (non-regression: LSD keeps its own real Risk Zones mode)', () => {
    const withRiskZones = { ...initialOutbreakSelectionState, selectedDisease: DISEASE_CODE.FMD, analysisMode: ANALYSIS_MODE.RISK_ZONES }
    const next = outbreakSelectionReducer(withRiskZones, { type: 'SELECT_DISEASE', payload: { disease: DISEASE_CODE.LSD } })
    expect(next.analysisMode).toBe(ANALYSIS_MODE.RISK_ZONES)
  })
})

describe('FMD-10C: LSD <-> FMD stale-selection isolation (shared reducer)', () => {
  it('a Page-1-selected outbreak/model-run/day/frame-horizon never survives a disease switch in either direction', () => {
    const lsdSelected = outbreakSelectionReducer(initialOutbreakSelectionState, {
      type: 'SELECT_OUTBREAK',
      payload: { outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', modelRunId: 'snap-1', availableForecastFrames: [0, 1, 2, 3, 4, 5, 6, 7] },
    })
    const switchedToFmd = outbreakSelectionReducer(lsdSelected, { type: 'SELECT_DISEASE', payload: { disease: DISEASE_CODE.FMD } })
    expect(switchedToFmd.selectedOutbreakId).toBeNull()
    expect(switchedToFmd.selectedModelRunId).toBeNull()
    expect(switchedToFmd.availableForecastFrames).toEqual([0])

    const fmdSelected = outbreakSelectionReducer(switchedToFmd, {
      type: 'SELECT_OUTBREAK',
      payload: { outbreakId: 'ORIGIN:Sri Lanka:2009-09-09' },
    })
    const switchedBackToLsd = outbreakSelectionReducer(fmdSelected, { type: 'SELECT_DISEASE', payload: { disease: DISEASE_CODE.LSD } })
    expect(switchedBackToLsd.selectedOutbreakId).toBeNull()
  })
})

describe('FMD-10C: FmdOriginPanel presents the raw scalar score honestly', () => {
  const origins = [{ outbreakId: 'ORIGIN:Sri Lanka:2009-09-09', country: 'Sri Lanka', t0: '2009-09-09', sourceCount: 1 }]

  it('shows the exact "Relative Origin Spatial Score" label and a raw decimal number, never a percentage', () => {
    const html = renderToStaticMarkup(
      React.createElement(FmdOriginPanel, {
        origins,
        selectedOriginId: 'ORIGIN:Sri Lanka:2009-09-09',
        onSelect: () => {},
        risk: { status: FMD_RISK_STATUS.READY, data: { risk_score: 0.4325798925661575, n_eligible_sources: 1 }, error: null },
      }),
    )
    expect(html).toContain(LABEL_RELATIVE_ORIGIN_SPATIAL_SCORE)
    expect(html).toContain('0.4326')
    expect(html).not.toContain('%')
    // The panel's own disclaimer explicitly NEGATES probability/confidence
    // framing ("not infection probability... not confidence") -- so the
    // words appear only inside that negation, never asserted affirmatively.
    expect(html.toLowerCase()).toContain('not infection probability')
    expect(html.toLowerCase()).toContain('not confidence')
  })

  it('renders an honest unavailable state, never a fabricated 0/placeholder score', () => {
    const html = renderToStaticMarkup(
      React.createElement(FmdOriginPanel, {
        origins,
        selectedOriginId: 'ORIGIN:Sri Lanka:2009-09-09',
        onSelect: () => {},
        risk: { status: FMD_RISK_STATUS.UNAVAILABLE, data: null, error: null },
      }),
    )
    expect(html).toContain('Unavailable for this origin')
  })

  it('renders nothing (no panel at all) when there are zero real origins -- never an empty fabricated list', () => {
    const html = renderToStaticMarkup(React.createElement(FmdOriginPanel, { origins: [], selectedOriginId: null, onSelect: () => {}, risk: null }))
    expect(html).toBe('')
  })
})
