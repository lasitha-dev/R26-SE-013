import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import ObservedTimelineControl from '../components/ObservedTimelineControl'
import PageLegend from '../components/PageLegend'
import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'
import {
  LABEL_OBSERVED_CASES_TIMELINE,
  LABEL_OBSERVED_OUTBREAKS_TIMELINE,
} from '../semanticLabels'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

const timelineProps = {
  isPlaybackActive: false,
  onSelectDate: () => {},
  onPlay: () => {},
  onPause: () => {},
  onPrev: () => {},
  onNext: () => {},
  windowLabel: 'Last 14 days',
  emptyStateText: 'No verified LSD cases in My District · Matara',
  reduceMotion: false,
}

describe('GEO33B Section 10: the Cases-mode timeline always names its real dataset', () => {
  it('shows an explicit "Observed cases" header alongside the real replay date when dates exist', () => {
    const html = renderToStaticMarkup(
      React.createElement(ObservedTimelineControl, { ...timelineProps, dates: ['2026-08-24', '2026-08-29'], selectedDateKey: '2026-08-24' }),
    )
    expect(html).toContain(LABEL_OBSERVED_CASES_TIMELINE)
    expect(html).toContain('24 Aug 2026')
  })

  it('states "At latest" rather than inventing a date when nothing has been scrubbed back to', () => {
    const html = renderToStaticMarkup(
      React.createElement(ObservedTimelineControl, { ...timelineProps, dates: ['2026-08-24', '2026-08-29'], selectedDateKey: null }),
    )
    // The active date is the real LAST date, and the sub-line says the
    // vet is at latest -- never a fabricated "today".
    expect(html).toContain('29 Aug 2026')
    expect(html).toContain('At latest')
  })

  it('names the dataset in the zero-events state too -- never a bare, ambiguous "Observed"', () => {
    const html = renderToStaticMarkup(React.createElement(ObservedTimelineControl, { ...timelineProps, dates: [], selectedDateKey: null }))
    expect(html).toContain(LABEL_OBSERVED_CASES_TIMELINE)
    expect(html).toContain('Last 14 days')
  })

  it('never labels an observed replay as a forecast, in any state', () => {
    for (const dates of [[], ['2026-08-24', '2026-08-29']]) {
      const html = renderToStaticMarkup(React.createElement(ObservedTimelineControl, { ...timelineProps, dates, selectedDateKey: null }))
      expect(html.toLowerCase()).not.toContain('forecast')
    }
  })

  it('the accessible group name follows the real dataset, so the two observed timelines can never be confused', () => {
    const cases = renderToStaticMarkup(React.createElement(ObservedTimelineControl, { ...timelineProps, dates: [], selectedDateKey: null }))
    expect(cases).toContain(`aria-label="${LABEL_OBSERVED_CASES_TIMELINE} timeline"`)
    const outbreaks = renderToStaticMarkup(
      React.createElement(ObservedTimelineControl, { ...timelineProps, dates: [], selectedDateKey: null, datasetLabel: LABEL_OBSERVED_OUTBREAKS_TIMELINE }),
    )
    expect(outbreaks).toContain(`aria-label="${LABEL_OBSERVED_OUTBREAKS_TIMELINE} timeline"`)
  })

  it('the page wires the CLINICAL dataset label explicitly, and its dates come only from real verification timestamps', () => {
    const pageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')
    expect(pageSrc).toContain('datasetLabel={LABEL_OBSERVED_CASES_TIMELINE}')
    expect(pageSrc).toContain('buildObservedReplayDates(operationalContextsForDisease)')
    const replaySrc = readFileSync(join(FEATURE_ROOT, 'adapters', 'observedReplay.js'), 'utf-8')
    expect(replaySrc).toContain('parseVerificationTime(context?.verificationTime)')
  })

  it('the two observed datasets have distinct declared labels -- they can never collapse into one heading', () => {
    expect(LABEL_OBSERVED_CASES_TIMELINE).not.toBe(LABEL_OBSERVED_OUTBREAKS_TIMELINE)
    for (const label of [LABEL_OBSERVED_CASES_TIMELINE, LABEL_OBSERVED_OUTBREAKS_TIMELINE]) {
      expect(label.toLowerCase()).not.toContain('forecast')
    }
  })
})

