import { describe, expect, it, vi } from 'vitest'

import {
  ANALYSIS_BASIS,
  buildAnalysisBasisOptions,
  buildReachHistory,
  buildRiskCells,
  buildSpatialStory,
  cellFootprint,
  cellTierCounts,
  isWithinWindowEndingAt,
  latestHistoricalOriginDate,
  latestVerifiedDate,
  reachSeries,
  selectedBasisOption,
  unavailableReason,
} from '../adapters/spatialStory'
import { STAGE_LAYER, applyStageVisibility } from '../components/stageLayers'
import { buildNationalCaseView, caseDate } from '../adapters/nationalCases'
import { ALL_RECORDED_WINDOW, LATEST_REPORTS_WINDOW, resolveObservationWindow } from '../adapters/observationWindow'
import { ANALYSIS_MODE } from '../context/outbreakSelectionReducer'

const square = (x, y, d = 0.1) => ({ type: 'Polygon', coordinates: [[[x, y], [x + d, y], [x + d, y + d], [x, y + d], [x, y]]] })

function frame(day, { reach = null, zones = [], envelope = null, districts = [] } = {}) {
  return {
    day,
    date: `2026-09-${String(15 + day).padStart(2, '0')}`,
    horizon_status: day === 0 ? 'AS_OF_OBSERVED_CONTEXT' : day <= 7 ? 'WITHIN_D1_D7_REACH_HORIZON' : 'EXPLORATORY_BEYOND_D7_REACH_HORIZON',
    active_source_ids: ['S1'],
    reach: reach == null ? null : { nominal_reach_km: reach, interval_km: [reach * 0.9, reach * 1.1], rate_km_day: 3.9 },
    reach_envelope: envelope,
    reach_limited_risk_zones: { type: 'FeatureCollection', features: zones },
    source_corridors: [],
    district_summaries: districts,
  }
}

const zone = (tier, geometry) => ({ type: 'Feature', geometry, properties: { tier } })

const TIMELINE = {
  status: 'OK',
  as_of: '2026-09-15',
  time_window: { source_window_start: '2026-09-01', source_window_end: '2026-09-15' },
  sources: [{ source_id: 'S1', record_domain: 'OPERATIONAL', latitude: 7.0, longitude: 80.0, observation_date: '2026-09-15', member_record_ids: ['case-1'] }],
  source_directions: [{ source_id: 'S1', bearing_deg: 216.8, directional_clarity: 0.92 }],
  risk_zones: { type: 'FeatureCollection', features: [zone('highest', square(80, 7)), zone('lower', square(80.2, 7))] },
  cells: [
    { cell_id: 'C-near', centroid: { longitude: 80.02, latitude: 7.02 }, raw_c0_score: 1.6, score_status: 'SCORED', tier: 'highest', in_scope: true, direction: { bearing_deg: 90 } },
    { cell_id: 'C-east', centroid: { longitude: 80.07, latitude: 7.02 }, raw_c0_score: 0.4, score_status: 'SCORED', tier: 'lower', in_scope: true },
    { cell_id: 'C-unscored', centroid: { longitude: 80.03, latitude: 7.03 }, raw_c0_score: null, score_status: 'UNSCORED', tier: null, in_scope: true },
  ],
  district_summaries: [{ district: 'Kegalle', scored_area_km2: 40, max_tier: 'highest', n_sources_in_district: 1 }],
  environment: { status: 'NOT_INTEGRATED', reason: 'No evaluated environmental model.', candidate_variables: [] },
  limitations: ['RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY'],
  frames: [
    frame(0),
    frame(1, { reach: 3.9, envelope: square(80, 7, 0.05), zones: [zone('highest', square(80, 7, 0.05))], districts: [{ district: 'Kegalle', area_within_reach_km2: 12, highest_tier_within_reach: 'highest' }] }),
    frame(2, { reach: 7.8, envelope: square(80, 7, 0.08), zones: [zone('lower', square(80.2, 7)), zone('highest', square(80, 7))], districts: [{ district: 'Kegalle', area_within_reach_km2: 30, highest_tier_within_reach: 'highest' }, { district: 'Colombo', area_within_reach_km2: 5, highest_tier_within_reach: 'lower' }] }),
  ],
}

