/**
 * Real (trimmed) responses captured 2026-08-27 from the running backend:
 * `GET /api/geospatial/origins?disease=lsd&country=Sri%20Lanka` and
 * `GET /api/geospatial/analysis/ORIGIN:Sri%20Lanka:2020-09-28/{summary,sources,cells}`.
 * Not fabricated -- copied verbatim (cells truncated from 117 to 2
 * features to keep this fixture small; everything else is the real
 * response). Used to keep the adapter tests honest against the real
 * contract instead of an invented shape.
 */

export const REAL_ORIGINS_RESPONSE = {
  origins: [
    { forecast_origin_id: 'ORIGIN:Sri Lanka:2020-09-07', country: 'Sri Lanka', t0: '2020-09-07', trigger_source_count: 1 },
    { forecast_origin_id: 'ORIGIN:Sri Lanka:2020-09-09', country: 'Sri Lanka', t0: '2020-09-09', trigger_source_count: 1 },
    { forecast_origin_id: 'ORIGIN:Sri Lanka:2020-09-28', country: 'Sri Lanka', t0: '2020-09-28', trigger_source_count: 2 },
    { forecast_origin_id: 'ORIGIN:Sri Lanka:2020-09-29', country: 'Sri Lanka', t0: '2020-09-29', trigger_source_count: 1 },
    { forecast_origin_id: 'ORIGIN:Sri Lanka:2020-10-28', country: 'Sri Lanka', t0: '2020-10-28', trigger_source_count: 1 },
  ],
  n_origins: 5,
}

export const REAL_SUMMARY_20200928 = {
  analysis_metadata: {
    forecast_origin_id: 'ORIGIN:Sri Lanka:2020-09-28',
    country: 'Sri Lanka',
    t0: '2020-09-28',
    disease: 'Lumpy skin disease',
    status: 'ANALYZED',
    runtime_data_mode: 'HISTORICAL_RETROSPECTIVE_REPLAY',
  },
  n_eligible_sources: 2,
  apparent_rate_context: {
    apparent_rate_km_day: 3.946421443154751,
    rate_interval_lower_km_day: 3.5491046170907765,
    rate_interval_upper_km_day: 4.343077329563724,
  },
  nominal_reach_by_day: [
    { day: 1, nominal_reach_km: 3.946421443154751, derived_interval_lower_km: 3.5491046170907765, derived_interval_upper_km: 4.343077329563724 },
    { day: 2, nominal_reach_km: 7.892842886309502, derived_interval_lower_km: 7.098209234181553, derived_interval_upper_km: 8.686154659127448 },
    { day: 3, nominal_reach_km: 11.839264329464253, derived_interval_lower_km: 10.64731385127233, derived_interval_upper_km: 13.029231988691173 },
    { day: 4, nominal_reach_km: 15.785685772619004, derived_interval_lower_km: 14.196418468363106, derived_interval_upper_km: 17.372309318254896 },
    { day: 5, nominal_reach_km: 19.732107215773755, derived_interval_lower_km: 17.745523085453883, derived_interval_upper_km: 21.71538664781862 },
    { day: 6, nominal_reach_km: 23.678528658928506, derived_interval_lower_km: 21.29462770254466, derived_interval_upper_km: 26.058463977382345 },
    { day: 7, nominal_reach_km: 27.624950102083258, derived_interval_lower_km: 24.843732319635436, derived_interval_upper_km: 30.40154130694607 },
  ],
  nominal_reach_semantics: 'VISUALIZATION_ONLY_NOT_HARD_DISEASE_BOUNDARY',
  snapshot_id: '8b523733c7504ab5b0e09a492436ca37e17990d3f8a0688d4069b76bc9a807a7',
  generated_at_utc: '2026-08-27T15:49:07.362221+00:00',
}

export const REAL_SOURCES_20200928 = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [80.0290277, 9.6734908] },
      properties: { source_id: 'WAHIS_PDF:Event_3473.pdf:002409', availability_quality: 'EVENT_DATE_PROXY', gps_quality: 'EXACT' },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [80.08333, 9.75] },
      properties: { source_id: 'WAHIS_PDF:Event_3473.pdf:002410', availability_quality: 'EVENT_DATE_PROXY', gps_quality: 'EXACT' },
    },
  ],
}

// Real cells response had 117 features; trimmed to 2 here (verbatim
// content, just fewer of them) to keep the fixture readable.
export const REAL_CELLS_20200928 = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [80.09780348313204, 9.515413096040023] },
      properties: {
        scientific_cell_id: 'SCICELL:03d6094dcb1fc97d81333492',
        risk: { raw_c0_score: 0.8203567247362947, score_status: 'SCORED', semantics: 'RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY' },
        direction: { bearing_deg: 165.19004212579355, directional_clarity: 0.9853269036184936, direction_status: 'DIRECTION_AVAILABLE' },
      },
    },
  ],
}

// A rough Jaffna-district-ish polygon ring, used only to exercise the
// relevance-computation geometry in tests -- not a real administrative
// boundary (that's the Section D/N "new static asset" work item).
export const FIXTURE_AREA_RING_NEAR_JAFFNA = [
  [79.9, 9.5],
  [80.2, 9.5],
  [80.2, 9.8],
  [79.9, 9.8],
  [79.9, 9.5],
]

export const FIXTURE_AREA_RING_FAR_AWAY_KANDY = [
  [80.5, 7.1],
  [80.7, 7.1],
  [80.7, 7.3],
  [80.5, 7.3],
  [80.5, 7.1],
]
