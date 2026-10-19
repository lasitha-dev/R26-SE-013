import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const page = readFileSync(join(ROOT, 'pages', 'MyAreaPage.jsx'), 'utf8')
const map = readFileSync(join(ROOT, 'components', 'MyAreaMapCanvas.jsx'), 'utf8')
const chart = readFileSync(join(ROOT, 'components', 'MyAreaTemporalOutlook.jsx'), 'utf8')
const cards = readFileSync(join(ROOT, 'components', 'MyAreaOutbreaksInfluencing.jsx'), 'utf8')

describe('Page-2 synchronized vet-district presentation wiring', () => {
  it('uses one activeAreaForecastIndex over ONE backend snapshot for map, timeline, chart and intelligence', () => {
    expect(page).toContain('const [activeAreaForecastIndex, setActiveAreaForecastIndex] = useState(0)')
    expect(page).toContain("useSpatialTimeline({")
    expect(page).toContain("scope: 'district',")
    expect(page).toContain('buildMyAreaTimelineView(spatialTimeline.data, activeAreaForecastIndex, authorizedDistrict, { landDomain: districtFeature ?? null })')
    expect(page).toContain('activeIndex={activeAreaForecastIndex}')
    expect(page.match(/activeIndex=\{activeAreaForecastIndex\}/g)).toHaveLength(2) // model strip + Future Risk Outlook
  })

  it("sources real case identities/coordinates from the current operational collection and the vet's district polygon", () => {
    expect(page).toContain('collectMyAreaCaseContexts({')
    expect(page).toContain('buildObservedCaseFeatures(candidateCaseContexts)')
    expect(page).toContain('scopePointFeaturesToDistrict')
    expect(page).not.toMatch(/caseId:\s*['"][^'"]+['"]/)
    expect(page).not.toMatch(/coordinates:\s*\[\s*\d/)
  })

  it('View on Map changes only focusedCaseId and never changes the master date', () => {
    expect(page).toContain('onFocusCase={setFocusedCaseId}')
    const handler = map.slice(map.indexOf('View on Map changes only'), map.indexOf('nominal-reach ring:'))
    expect(handler).toContain('emphasizeCoordinate(map, coordinate, reduceMotion)')
    expect(handler).not.toContain('setActiveAreaForecastIndex')
  })

  it('updates persistent risk/path/front sources with setData and does not recreate the map per tick', () => {
    expect(map.split('new maplibregl.Map(')).toHaveLength(2)
    expect(map).toContain("const AREA_FORECAST_RISK_SOURCE_ID = 'geo-my-area-forecast-risk'")
    expect(map).toContain("const AREA_FORECAST_PATH_SOURCE_ID = 'geo-my-area-forecast-paths'")
    expect(map).toContain("const AREA_FORECAST_FRONT_SOURCE_ID = 'geo-my-area-forecast-fronts'")
    // Phase 4: reach-limited zones go through the double-buffered cross-fader
    // (exact backend polygons, opacity only); corridors through the reveal.
    expect(map).toContain('riskFaderRef.current?.show(areaForecastVisualization?.riskZones')
    expect(map).toContain('const pathSource = map.getSource(AREA_FORECAST_PATH_SOURCE_ID)')
    expect(map).toContain('const frontSource = map.getSource(AREA_FORECAST_FRONT_SOURCE_ID)')
    expect(map).toContain('pathSource?.setData(paths)')
    expect(map).toContain('frontSource?.setData(fronts)')
  })

  it('maps every riskLevel to an explicit non-black MapLibre color in green-to-red layer order', () => {
    expect(map).toContain("const AREA_RISK_LEVELS = ['green', 'yellow', 'orange', 'red']")
    expect(map).toContain('for (const riskLevel of AREA_RISK_LEVELS)')
    expect(map).toContain("filter: ['==', ['get', 'riskLevel'], riskLevel]")
    expect(map).toContain("'fill-color': color")
    expect(map).toContain("'line-color': color")
    expect(map).not.toContain("'fill-color': '#000")
  })

  it('renders the district Future Risk Outlook and active bar from the same controlled index', () => {
    expect(chart).toContain('Future Risk Outlook — {areaLabel}')
    expect(chart).toContain('const active = index === activeIndex')
    expect(chart).not.toMatch(/D\+\d/)
  })

  it('influencing cards are real identities with date-varying status and no placeholder IDs', () => {
    // Task 4: real case number (or one-way source key) and the card's
    // backend-derived kind and selected-day status.
    expect(cards).toContain('{sourceIdOf(influence)}')
    expect(cards).toContain("{card.kind ?? 'NO MODEL DATA'}")
    expect(cards).toContain('card.dayStatusText')
    expect(cards).not.toContain('FMD-024')
    expect(cards).not.toContain('FMD-031')
    expect(cards).not.toContain('Kegalle')
    expect(cards).not.toContain('Matale')
  })

  it('keeps all frame changes frontend-only', () => {
    const playback = page.slice(page.indexOf('One RAF clock'), page.indexOf('const national ='))
    expect(playback).toContain('requestAnimationFrame')
    expect(playback).not.toContain('fetch(')
    expect(playback).not.toContain('setRetryToken')
  })
})