describe('analysis basis (as-of date) options', () => {
  it('offers only options backed by a real date, live always first', () => {
    expect(buildAnalysisBasisOptions().map((o) => o.id)).toEqual([ANALYSIS_BASIS.LIVE])
    const options = buildAnalysisBasisOptions({ latestVerified: '2026-09-15', retrospective: '2020-10-10' })
    expect(options.map((o) => [o.id, o.asOf])).toEqual([
      [ANALYSIS_BASIS.LIVE, null],
      [ANALYSIS_BASIS.LATEST_VERIFIED, '2026-09-15'],
      [ANALYSIS_BASIS.RETROSPECTIVE, '2020-10-10'],
    ])
    expect(options[2].label).toBe('Retrospective · 10 Oct 2020')
    expect(options[2].description).toMatch(/Not current activity/)
    // A basis that is no longer available falls back to live.
    expect(selectedBasisOption(buildAnalysisBasisOptions(), ANALYSIS_BASIS.RETROSPECTIVE).id).toBe(ANALYSIS_BASIS.LIVE)
  })

  it('derives dates from real verified contexts / origins only', () => {
    const contexts = [
      { disease: 'LSD', verificationTime: '2026-08-24T10:00:00Z' },
      { disease: 'LSD', verificationTime: '2026-09-15T02:00:00+05:30' },
      { disease: 'FMD', verificationTime: '2026-10-01T00:00:00Z' },
      { disease: 'LSD', verificationTime: null },
    ]
    expect(latestVerifiedDate(contexts, 'LSD')).toBe('2026-09-15')
    expect(latestVerifiedDate([], 'LSD')).toBeNull()
    expect(latestHistoricalOriginDate([{ t0: '2020-09-07' }, { t0: '2020-10-10' }])).toBe('2020-10-10')
  })
})

describe('risk cells are the backend scored cells at their true footprint', () => {
  it('draws only SCORED cells; the source cell from Day 0, others as that day reach covers them', () => {
    // Day 0: only the cell holding the real source case (the current situation).
    expect(buildRiskCells(TIMELINE, 0).features.map((f) => [f.properties.cellId, f.properties.inReach, f.properties.isSourceCell])).toEqual([['C-near', false, true]])
    const day1 = buildRiskCells(TIMELINE, 1)
    expect(Object.fromEntries(day1.features.map((f) => [f.properties.cellId, f.properties.inReach]))).toEqual({ 'C-near': true })
    const day2 = buildRiskCells(TIMELINE, 2)
    expect(Object.fromEntries(day2.features.map((f) => [f.properties.cellId, f.properties.inReach]))).toEqual({ 'C-near': true, 'C-east': true })
    expect(day2.features.find((f) => f.properties.cellId === 'C-near').properties).toMatchObject({ tier: 'highest', tierLabel: 'Highest relative', riskLevel: 'red', score: 1.6, day: 2 })
    expect(cellTierCounts(day1)).toEqual({ highest: 1, high: 0, moderate: 0, lower: 0, scored: 1 })
  })

  it('a cell footprint is 5 km on each side around the backend centroid', () => {
    const [ring] = cellFootprint(80, 7).coordinates
    const kmLat = (ring[2][1] - ring[0][1]) * 110.574
    const kmLon = (ring[1][0] - ring[0][0]) * 111.32 * Math.cos((7 * Math.PI) / 180)
    expect(kmLat).toBeCloseTo(5, 6)
    expect(kmLon).toBeCloseTo(5, 6)
  })

  it('reach history holds one envelope per elapsed day, aged from the selected day', () => {
    const history = buildReachHistory(TIMELINE, 2)
    expect(history.features.map((f) => [f.properties.day, f.properties.age, f.properties.isCurrent])).toEqual([[1, 1, false], [2, 0, true]])
    expect(buildReachHistory(TIMELINE, 0).features).toEqual([])
    expect(reachSeries(TIMELINE).map((r) => r.reachKm)).toEqual([0, 3.9, 7.8])
  })

  it('draws nothing for a snapshot the backend did not compute', () => {
    const empty = { status: 'NO_ELIGIBLE_SOURCES', frames: [], cells: TIMELINE.cells }
    expect(buildRiskCells(empty, 0).features).toEqual([])
    expect(buildReachHistory(empty, 3).features).toEqual([])
    expect(buildSpatialStory(empty, 0).renderable).toBe(false)
  })
})

describe('observation window ending at the analysis date', () => {
  it('includes the N days up to the date and EXCLUDES anything verified later', () => {
    expect(isWithinWindowEndingAt('2026-09-15T08:00:00Z', 14, '2026-09-15')).toBe(true)
    expect(isWithinWindowEndingAt('2026-09-02T08:00:00Z', 14, '2026-09-15')).toBe(true)
    expect(isWithinWindowEndingAt('2026-08-29T08:00:00Z', 14, '2026-09-15')).toBe(false)
    expect(isWithinWindowEndingAt('2026-09-16T01:00:00Z', 14, '2026-09-15')).toBe(false)
    expect(isWithinWindowEndingAt(null, 14, '2026-09-15')).toBe(false)
  })
})