describe('GEO33B Section 9: the legend keys only what is really drawn', () => {
  function renderCasesLegend(props) {
    return renderToStaticMarkup(
      React.createElement(PageLegend, { analysisMode: ANALYSIS_MODE.CASES, riskStats: null, initialOpen: true, ...props }),
    )
  }

  it('distinguishes the national observed source, the verified clinical location, and the district outline', () => {
    const html = renderCasesLegend({ hasClinicalMarkers: true })
    expect(html).toContain('Observed outbreak source (national)')
    expect(html).toContain('Verified clinical location')
    expect(html).toContain('My District boundary')
  })

  it('never presents a live clinical swatch when no real clinical marker is on the map', () => {
    const html = renderCasesLegend({ hasClinicalMarkers: false })
    expect(html).toContain('None shown in the current selection')
  })

  it('drops that caveat as soon as a real clinical marker IS drawn', () => {
    const html = renderCasesLegend({ hasClinicalMarkers: true })
    expect(html).not.toContain('None shown in the current selection')
  })

  it('only keys the stack ring when a real stack exists', () => {
    expect(renderCasesLegend({ hasStackedSources: false })).not.toContain('More than one record here')
    expect(renderCasesLegend({ hasStackedSources: true })).toContain('More than one record here')
  })

  it('the marker swatch follows the real per-disease icon shape the map paints', () => {
    // diamond = LSD (rotated square), circle = FMD.
    expect(renderCasesLegend({ nationalMarkerShape: 'diamond' })).toContain('rotate-45')
    expect(renderCasesLegend({ nationalMarkerShape: 'circle' })).not.toContain('rotate-45')
  })

  it('every legend colour is the exact hex its own map layer paints -- the key can never drift from the map', () => {
    const legendSrc = readFileSync(join(FEATURE_ROOT, 'components', 'PageLegend.jsx'), 'utf-8')
    const iconsSrc = readFileSync(join(FEATURE_ROOT, 'components', 'presentationIcons.js'), 'utf-8')
    const canvasSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8')
    const stackSrc = readFileSync(join(FEATURE_ROOT, 'adapters', 'nationalSourcePresentation.js'), 'utf-8')
    // red-500 core, shared by the historical source icon.
    expect(legendSrc).toContain("OBSERVED_SOURCE_COLOR = '#ef4444'")
    expect(iconsSrc).toContain('[239, 68, 68, 255]')
    // emerald selection halo stroke.
    expect(legendSrc).toContain("SELECTION_HALO_COLOR = '#10b981'")
    expect(canvasSrc).toContain("'circle-stroke-color': '#10b981'")
    // mint district outline.
    expect(legendSrc).toContain("DISTRICT_BOUNDARY_COLOR = '#4edea3'")
    expect(canvasSrc).toContain("'line-color': '#4edea3'")
    // stack ring.
    expect(legendSrc).toContain("STACK_RING_COLOR = '#fca5a5'")
    expect(stackSrc).toContain("'circle-stroke-color': '#fca5a5'")
  })

  it('the collapsed control explains what it opens, for both pointer and assistive users', () => {
    const collapsed = renderToStaticMarkup(React.createElement(PageLegend, { analysisMode: ANALYSIS_MODE.CASES, riskStats: null }))
    expect(collapsed).toContain('aria-expanded="false"')
    expect(collapsed).toContain('Show map legend')
    expect(collapsed).toContain('title="Map legend')
  })

  it('the page tells the legend what is really on the map, never a hardcoded true', () => {
    const pageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')
    expect(pageSrc).toContain('hasClinicalMarkers={showOperationalLayer && operationalFeatures.features.length > 0}')
    expect(pageSrc).toContain('hasStackedSources={hasStackedSources}')
  })
})

