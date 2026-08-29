import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const pageSrc = readFileSync(join(FEATURE_ROOT, 'pages', 'AnalysisTrendsPage.jsx'), 'utf-8')
const chartSrc = readFileSync(join(FEATURE_ROOT, 'components', 'AnalysisTrendsChart.jsx'), 'utf-8')
const summarySrc = readFileSync(join(FEATURE_ROOT, 'components', 'AnalysisTrendsSummaryPanel.jsx'), 'utf-8')
const originAnalyticsSrc = readFileSync(join(FEATURE_ROOT, 'components', 'AnalysisTrendsOriginAnalyticsPanel.jsx'), 'utf-8')
const originSelectorSrc = readFileSync(join(FEATURE_ROOT, 'components', 'AnalysisTrendsOriginSelector.jsx'), 'utf-8')
const evidenceSrc = readFileSync(join(FEATURE_ROOT, 'components', 'AnalysisTrendsEvidencePanel.jsx'), 'utf-8')
const diseaseToggleSrc = readFileSync(join(FEATURE_ROOT, 'components', 'AnalysisTrendsDiseaseToggle.jsx'), 'utf-8')
const hookSrc = readFileSync(join(FEATURE_ROOT, 'context', 'useAnalysisTrends.js'), 'utf-8')
const ledgerHookSrc = readFileSync(join(FEATURE_ROOT, 'context', 'useDiseaseOriginLedger.js'), 'utf-8')
const apiSrc = readFileSync(join(FEATURE_ROOT, 'api', 'analysisTrendsApi.js'), 'utf-8')
const adapterSrc = readFileSync(join(FEATURE_ROOT, 'adapters', 'analysisTrendsAdapter.js'), 'utf-8')

const ALL_NEW_FILES = [pageSrc, chartSrc, summarySrc, originAnalyticsSrc, originSelectorSrc, evidenceSrc, diseaseToggleSrc, hookSrc, ledgerHookSrc, apiSrc, adapterSrc]

describe('GEO-ANALYSIS-02-PAGE-01: no silent origin auto-selection (Section 10/41)', () => {
  it('selectedOriginId initializes to null, never pre-populated', () => {
    expect(pageSrc).toMatch(/useState\(null\)/)
  })

  it('the initial useAnalysisTrends call never passes a hardcoded/derived-non-user origin', () => {
    expect(pageSrc).toContain('originId: selectedOriginId')
  })

  it('no nearest/latest/first/highest-score auto-selection logic exists anywhere in the new files', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/nearest.*origin|latest.*origin|highest.*score|highest.*count/i)
    }
  })
})

