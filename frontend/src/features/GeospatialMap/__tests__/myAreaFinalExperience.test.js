import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const page = readFileSync(join(ROOT, 'pages', 'MyAreaPage.jsx'), 'utf8')
const map = readFileSync(join(ROOT, 'components', 'MyAreaMapCanvas.jsx'), 'utf8')
const outlook = readFileSync(join(ROOT, 'components', 'MyAreaTemporalOutlook.jsx'), 'utf8')
const intelligence = readFileSync(join(ROOT, 'components', 'MyAreaIntelligencePanel.jsx'), 'utf8')
const influencing = readFileSync(join(ROOT, 'components', 'MyAreaOutbreaksInfluencing.jsx'), 'utf8')

describe('My Area final synchronized presentation experience', () => {
  it('uses one canonical activeAreaForecastIndex everywhere that changes by date', () => {
    expect(page).toContain('const [activeAreaForecastIndex, setActiveAreaForecastIndex] = useState(0)')
    expect(page).toContain('buildMyAreaPresentationForecast(areaCaseFeatures, activeAreaForecastIndex, districtFeature)')
    expect(page.match(/activeIndex=\{activeAreaForecastIndex\}/g)).toHaveLength(3)
    expect(outlook).toContain('index === activeIndex')
    expect(intelligence).toContain('activeIndex + 1')
  })

  it('keeps the backend request fixed at day zero and advances frames locally with one RAF clock', () => {
    expect(page).toContain('originId: null')
    expect(page).toContain('day: 0')
    expect(page).not.toContain('day: activeAreaForecastIndex')
    expect(page).toContain('requestAnimationFrame(tick)')
  })

  it('creates one MapLibre instance and updates persistent GeoJSON sources', () => {
    expect(map.split('new maplibregl.Map(').length - 1).toBe(1)
    expect(map.split('fitBounds(').length - 1).toBe(1)
    expect(map).toContain('getSource(AREA_FORECAST_RISK_SOURCE_ID)?.setData')
    expect(map).toContain('getSource(AREA_FORECAST_PATH_SOURCE_ID)?.setData')
    expect(map).toContain('getSource(AREA_FORECAST_FRONT_SOURCE_ID)?.setData')
  })

  it('keeps confirmed observed cases in their own fixed red source', () => {
    expect(map).toContain("const OBSERVED_CASES_SOURCE_ID = 'geo-my-area-observed-cases'")
    expect(map).toContain("'circle-color': '#EF4444'")
    const observedEffect = map.slice(map.indexOf('Verified observations never depend'), map.indexOf('The one Page-2 forecast snapshot'))
    expect(observedEffect).not.toContain('areaForecastVisualization')
  })

  it('fits the real Matara district even when farm details are temporarily unavailable', () => {
    expect(page).toContain("MY_AREA_DEMO_DISTRICT_OVERRIDE = 'Matara'")
    expect(map).toContain("`${area?.farmId ?? 'district'}::${districtIdentity}`")
    expect(map).toContain('computeFeatureBounds(districtFeature)')
  })

  it('View on Map emphasizes one real case without filtering out the others or changing the date', () => {
    expect(influencing).toContain('onFocusCase(influence.anchorId)')
    expect(page).toContain('onFocusCase={setFocusedCaseId}')
    expect(map).toContain('my-area-forecast-selected-path')
    expect(map).toContain('my-area-observed-cases-selected')
    expect(map).toContain('map.easeTo')
  })

  it('uses Matara actual dates and consistent qualitative risk semantics in chart and panel', () => {
    expect(outlook).toContain('Future Risk Outlook — {areaLabel}')
    expect(outlook).toContain('Qualitative presentation outlook - no probability')
    expect(outlook).not.toMatch(/D\+\d/)
    expect(intelligence).toContain('districtRisk?.toUpperCase()')
  })

  it('does not duplicate the host shell or create fake future confirmed outbreaks', () => {
    expect(page).not.toContain('VetLayout')
    expect(page).not.toContain('TopHeader')
    expect(page).not.toContain('predictedHotspots')
    expect(page).not.toContain('Math.random')
    expect(page).toContain('not confirmed future cases')
  })

  it('never resets activeAreaForecastIndex from map-mode toggling or case-focus selection', () => {
    expect(page).toContain('setMapMode(MAP_MODE.FUTURE_IMPACT)')
    expect(page).toContain('setFocusedCaseId(null)')
    // setMapMode/setFocusedCaseId are always standalone state updates -- neither
    // call site is ever paired with setActiveAreaForecastIndex on the same line.
    expect(page).not.toMatch(/setMapMode\([^)]*\)[^\n]*setActiveAreaForecastIndex/)
    expect(page).not.toMatch(/setFocusedCaseId\([^)]*\)[^\n]*setActiveAreaForecastIndex/)
    expect(page.match(/onClick=\{\(\) => setMapMode\(MAP_MODE\.\w+\)\}/g)).toHaveLength(2)
  })

  it('removed the large full-width presentation banner and keeps only a small legend tooltip instead', () => {
    expect(page).not.toContain('Frontend presentation visualization only. Purple projections and qualitative risk contours are not confirmed future cases, medical probabilities, or backend model outputs.')
    expect(page).toContain('PRESENTATION_DISCLAIMER_TEXT')
    expect(page).toContain('title={PRESENTATION_DISCLAIMER_TEXT}')
  })
})
