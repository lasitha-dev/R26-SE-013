import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const page = readFileSync(join(ROOT, 'pages', 'MyAreaPage.jsx'), 'utf8')
const map = readFileSync(join(ROOT, 'components', 'MyAreaMapCanvas.jsx'), 'utf8')
const chart = readFileSync(join(ROOT, 'components', 'MyAreaTemporalOutlook.jsx'), 'utf8')
const cards = readFileSync(join(ROOT, 'components', 'MyAreaOutbreaksInfluencing.jsx'), 'utf8')

describe('Page-2 synchronized Matara presentation wiring', () => {
  it('uses one activeAreaForecastIndex for generator, timeline, chart and intelligence', () => {
    expect(page).toContain('const [activeAreaForecastIndex, setActiveAreaForecastIndex] = useState(0)')
    expect(page).toContain('buildMyAreaPresentationForecast(areaCaseFeatures, activeAreaForecastIndex, districtFeature)')
    expect(page).toContain('activeIndex={activeAreaForecastIndex}')
    expect(page.match(/activeIndex=\{activeAreaForecastIndex\}/g)).toHaveLength(3)
  })

  it('sources real case identities/coordinates from the current operational collection and Matara polygon', () => {
    expect(page).toContain('operational.data?.surveillanceContexts')
    expect(page).toContain('buildObservedCaseFeatures(candidateCaseContexts)')
    expect(page).toContain('scopePointFeaturesToDistrict')
    expect(page).not.toMatch(/caseId:\s*['"][^'"]+['"]/) 
    expect(page).not.toMatch(/coordinates:\s*\[\s*\d/)
  })

  it('View on Map changes only focusedCaseId and never changes the master date', () => {
    expect(page).toContain('onFocusCase={setFocusedCaseId}')
    const handler = map.slice(map.indexOf('View on Map changes only'), map.indexOf('nominal-reach ring:'))
    expect(handler).toContain('map.easeTo')
    expect(handler).not.toContain('setActiveAreaForecastIndex')
  })

  it('updates persistent risk/path/front sources with setData and does not recreate the map per tick', () => {
    expect(map.split('new maplibregl.Map(')).toHaveLength(2)
    expect(map).toContain("const AREA_FORECAST_RISK_SOURCE_ID = 'geo-my-area-forecast-risk'")
    expect(map).toContain("const AREA_FORECAST_PATH_SOURCE_ID = 'geo-my-area-forecast-paths'")
    expect(map).toContain("const AREA_FORECAST_FRONT_SOURCE_ID = 'geo-my-area-forecast-fronts'")
    expect(map).toContain("getSource(AREA_FORECAST_RISK_SOURCE_ID)?.setData")
    expect(map).toContain("getSource(AREA_FORECAST_PATH_SOURCE_ID)?.setData")
    expect(map).toContain("getSource(AREA_FORECAST_FRONT_SOURCE_ID)?.setData")
  })

  it('maps every riskLevel to an explicit non-black MapLibre color in green-to-red layer order', () => {
    expect(map).toContain("for (const riskLevel of ['green', 'yellow', 'orange', 'red'])")
    expect(map).toContain("filter: ['==', ['get', 'riskLevel'], riskLevel]")
    expect(map).toContain("'fill-color': color")
    expect(map).toContain("'line-color': color")
    expect(map).not.toContain("'fill-color': '#000")
  })

  it('renders Matara Future Risk Outlook and active bar from the same controlled index', () => {
    expect(chart).toContain('Future Risk Outlook — {areaLabel}')
    expect(chart).toContain('const active = index === activeIndex')
    expect(chart).not.toMatch(/D\+\d/)
  })

  it('influencing cards are real identities with date-varying status and no placeholder IDs', () => {
    expect(cards).toContain('{influence.caseId}')
    expect(cards).toContain('{influence.status}')
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