describe('GEO-ANALYSIS-02-PAGE-02: explicit cross-page origin continuity (Section 11)', () => {
  it('adopts ctx.selectedOutbreakId only after verifying ledger membership', () => {
    expect(pageSrc).toContain('ledger.origins.some((o) => o.originId === ctx.selectedOutbreakId)')
  })

  it('adoption happens at most once via a ref guard, never on every render', () => {
    expect(pageSrc).toMatch(/seededFromSharedSelectionRef\.current\s*=\s*true/)
  })

  it('never trusts the origin id by string prefix parsing', () => {
    expect(pageSrc).not.toMatch(/startsWith\(['"]ORIGIN:/)
    expect(ledgerHookSrc).not.toMatch(/startsWith\(['"]ORIGIN:/)
  })
})

describe('GEO-ANALYSIS-02-PAGE-03: no country override anywhere (Section 4/36)', () => {
  it('the API client never sets a country query parameter or accepts a country argument', () => {
    expect(apiSrc).not.toMatch(/params\.set\(['"]country['"]/)
    expect(apiSrc).not.toMatch(/\bcountry\s*[,}]/) // no `country` in a destructured parameter list
  })

  it('the page never passes a country value into fetchAnalysisTrends/useAnalysisTrends', () => {
    expect(pageSrc).not.toMatch(/useAnalysisTrends\(\{[^}]*country/)
    expect(pageSrc).not.toMatch(/fetchAnalysisTrends\([^)]*country/)
  })

  it('no country selector/dropdown exists in any new component', () => {
    for (const src of [pageSrc, chartSrc, summarySrc, originAnalyticsSrc, originSelectorSrc, evidenceSrc, diseaseToggleSrc]) {
      expect(src).not.toMatch(/country.*select|select.*country/i)
    }
  })

  it('the disease-origin-ledger hook hardcodes the SAME Sri Lanka value Page 1 already uses, never a user-supplied one', () => {
    expect(ledgerHookSrc).toContain("const COUNTRY = 'Sri Lanka'")
    expect(ledgerHookSrc).not.toMatch(/props\.country|params\.country|query\.country/i)
  })
})

describe('GEO-ANALYSIS-02-PAGE-04: KPI wording correctness (Section 16/17)', () => {
  it('uses "Historical source records" label, never "cases"/"active"/"current infections"', () => {
    expect(summarySrc).toContain('LABEL_HISTORICAL_SOURCE_RECORDS')
    expect(summarySrc.toLowerCase()).not.toMatch(/cases today|active cases|current infections|confirmed active outbreaks/)
  })

  it('forecast origins rendered as a separate card, never summed with source count', () => {
    expect(summarySrc).toContain('LABEL_FORECAST_ORIGINS')
    expect(summarySrc).not.toMatch(/historicalSourceCount\s*\+\s*forecastOriginCount/)
    expect(summarySrc).not.toMatch(/forecastOriginCount\s*\+\s*historicalSourceCount/)
  })

  it('no invented percentage-change/growth/accuracy metric computed in the summary panel', () => {
    expect(summarySrc).not.toMatch(/growth|accuracy|change[Pp]ercent|improv(ed|ement)/)
  })

  it('observation coverage uses non-alarmist wording, never "Active period"/"Epidemic duration"', () => {
    expect(summarySrc).toContain('LABEL_OBSERVATION_COVERAGE')
    expect(summarySrc.toLowerCase()).not.toMatch(/active period|epidemic duration|current outbreak duration/)
  })
})

describe('GEO-ANALYSIS-02-PAGE-05: historical trend rendering (Section 18/19/20)', () => {
  it('chart reads points directly, never fabricates interpolated points', () => {
    expect(chartSrc).not.toMatch(/interpolat|smooth|bezier|spline/i)
  })

  it('zero-count points are rendered (height computed, never filtered out)', () => {
    expect(chartSrc).not.toMatch(/\.filter\(\s*\(?\w*\)?\s*=>\s*\w*\.count\s*[!=]==?\s*0/)
  })

  it('trend basis is read dynamically from the backend field, never hardcoded to WEEK or YEAR', () => {
    expect(pageSrc).toContain('data.historicalTrend.periodBasis')
    expect(pageSrc).not.toMatch(/periodBasis\s*=\s*['"]WEEK['"]/)
    expect(pageSrc).not.toMatch(/periodBasis\s*=\s*['"]YEAR['"]/)
  })

  it('no chart dependency was added -- pure SVG only', () => {
    expect(chartSrc).not.toMatch(/from ['"](recharts|chart\.js|d3|victory|nivo)['"]/)
  })
})

describe('GEO-ANALYSIS-02-PAGE-06: disease behavior (Section 9)', () => {
  it('disease change clears the selected origin', () => {
    expect(pageSrc).toContain('setSelectedOriginId(null)')
    expect(pageSrc).toMatch(/prevDiseaseRef/)
  })

  it('reuses the shared ctx.selectedDisease / ctx.selectDisease state, never a second disease store', () => {
    expect(pageSrc).toContain('ctx.selectedDisease')
    expect(pageSrc).toContain('ctx.selectDisease')
  })

  it('unknown disease is never silently defaulted to LSD in this page/hook', () => {
    for (const src of [pageSrc, hookSrc, apiSrc]) {
      expect(src).not.toMatch(/disease\s*(\|\|=|=\s*disease\s*\?\?)\s*['"]lsd['"]/i)
    }
  })

  it('both LSD and FMD are real, clickable disease options (never a disabled FMD button on this page)', () => {
    expect(diseaseToggleSrc).not.toMatch(/aria-disabled/)
    expect(diseaseToggleSrc).toContain('listDiseaseCodes')
  })
})

describe('GEO-ANALYSIS-02-PAGE-07: apparent rate / direction wording (Section 23/24)', () => {
  it('apparent rate uses "Apparent rate" label, never "virus speed"/"spread speed"/"transmission velocity"', () => {
    expect(originAnalyticsSrc).toContain('LABEL_ANALYSIS_APPARENT_RATE')
    expect(originAnalyticsSrc.toLowerCase()).not.toMatch(/virus speed|spread speed|future speed|transmission velocity/)
  })

  it('apparent rate uses km/day unit, never left unitless', () => {
    expect(originAnalyticsSrc).toContain('APPARENT_RATE_UNIT')
  })

  it('direction never computes an average/dominant/mean bearing in JS', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/average.*bearing|dominant.*bearing|mean.*bearing|mean.*direction/i)
    }
  })

  it('direction renders as an honest unavailable state, never a fabricated 0°', () => {
    expect(originAnalyticsSrc).toContain('LABEL_DIRECTION_NOT_DEFINED')
    expect(originAnalyticsSrc).not.toMatch(/directionContext.*0°|0°.*direction/i)
  })
})

describe('GEO-ANALYSIS-02-PAGE-08: nominal reach semantics (Section 25/26)', () => {
  it('exact nominal-reach disclaimer sentence appears as a fallback', () => {
    expect(originAnalyticsSrc).toContain('Nominal reach — visualization only, not a disease boundary.')
  })

  it('D0 is never rendered as a fabricated 0 km value -- only real D1-D7 entries are mapped', () => {
    expect(originAnalyticsSrc).toContain('nominalReach.days')
    expect(originAnalyticsSrc).not.toMatch(/day:\s*0.*nominalReachKm|D0.*0\s*km/i)
  })

  it('no farm inside/outside nominal-reach relation is computed on this page', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/inside.*reach|outside.*reach|within.*reach.*farm/i)
    }
  })

  it('no infection-radius/quarantine-radius/safe-boundary wording', () => {
    expect(originAnalyticsSrc.toLowerCase()).not.toMatch(/infection radius|quarantine radius|safe boundary|predicted infection area/)
  })
})

describe('GEO-ANALYSIS-02-PAGE-09: Relative Spatial Score semantics (Section 27/28/29)', () => {
  it('RSS values render as raw decimals via toFixed, never a percentage transform', () => {
    expect(originAnalyticsSrc).toMatch(/toFixed\(3\)/)
    expect(originAnalyticsSrc).not.toMatch(/\* 100|toFixed\(0\)\s*\+\s*['"]%['"]/)
  })

  it('RSS panel is labelled Relative Spatial Score', () => {
    expect(originAnalyticsSrc).toContain('LABEL_RSS_DISTRIBUTION')
  })

  it('no low/medium/high risk label is inferred from min/median/max', () => {
    expect(originAnalyticsSrc.toLowerCase()).not.toMatch(/\blow risk\b|\bmedium risk\b|\bhigh risk\b|\bsafe\b/)
  })

  it('no risk-color mapping (green/orange/red) tied to min/median/max', () => {
    expect(originAnalyticsSrc).not.toMatch(/(minScore|min_score).*(green|#22c55e|#16a34a)/i)
    expect(originAnalyticsSrc).not.toMatch(/(maxScore|max_score).*(red|#ef4444|#dc2626)/i)
  })

  it('cross-snapshot comparison is never fabricated -- only the unsupported label is rendered', () => {
    expect(originAnalyticsSrc).toContain('LABEL_CROSS_SNAPSHOT_UNSUPPORTED')
    expect(originAnalyticsSrc).not.toMatch(/origin[^"']*vs[^"']*origin|week \d.*vs.*week \d/i)
  })
})

describe('GEO-ANALYSIS-02-PAGE-10: evidence-availability panel is honest (Section 30-34)', () => {
  it('model evaluation renders an intentional unavailable state, never a fake accuracy card', () => {
    expect(evidenceSrc).toContain('LABEL_MODEL_EVALUATION_NOT_AVAILABLE')
    expect(evidenceSrc.toLowerCase()).not.toMatch(/\baccuracy\b|\bmae\b|\brmse\b|\bprecision\b|\brecall\b|\bf1\b|\bauc\b/)
  })

  it('confidence renders unavailable, no gauge/progress-bar element implied', () => {
    expect(evidenceSrc).toContain('LABEL_CONFIDENCE_NOT_AVAILABLE')
    expect(evidenceSrc).not.toMatch(/progress|gauge|<circle/i)
  })

  it('driver decomposition unavailable, no percentages rendered', () => {
    expect(evidenceSrc).toContain('LABEL_DRIVERS_NOT_AVAILABLE')
    expect(evidenceSrc).not.toMatch(/rainfall|humidity|wind\s*\d/i)
  })

  it('model-run comparison unavailable, no "Run A"/"Run B"/improvement wording', () => {
    expect(evidenceSrc).toContain('LABEL_MODEL_RUN_COMPARISON_NOT_AVAILABLE')
    expect(evidenceSrc.toLowerCase()).not.toMatch(/run a|run b|improved by/)
  })
})

describe('GEO-ANALYSIS-02-PAGE-11: FMD partial-availability UI (Section 13/35)', () => {
  it('FMD historical analytics remain visible -- summary panel is disease-agnostic, no FMD-specific hiding', () => {
    expect(summarySrc).not.toMatch(/selectedDisease\s*===\s*['"]FMD['"]/)
  })

  it('a distinct model-not-ready statement exists, never a hidden/blank page', () => {
    expect(evidenceSrc).toContain('LABEL_MODEL_EVALUATION_MODEL_NOT_READY')
    expect(originAnalyticsSrc).toContain('LABEL_MODEL_NOT_READY_FOR_DISEASE')
  })

  it('FMD path never substitutes LSD scientific values', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/disease\s*===\s*['"]FMD['"][^;]*(apparent_rate_km_day|nominal_reach_km)\s*=\s*[\d.]/)
    }
  })
})

describe('GEO-ANALYSIS-02-PAGE-12: host-composition / failure states (Section 6/48)', () => {
  it('a HOST_COMPOSITION_REQUIRED state is mapped to a polished label, never left as a raw error', () => {
    expect(pageSrc).toContain('LABEL_ANALYSIS_TRENDS_HOST_NOT_CONNECTED')
  })

  it('the service-not-connected state never renders fabricated sample counts/trend', () => {
    expect(pageSrc).not.toMatch(/mock|sample.*data|fake.*chart|demo.*chart/i)
  })

  it('every failure state maps through the same ERROR_LABEL lookup, never a raw exception message', () => {
    expect(pageSrc).toContain('ERROR_LABEL_BY_FETCH_STATUS[analysisTrends.errorStatus]')
  })
})

describe('GEO-ANALYSIS-02-PAGE-13: request race / abort safety (Section 37)', () => {
  it('useAnalysisTrends uses AbortController', () => {
    expect(hookSrc).toContain('new AbortController()')
    expect(hookSrc).toContain('controller.abort()')
  })

  it('a monotonic request-id guard rejects a stale response', () => {
    expect(hookSrc).toMatch(/requestIdRef\.current\s*!==\s*requestId/)
  })

  it('the effect dependency array includes both disease and originId, so either change starts a fresh request', () => {
    expect(hookSrc).toMatch(/\[disease, originId, retryToken\]/)
  })
})

describe('GEO-ANALYSIS-02-PAGE-14: no polling (Section 38)', () => {
  it('no setInterval/setTimeout anywhere in the new files', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/setInterval\(|setTimeout\(/)
    }
  })

  it('no LIVE/real-time wording describing the fetch (a "not live" disclaimer is fine, an affirmative "LIVE"/"real-time" claim is not)', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/\bLIVE\b/) // case-sensitive: a capitalized status-label-style "LIVE" would be the real risk
      expect(src.toLowerCase()).not.toMatch(/(?<!not )real-time/)
    }
  })
})

describe('GEO-ANALYSIS-02-PAGE-15: shared selected-origin state reuse (Section 39)', () => {
  it('reuses ctx.selectOutbreak rather than inventing a second global origin-selection concept', () => {
    expect(pageSrc).toContain('ctx.selectOutbreak(originId)')
    expect(pageSrc).not.toMatch(/analysisSelectedOriginId/)
  })
})

describe('GEO-ANALYSIS-02-PAGE-16: not globally mounted yet (Section 3/57)', () => {
  it('App.jsx is never referenced by the new files', () => {
    for (const src of ALL_NEW_FILES) {
      expect(src).not.toMatch(/App\.jsx|from ['"]\.\.\/\.\.\/App['"]/)
    }
  })
})
