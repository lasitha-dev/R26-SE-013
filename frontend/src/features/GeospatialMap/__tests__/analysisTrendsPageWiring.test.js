import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * PAGE-3-CURRENT-DASHBOARD: replaces the retired GEO-ANALYSIS-02 wiring
 * suite. That suite asserted the OLD retrospective/Matara-deep-dive
 * design (real Sri Lanka historical/model evidence, an explicit Matara
 * point-in-polygon filter, an origin selector/evidence-availability
 * panel). The page has since been rebuilt into a small CURRENT-
 * surveillance dashboard sourced from the same real, current, DB-backed
 * Verified Clinical Context collection Page 1's own confirmed-case red
 * markers already use -- this suite verifies THAT design instead.
 */

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const pageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'AnalysisTrendsPage.jsx'), 'utf-8')
const kpiRowSrc = readFileSync(join(FEATURE_ROOT, 'components', 'CurrentKpiRow.jsx'), 'utf-8')
const mostAffectedSrc = readFileSync(join(FEATURE_ROOT, 'components', 'CurrentMostAffectedAreas.jsx'), 'utf-8')
const windowToggleSrc = readFileSync(join(FEATURE_ROOT, 'components', 'CurrentActivityWindowToggle.jsx'), 'utf-8')
const surveillanceAdapterSrc = readFileSync(join(FEATURE_ROOT, 'adapters', 'currentSurveillance.js'), 'utf-8')

const analysisAdapterSrc = readFileSync(join(FEATURE_ROOT, 'adapters', 'analysisSurveillance.js'), 'utf-8')
const analysisCardsSrc = readFileSync(join(FEATURE_ROOT, 'components', 'AnalysisSurveillanceCards.jsx'), 'utf-8')
const ALL_NEW_FILES = [pageSrc, kpiRowSrc, mostAffectedSrc, windowToggleSrc, surveillanceAdapterSrc, analysisAdapterSrc, analysisCardsSrc]

describe('PAGE-3-CURRENT-DASHBOARD-01: the retired Matara/historical deep-dive is gone', () => {
  it('no Matara-scoped component is imported', () => {
    for (const forbidden of [
      'AnalysisTrendsMataraKpiCards',
      'AnalysisTrendsMataraOriginTable',
      'AnalysisTrendsOriginSelector',
      'AnalysisTrendsOriginAnalyticsPanel',
      'AnalysisTrendsEvidencePanel',
      'AnalysisTrendsKeySpatialInsights',
      'AnalysisTrendsSummaryPanel',
    ]) {
      expect(pageSrc).not.toContain(forbidden)
    }
  })

  it('no retrospective/historical data hook or ledger is used by the page itself', () => {
    // useDistrictGeometry is now used only for the vet's OWN authorised district
    // (the 'My district' analysis scope); never a fixed/default district.
    for (const forbidden of ['useAnalysisTrends', 'useNationalOutbreaks', 'filterOriginsInsideDistrict', 'DEFAULT_ANALYSIS_DISTRICT']) {
      expect(pageSrc).not.toContain(forbidden)
    }
  })

  it('the retrospective research record section is not on the page; the current sections never use it', () => {
    expect(pageSrc).not.toContain('HistoricalResearchSection')
    expect(pageSrc).not.toContain('useAnalysisTrends')
    // The current sections derive only from the national ADRS case records.
    // Most affected areas: the windowed real-record table (analysisSurveillance.js).
    expect(pageSrc).toContain('buildAffectedAreas(prepared, {')
    expect(pageSrc).toContain('buildDailyActivity(records, { windowDays })')
  })

  it('no "Retrospective evidence" / "AREA SCOPE · MATARA" / retrospective footer wording remains', () => {
    expect(pageSrc).not.toMatch(/Retrospective evidence/i)
    expect(pageSrc).not.toMatch(/AREA SCOPE/i)
    expect(pageSrc.toLowerCase()).not.toContain('matara')
  })

  it('the chart section is titled "Recent Outbreak Activity", never "Historical Outbreak Activity"', () => {
    expect(pageSrc).toContain('Recent Outbreak Activity')
    expect(pageSrc).not.toMatch(/Historical Outbreak Activity/i)
  })

  it('no origin selector, evidence-availability panel, or key-spatial-insights section is rendered', () => {
    expect(pageSrc).not.toMatch(/Origin Analysis|Evidence Availability|Key Spatial Insights|Selected Origin/i)
  })
})