describe('GEO33B Section 8/11: the replay pulse is per-feature and time-bounded, never a global animation', () => {
  const canvasSrc = readFileSync(join(FEATURE_ROOT, 'components', 'MapLibreCanvas.jsx'), 'utf-8')
  const pageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')

  it('markers revealed by a real replay step are pulsed through the SAME feature-state machinery as a live arrival', () => {
    expect(canvasSrc).toContain('newlyRevealedKeys')
    expect(canvasSrc).toContain('pulseKeySignature')
    expect(canvasSrc).toContain('pulseActive: true')
  })

  it('the pulse clears itself, so nothing animates permanently', () => {
    const effectStart = canvasSrc.indexOf('const pulseKeySignature')
    const effectBody = canvasSrc.slice(effectStart, canvasSrc.indexOf('}, [pulseKeySignature, reduceMotion])'))
    expect(effectBody).toContain('applyToAll({ justArrived: false, pulseActive: false, pulseExpanded: false })')
    expect(effectBody).toContain('cancelAnimationFrame(frame)')
  })

  it('the halo layer falls through to zero opacity when neither selected nor pulsing -- a settled marker has no ring', () => {
    const layerSrc = readFileSync(join(FEATURE_ROOT, 'components', 'operationalMarkerLayer.js'), 'utf-8')
    const haloStart = layerSrc.indexOf('export function operationalMarkerHaloPaint')
    const halo = layerSrc.slice(haloStart)
    expect(halo).toContain("'circle-opacity': [")
    // The last branch of the opacity `case` is the literal 0 fallthrough.
    expect(halo).toMatch(/0\.5,\s*\n\s*0,\s*\n\s*\]/)
  })

  it('the selection halo is a separate, steady state -- distinct from the pulse', () => {
    const layerSrc = readFileSync(join(FEATURE_ROOT, 'components', 'operationalMarkerLayer.js'), 'utf-8')
    expect(layerSrc).toContain("['boolean', ['feature-state', 'selected'], false]")
    expect(canvasSrc).toContain('selectedOperationalKey')
  })

  it('the reveal diff is gated on the real replay date changing, not on any list change', () => {
    expect(pageSrc).toContain('previousReplayRevealRef')
    expect(pageSrc).toContain('replayDateChanged')
    expect(pageSrc).toContain('}, [revealedOperationalKeys, observedReplayDateKey])')
  })
})

describe('GEO33B Section 14: the floating mode toolbar uses a restrained shadow', () => {
  // Comments are stripped first, mirroring `visualLayerStructural.test.js`'s
  // own convention: the code comment that DOCUMENTS the removed
  // `shadow-lg` would otherwise false-positive a plain source scan.
  const toolbarSrc = readFileSync(join(FEATURE_ROOT, 'components', 'ModeToolbar.jsx'), 'utf-8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/.*$/gm, '')

  it('no longer uses the heavy shadow-lg/xl/2xl blur over live geography', () => {
    expect(toolbarSrc).not.toMatch(/shadow-(lg|xl|2xl)/)
  })

  it('uses a small shadow plus a real border for separation instead', () => {
    expect(toolbarSrc).toContain('shadow-sm')
    expect(toolbarSrc).toMatch(/border border-\S+/)
  })
})

describe('GEO33B Section 12: the clinical layer stays scoped to the vet\'s own authorized data', () => {
  const pageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'OutbreakMapPage.jsx'), 'utf-8')

  it('markers are built only from the authorized operational-context response, never the national scope', () => {
    expect(pageSrc).toContain('operational.data?.surveillanceContexts')
    // The national/scientific collection never feeds the clinical layer.
    const memoStart = pageSrc.indexOf('const operationalContextsForDisease = useMemo(')
    const memoBody = pageSrc.slice(memoStart, pageSrc.indexOf('[operational.data, ctx.selectedDisease, observationWindowDays],', memoStart))
    expect(memoBody).not.toContain('national')
    expect(memoBody).not.toContain('nationalSourcesFC')
  })

  it('a genuinely empty result shows an honest empty state rather than falling back to other data', () => {
    expect(pageSrc).toContain('operationalContextsForDisease.length === 0')
    expect(pageSrc).toContain('showNoVerifiedCasesEmptyState')
    // The empty state is gated on the fetch having actually SUCCEEDED --
    // a loading/error state is never dressed up as "zero cases".
    expect(pageSrc).toMatch(/OPERATIONAL_STATE\.CONNECTED \|\| operational\.state === OPERATIONAL_STATE\.STALE/)
  })

  it('the adapter drops any context whose farm did not resolve to an authorized, located farm', () => {
    const adapterSrc = readFileSync(join(FEATURE_ROOT, 'adapters', 'operationalContextAdapter.js'), 'utf-8')
    expect(adapterSrc).toContain('const farm = farmsById.get(rawContext.farm_id)')
    expect(adapterSrc).toContain("if (!farm || farm.locationStatus !== 'VALID') return null")
  })
})