describe('situation brief', () => {
  it('reads the selected frame and the vet district straight from backend summaries', () => {
    const story = buildSpatialStory(TIMELINE, 2, { vetDistrict: 'Kegalle District' })
    expect(story).toMatchObject({ day: 2, reachKm: 7.8, exploratory: false })
    expect(story.domainCounts).toEqual({ operational: 1, historical: 0 })
    expect(story.sources[0]).toMatchObject({ compass: 'SW', bearingDeg: 216.8 })
    expect(story.districtsInReach.map((d) => d.district)).toEqual(['Kegalle', 'Colombo'])
    expect(story.topConcern).toMatchObject({ district: 'Kegalle', tier: 'highest' })
    expect(story.myDistrict).toMatchObject({ name: 'Kegalle', tierWithinReach: 'highest', areaWithinReachKm2: 30 })
    expect(story.attention.level).toBe('PRIORITISE')
    expect(story.attention.detail).toMatch(/not an infection forecast/)
  })

  it('a district with scored area beyond reach is told to step forward, not alarmed', () => {
    const story = buildSpatialStory(TIMELINE, 0, { vetDistrict: 'Kegalle' })
    expect(story.attention.level).toBe('MONITOR')
    expect(story.attention.headline).toMatch(/beyond Day 0 nominal reach/)
    const elsewhere = buildSpatialStory(TIMELINE, 2, { vetDistrict: 'Matara' })
    expect(elsewhere.attention.level).toBe('ROUTINE')
  })

  it('explains empty and model-not-ready snapshots in plain language', () => {
    const none = unavailableReason({ status: 'NO_ELIGIBLE_SOURCES', time_window: TIMELINE.time_window, source_exclusions: { 'operational:OUTSIDE_ACTIVE_SOURCE_WINDOW': 8, 'operational:WRONG_DISEASE': 5 } }, { diseaseShortLabel: 'LSD' })
    expect(none.title).toBe('No eligible LSD source cases in the last 14 days')
    expect(none.body).toMatch(/8 verified before the 14-day window/)
    expect(none.reasons).toEqual(['8 verified before the 14-day window']) // other diagnoses are not a reason a source is missing
    const gps = unavailableReason({ status: 'NO_ELIGIBLE_SOURCES', source_exclusions: { 'operational:MISSING_OR_INVALID_COORDINATES': 3, 'operational:NOT_VET_VERIFIED': 1 } }, { diseaseShortLabel: 'LSD' })
    expect(gps.reasons).toEqual(['3 reports have no farm GPS (set the farm location in ADRS to map them)', '1 awaiting vet verification'])
    expect(none.canSwitchBasis).toBe(true)
    const fmd = unavailableReason({ status: 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY' }, { diseaseShortLabel: 'FMD' })
    expect(fmd.canSwitchBasis).toBe(false)
    expect(fmd.body).toMatch(/no frozen spatial kernel/)
  })
})

describe('national case surveillance view', () => {
  const records = [
    { record_key: 'CASE:a', disease: 'LSD', verification_status: 'VERIFIED', verified_at: '2026-08-30T06:00:00+00:00', reported_at: '2026-08-29T10:00:00', location_status: 'VALID', latitude: 5.95, longitude: 80.55, district: 'Matara' },
    { record_key: 'CASE:b', disease: 'LSD', verification_status: 'PENDING_VERIFICATION', verified_at: null, reported_at: '2026-09-20T10:00:00', location_status: 'VALID', latitude: 6.9, longitude: 79.86, district: 'Colombo' },
    { record_key: 'CASE:c', disease: 'LSD', verification_status: 'VERIFIED', verified_at: '2026-09-15T00:00:00+00:00', reported_at: '2026-09-14T00:00:00', location_status: 'LOCATION_REQUIRED', latitude: null, longitude: null },
    { record_key: 'CASE:d', disease: 'FMD', verification_status: 'VERIFIED', verified_at: '2026-09-01T00:00:00+00:00', location_status: 'VALID', latitude: 7.3, longitude: 81.6 },
  ]
  const matara = { type: 'Feature', geometry: square(80.2, 5.8, 0.6) }

  it('keeps verified and pending apart, never places a record without GPS, and counts district cases', () => {
    const view = buildNationalCaseView(records, { disease: 'LSD', windowDays: ALL_RECORDED_WINDOW, districtFeature: matara, ageReferenceDateKey: '2026-09-20' })
    expect(view.counts).toMatchObject({ inWindow: 3, verified: 2, pending: 1, withoutGps: 1, inDistrictVerified: 1, inDistrictPending: 0, mappedVerified: 1, mappedPending: 1 })
    expect(view.featureCollection.features.map((f) => [f.properties.recordKey, f.properties.verified, f.properties.inDistrict])).toEqual([
      ['CASE:b', false, false],
      ['CASE:a', true, true],
    ])
  })

  it('windows end at the analysis date when one is chosen; "Latest reports" = 14 days to the latest record', () => {
    expect(buildNationalCaseView(records, { disease: 'LSD', windowDays: 14, endIsoDate: '2026-09-01' }).counts.inWindow).toBe(1)
    expect(resolveObservationWindow(LATEST_REPORTS_WINDOW, { latestRecordDate: '2026-09-20' })).toEqual({ days: 14, endIsoDate: '2026-09-20' })
    expect(resolveObservationWindow(30, { basisAsOf: '2026-08-30' })).toEqual({ days: 30, endIsoDate: '2026-08-30' })
    expect(caseDate(records[1])).toBe('2026-09-20T10:00:00')
  })
})

describe('stage-layer visibility is decided per mode only', () => {
  function fakeMap() {
    const visibility = {}
    return {
      visibility,
      style: {},
      getLayer: () => true,
      setLayoutProperty: vi.fn((id, prop, value) => {
        visibility[id] = value
      }),
    }
  }

  it('each mode shows only its own overlays', () => {
    const map = fakeMap()
    applyStageVisibility(map, ANALYSIS_MODE.RISK_ZONES)
    expect(map.visibility[STAGE_LAYER.CELL_FILL_A]).toBe('visible')
    expect(map.visibility[STAGE_LAYER.HISTORY_LINE]).toBe('none')
    // Observed cases stay visible over model output; the district halo does not.
    expect(map.visibility[STAGE_LAYER.NATIONAL_CASE]).toBe('visible')
    expect(map.visibility[STAGE_LAYER.NATIONAL_CASE_HALO]).toBe('none')

    applyStageVisibility(map, ANALYSIS_MODE.TRAJECTORY)
    // Paths only: no large reach rings around them in Trajectory.
    expect(map.visibility[STAGE_LAYER.HISTORY_LINE]).toBe('none')
    expect(map.visibility[STAGE_LAYER.CURRENT_FILL]).toBe('none')
    expect(map.visibility[STAGE_LAYER.CELL_FILL_A]).toBe('none')
    expect(map.visibility[STAGE_LAYER.TRAJECTORY_FLOW]).toBe('visible')
    expect(map.visibility[STAGE_LAYER.NATIONAL_CASE_PULSE]).toBe('visible')
    expect(map.visibility[STAGE_LAYER.NATIONAL_CASE]).toBe('visible')

    applyStageVisibility(map, ANALYSIS_MODE.CASES)
    expect(map.visibility[STAGE_LAYER.NATIONAL_CASE]).toBe('visible')
    expect(map.visibility[STAGE_LAYER.CELL_FILL_A]).toBe('none')

    // Clusters: only the exploratory ST-DBSCAN layers (hull, members, noise).
    applyStageVisibility(map, ANALYSIS_MODE.CLUSTERS)
    const clusterLayers = [STAGE_LAYER.CLUSTER_HULL, STAGE_LAYER.CLUSTER_MEMBER, STAGE_LAYER.CLUSTER_NOISE]
    expect(Object.values(STAGE_LAYER).every((id) => map.visibility[id] === (clusterLayers.includes(id) ? 'visible' : 'none'))).toBe(true)

    // Env: the real ERA5 rain/wind/value layers plus the observed cases.
    applyStageVisibility(map, ANALYSIS_MODE.ENV)
    const envLayers = [STAGE_LAYER.ENV_AREA, STAGE_LAYER.ENV_HEAT, STAGE_LAYER.ENV_HEAT_SHIMMER, STAGE_LAYER.ENV_RAIN, STAGE_LAYER.ENV_RAIN_RIPPLE, STAGE_LAYER.ENV_WIND, STAGE_LAYER.ENV_WIND_FLOW, STAGE_LAYER.ENV_LABEL, STAGE_LAYER.NATIONAL_CASE_PULSE, STAGE_LAYER.NATIONAL_CASE]
    expect(Object.values(STAGE_LAYER).every((id) => map.visibility[id] === (envLayers.includes(id) ? 'visible' : 'none'))).toBe(true)

    applyStageVisibility(map, null)
    expect(Object.values(STAGE_LAYER).every((id) => map.visibility[id] === 'none')).toBe(true)
  })
})