describe('PAGE-3-CURRENT-DASHBOARD-02: sourced from the real current operational collection, never the historical one', () => {
  it('the page reads the national case records -- the SAME collection Page 1 draws as countrywide case markers', () => {
    expect(pageSrc).toContain("from '../context/useNationalCases'")
    expect(pageSrc).toContain('useNationalCases(')
  })

  it('its Sri Lanka scope is the national population, never the vet district surveillance contexts', () => {
    expect(pageSrc).toContain('prepareRecords(nationalCases.data?.records, ctx.selectedDisease, districtCollection)')
    expect(pageSrc).toContain('scopeRecords(prepared, { scope: analysisScope, districtName })')
    expect(pageSrc).not.toContain('surveillanceContexts')
  })

  it('never counts Page-1 presentation-only forecast/spread visuals as current records', () => {
    for (const forbidden of ['predictedHotspots', 'riskZones', 'trajectory', 'presentationForecast', 'myAreaPresentationForecast']) {
      expect(surveillanceAdapterSrc).not.toContain(forbidden)
      expect(pageSrc).not.toContain(forbidden)
    }
  })
})

describe('PAGE-3-CURRENT-DASHBOARD-03: current control set is 7D/14D/30D, default 14D', () => {
  it('window options are 7D/14D/30D plus 90D for older real activity', () => {
    expect(surveillanceAdapterSrc).toMatch(/label:\s*'90D'/)
    expect(surveillanceAdapterSrc).toMatch(/label:\s*'7D'/)
    expect(surveillanceAdapterSrc).toMatch(/label:\s*'14D'/)
    expect(surveillanceAdapterSrc).toMatch(/label:\s*'30D'/)
    expect(surveillanceAdapterSrc).not.toMatch(/label:\s*'12W'|label:\s*'YTD'/)
  })

  it('the default window is 14 days', () => {
    expect(surveillanceAdapterSrc).toContain('DEFAULT_CURRENT_ACTIVITY_WINDOW_DAYS = 14')
  })

  it('the old 30D/12W/YTD historical toggle is not used by the page', () => {
    expect(pageSrc).not.toContain('AnalysisTrendsWindowToggle')
    expect(pageSrc).not.toContain('filterTrendPointsByWindow')
  })
})

describe('PAGE-3-CURRENT-DASHBOARD-04: honest unavailable states, never a fabricated number', () => {
  it('Current Clusters is a fixed, honest N/A', () => {
    expect(kpiRowSrc).toContain('N/A')
    expect(kpiRowSrc).toContain('Current cluster output unavailable')
  })

  it('Forecast Horizon never depends on an origin selection that no longer exists on this page', () => {
    expect(kpiRowSrc).toContain('Not available')
    expect(pageSrc).not.toMatch(/selectedOriginId|selectOutbreak\(/)
  })

  it('zero current data stays zero rather than substituting historical/retrospective numbers', () => {
    expect(pageSrc).toContain('No current outbreak activity in this period.')
    expect(mostAffectedSrc).toMatch(/No current affected areas/)
  })

  it('no mock/sample/fake fallback data exists in any of the new files', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src.toLowerCase()).not.toMatch(/mock_|sample_data|fake_data|placeholder.*count/)
    }
  })
})

describe('PAGE-3-CURRENT-DASHBOARD-05: Most Affected Areas is current-case-derived only', () => {
  it('rows come from buildNationalMostAffectedAreas over the disease-filtered national records', () => {
    // Most affected areas: the windowed real-record table (analysisSurveillance.js).
    expect(pageSrc).toContain('buildAffectedAreas(prepared, {')
  })

  it('never pads a short real result with filler rows', () => {
    expect(mostAffectedSrc).not.toMatch(/while\s*\(.*<\s*5|push\(\{\s*district:\s*['"]/)
  })
})

describe('PAGE-3-CURRENT-DASHBOARD-06: no map on this page', () => {
  it('no map rendering component/library is imported anywhere in the new files', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/MapLibreCanvas|MapView|MapCanvas|from ['"]leaflet['"]|from ['"]maplibre-gl['"]|react-leaflet/)
    }
  })
})

describe('PAGE-3-CURRENT-DASHBOARD-07: reactive recompute on disease change (Section 18/24)', () => {
  it('reuses the shared ctx.selectedDisease / ctx.selectDisease state, never a second disease store', () => {
    expect(pageSrc).toContain('ctx.selectedDisease')
    expect(pageSrc).toContain('ctx.selectDisease')
  })

  it('every derived KPI/chart/table value is memoized on records, which itself depends on ctx.selectedDisease', () => {
    expect(pageSrc).toContain('[nationalCases.data, ctx.selectedDisease, districtCollection]')
    expect(pageSrc).toContain('[prepared, analysisScope, districtName]')
    expect(pageSrc).toContain('useMemo(() => summarizeWindow(records, { windowDays, scope: analysisScope }), [records, windowDays, analysisScope])')
    expect(pageSrc).toContain('useMemo(() => buildDailyActivity(records, { windowDays }), [records, windowDays])')
  })
})

describe('PAGE-3-CURRENT-DASHBOARD-08: no polling introduced by this page (Section 11A-POLL-01 stays satisfied)', () => {
  it('no setInterval/setTimeout in any of the new files -- the only real recurring timer stays inside useOperationalContext.js', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/setInterval\(|setTimeout\(/)
    }
  })
})
