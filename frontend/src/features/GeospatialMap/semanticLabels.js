/**
 * Checkpoint 11A Part 6: centralized scientific-semantics wording
 * firewall.
 *
 * Every user-facing string describing a scientific field MUST be
 * imported from here, never inlined in a component. This lets a
 * single test file scan every exported string value for forbidden
 * wording without needing to render any component.
 */

export const LABEL_RISK_SCORE = 'Relative spatial risk score'
export const LABEL_RUNTIME_MODE = 'Historical retrospective replay'
export const LABEL_SOURCES = 'Eligible outbreak sources'
export const LABEL_DIRECTION = 'Local geometric tendency'
export const LABEL_CLARITY = 'Directional clarity'
export const LABEL_RATE = 'Estimated apparent local spread-front rate'
export const LABEL_REACH = 'Nominal reach — visualization only'

export const DISCLAIMER_RUNTIME_MODE =
  'Historical retrospective replay — live operational forecasting is not implemented.'

export const DISCLAIMER_RISK =
  'Relative spatial score; not infection probability.'

export const DISCLAIMER_DIRECTION =
  'Direction is a C0-derived local geometric tendency, not a predicted disease-spread direction.'

export const DISCLAIMER_CLARITY =
  'Directional clarity is not confidence.'

export const DISCLAIMER_RATE =
  'Rate is a frozen historical apparent spread-front estimate, not wind speed.'

export const DISCLAIMER_REACH =
  'Nominal reach is visualization only and is not a hard disease boundary.'

export const RATE_FIELD_LABEL = 'Estimated apparent local spread-front rate (km/day)'

export const GENERATED_AT_LABEL = 'Snapshot generated in this process'

export const INCOMPATIBLE_PROTOCOL_MESSAGE = 'Geospatial frontend/backend contract mismatch.'

export const NEAREST_SOURCE_DISCLAIMER =
  'Nearest eligible source is a geometric reference only, never a confirmed transmission origin.'

export const PRESENTATION_ONLY_COLOR_SCALE = 'PRESENTATION_ONLY_COLOR_SCALE'

/**
 * LSD-PAGE1-HARDENING: page-level product copy vs. the transport-status
 * chip (plan Section 9) are still different concepts, but both are now
 * held to the SAME honesty rule on this page -- the real transport is
 * `HISTORICAL_RETROSPECTIVE_REPLAY_SNAPSHOT_TRANSPORT`
 * (`runtime_data_mode`/`realtime_transport_status` from the real
 * `/api/geospatial/protocol` response, confirmed 2026-08-27), so neither
 * may visually imply true live operational surveillance. The tagline
 * previously kept "Live outbreak surveillance and spatial forecasting"
 * verbatim from the ADRS visual reference as product copy; the
 * LSD-PAGE1-HARDENING checkpoint corrects that because a vet reading
 * this page alongside a "Snapshot connected · historical replay" status
 * chip should never see a contradictory "Live" claim one line above it.
 * See `SnapshotStatusChip.jsx`, which uses ONLY the three labels below.
 */
export const PAGE_TITLE = 'Geospatial Disease Intelligence'
// GEO29A Part 9 asked for a punchier subtitle mentioning "live"
// surveillance. Deliberately NOT adopted verbatim: `semanticLabels.test.js`
// (LSD-PAGE1-HARDENING) locks this exact string AND asserts it never
// contains the word "Live" -- a prior checkpoint added that guard after
// the original reference copy ("Live outbreak surveillance and spatial
// forecasting") was found to imply live FORECASTING, which is false (the
// scientific/forecast layer is historical replay; only the separate
// verified-case SSE layer is genuinely live). Modernized to drop the
// "historical replay" jargon per Part 9's intent without reopening that
// fixed issue -- "live"-ness is still communicated, honestly, by
// `OperationalStatusChip`'s own real-time wording elsewhere on this page.
export const PAGE_TAGLINE = 'Verified-case surveillance and spatial intelligence'

export const LABEL_SNAPSHOT_CONNECTED = 'Snapshot connected'
export const LABEL_SNAPSHOT_LOADING = 'Loading snapshot…'
export const LABEL_SNAPSHOT_UNAVAILABLE = 'Snapshot unavailable'
export const ACTION_CHECK_FOR_NEWER_SNAPSHOT = 'Check for newer snapshot'

// Backend error-status -> user-safe message map (Part 12). Never a raw
// stack trace, file path, or SQL fragment.
export const ERROR_STATUS_MESSAGES = {
  ORIGIN_NOT_FOUND: 'This forecast origin does not exist.',
  ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE: 'No eligible sources were available for this origin at its date -- analysis unavailable.',
  ANALYSIS_UNAVAILABLE_SCIENTIFIC_DOMAIN: 'The scientific domain could not be constructed for this origin -- analysis unavailable.',
  ANALYSIS_UNAVAILABLE_GRID: 'The scientific grid could not be constructed for this origin -- analysis unavailable.',
  ANALYSIS_INTERNAL_ERROR: 'An unexpected backend error occurred. Please try again.',
  INVALID_MESSAGE: 'The request could not be understood by the backend.',
  UNSUPPORTED_MESSAGE_TYPE: 'The request type is not supported by the backend.',
  INVALID_FORECAST_ORIGIN_ID: 'The selected origin id is invalid.',
  MESSAGE_TOO_LARGE: 'The request was too large to send.',
  SNAPSHOT_CONTENT_INTEGRITY_MISMATCH: 'The backend could not verify the integrity of this snapshot. Please retry.',
  PROTOCOL_CHECK_FAILED: 'Could not reach the geospatial backend.',
  INCOMPATIBLE_BACKEND_PROTOCOL: INCOMPATIBLE_PROTOCOL_MESSAGE,
  MIXED_SNAPSHOT_ID: 'The backend sent inconsistent snapshot data. Please retry.',
  INVALID_CHUNK_INDEX: 'The backend sent an invalid data chunk. Please retry.',
  DUPLICATE_CHUNK_INDEX: 'The backend sent a duplicate data chunk. Please retry.',
  MISSING_CHUNK: 'The backend did not send all expected data. Please retry.',
  UNEXPECTED_CHUNK_COUNT: 'The backend sent an unexpected number of data chunks. Please retry.',
  CELL_COUNT_MISMATCH: 'The backend cell count did not match the expected count. Please retry.',
  SOURCE_COUNT_MISMATCH: 'The backend source count did not match the expected count. Please retry.',
  INCOMPLETE_SNAPSHOT: 'The backend snapshot was incomplete. Please retry.',
  CHUNK_COUNT_MISMATCH: 'The backend sent an inconsistent number of data chunks. Please retry.',
  FORECAST_ORIGIN_ID_MISMATCH: 'The backend returned a snapshot for a different forecast origin.',
  SNAPSHOT_METADATA_CONTRACT_MISMATCH: 'The backend snapshot metadata did not match the confirmed contract. Please retry.',
  FRAME_SEQUENCE_VIOLATION: 'The backend sent data out of the expected order. Please retry.',
  TRANSPORT_NOT_READY: 'The connection to the geospatial backend is not ready yet. Please wait and try again.',
}

export function errorStatusMessage(status) {
  return ERROR_STATUS_MESSAGES[status] || 'An unexpected error occurred. Please try again.'
}

/**
 * GEO-INT-03 Section 8: the operational overlay shows a veterinarian-
 * verified diagnostic case -- neutral clinical evidence, never an
 * outbreak classification (mirrors the backend semantic firewall,
 * `backend/components/geospatial_tracking/domain/operational_enums.py::
 * ClinicalSemanticClass`, read-only). Approved wording only: "Verified
 * clinical context" (or the short form for tight spaces) -- never
 * "Confirmed"/"Confirmed outbreak"/"Current outbreak"/"Live outbreak"/
 * "Official outbreak".
 */
export const LABEL_OPERATIONAL_CONTEXT = 'Verified clinical context'
export const LABEL_OPERATIONAL_CONTEXT_SHORT = 'Verified clinical'
export const DISCLAIMER_OPERATIONAL =
  'Verified clinical context is not a confirmed outbreak, forecast origin, or official historical record.'

export const LABEL_OPERATIONAL_DISEASE = 'Disease'
export const LABEL_OPERATIONAL_FARM_ID = 'Farm identifier'
export const LABEL_OPERATIONAL_DISTRICT = 'District'
export const LABEL_OPERATIONAL_VERIFIED_AT = 'Verification time'
export const LABEL_OPERATIONAL_LOCATION_STATUS = 'Location status'

// GEO26B Section 8/10: farm-aggregate popup -- a farm marker represents
// one or more real verified cases at ONE farm, so the popup states the
// real count and the real latest/recent verification times, never an
// invented density/confidence/outbreak-speed value.
export const LABEL_OPERATIONAL_CASE_COUNT = 'Verified cases at this farm'
export const LABEL_OPERATIONAL_LATEST_VERIFIED = 'Latest verified'
export const LABEL_OPERATIONAL_RECENT_VERIFIED = 'Recent verified dates'
export const LABEL_OPERATIONAL_CASE_IDS = 'Case identifiers'

// GEO29A Phase 5: a farm that only qualifies through district-wide
// surveillance (never personally assigned to the signed-in vet) shows a
// neutral location label instead of its real farm identifier -- never
// leaking a farmer's identity to a vet with no personal relationship to
// that farm.
export const LABEL_OPERATIONAL_NEUTRAL_LOCATION = 'Verified clinical location'

// GEO26B Section 6/25: the Observation Date Range control -- a
// clinical-history filter, deliberately distinct wording from the
// scientific forecast timeline's D0/D+N labels.
// GEO31A: "Window" (matches the approved reference's "WINDOW:" label) --
// content unchanged in meaning, just shorter; casing is a CSS concern
// (`uppercase` utility class), never baked into the string itself.
export const LABEL_OBSERVATION_WINDOW = 'Window'

// GEO26B Section 15: the Location control -- "My District" is honestly
// scoped to the vet's own authorized assigned-farm bounds (no real Sri
// Lanka ADM2 boundary dataset is available in this codebase), never a
// fabricated polygon.
// GEO30A Section 5: "My District" (dynamically suffixed with the vet's
// real registered district, e.g. "My District · Matara" -- never
// hardcoded, never "My District" alone with no real district behind it).
// This control fits real district/assigned-farm bounds ONLY (camera, not
// a data filter) -- never a fabricated district boundary, since no real
// Sri Lanka ADM2 dataset exists in this repo.
export const LABEL_LOCATION_SCOPE = 'Location'
export const LABEL_LOCATION_SRI_LANKA = 'Sri Lanka'
export const LABEL_LOCATION_MY_DISTRICT = 'My District'
export const LABEL_LOCATION_MY_DISTRICT_UNAVAILABLE = 'No real farm location is available to focus on yet'

// GEO26D Section 6/7: honest empty-state copy for Cases mode when the
// real, already-filtered clinical-context list has zero entries -- never
// silence, never a fabricated marker.
export const LABEL_NO_VERIFIED_CASES_IN_WINDOW = 'No verified cases in the selected window'

// GEO31A Section 5/6/18: the Cases-mode Observed Timeline/status surface --
// distinct wording from the scientific D0/D+N timeline (`LABEL_FORECAST_D0`
// etc.) so a vet never confuses "which real dates were verified" with "the
// model's own forecast frames".
export const LABEL_OBSERVED_TIMELINE_PREFIX = 'Observed'
export const LABEL_OBSERVED_TIMELINE_SNAPSHOT_HINT = 'Play reveals verified events by their own real date.'

/**
 * GEO33B Section 10: the Cases-mode timeline header must name WHICH real
 * dataset it is replaying, explicitly and always -- not only in its
 * zero-events branch, where the only header used to live.
 *
 * Two genuinely different real datasets could drive an "observed" replay
 * on this page and they must never be silently mixed in one timeline or
 * one header:
 *  - OBSERVED CASES  -> the authorized VERIFIED CLINICAL replay. Real
 *    dates come from each case's own real `verification_time`
 *    (`adapters/observedReplay.js`). This is what Cases mode actually
 *    renders today.
 *  - OBSERVED OUTBREAKS -> the national HISTORICAL/SCIENTIFIC replay.
 *    Declared here so the distinction is nameable and reviewable, and so
 *    the two can never collapse into one ambiguous "Observed" string if a
 *    later checkpoint wires that layer up. It is deliberately NOT in use
 *    yet: the real `/analysis/{id}/sources` response carries only
 *    `source_id`/`availability_quality`/`gps_quality` and NO date field
 *    (`api/router.py::_source_features`), so there is no defensible real
 *    timestamp to build a national replay from -- and a fabricated one is
 *    never acceptable.
 *
 * Neither label may ever read "FORECAST": both describe real observations
 * that already happened. The scientific D0/D+N forecast timeline is a
 * separate control (`TimelineControl.jsx`) with its own separate wording.
 */
export const LABEL_OBSERVED_CASES_TIMELINE = 'Observed cases'
export const LABEL_OBSERVED_OUTBREAKS_TIMELINE = 'Observed outbreaks'
/** Shown in place of a date when the vet has NOT scrubbed back -- i.e.
 * every real event in the current window is revealed. Never a fabricated
 * "today"/date. */
export const LABEL_OBSERVED_AT_LATEST = 'At latest'

/**
 * GEO-UI-TIMELINE-01: the Risk-Zones-mode scientific D0/D+N timeline's own
 * dataset name, mirroring `LABEL_OBSERVED_CASES_TIMELINE`'s pattern so
 * `TimelineControl.jsx`'s header is exactly as explicit about which real
 * dataset it replays as `ObservedTimelineControl.jsx` already is. "Forecast"
 * describes the model's own D0..D+N horizon terminology (already used
 * throughout this codebase -- `LABEL_FORECAST_ORIGINS`,
 * `LABEL_FORECAST_D0`, the pre-existing "Forecast timeline" aria-label);
 * it never claims LIVE/real-time forecasting -- this page's actual
 * transport is `LABEL_RUNTIME_MODE`/`DISCLAIMER_RUNTIME_MODE` above
 * ("Historical retrospective replay"), unchanged by this label.
 */
export const LABEL_FORECAST_RISK_TIMELINE = 'Forecast risk'

// GEO26B Section 32: the risk-cell popup -- real per-cell scientific
// fields only (mirrors `CellDetailPanel.jsx`'s existing field list),
// plus which real forecast day it belongs to.
export const LABEL_CELL_POPUP_TITLE = 'Spatial cell'
export const LABEL_CELL_POPUP_DAY_PREFIX = 'Forecast day'

// GEO-INT-03 Section 14/20: honest controlled-refresh wording -- never
// "LIVE"/"Real-time"/"Streaming". The current transport is plain HTTP
// request/response, not a push mechanism.
export const LABEL_OPERATIONAL_STATUS_CONNECTED = 'Operational context'
export const LABEL_OPERATIONAL_STATUS_STALE = 'Operational context · Stale'
export const LABEL_OPERATIONAL_STATUS_LOADING = 'Operational context · Loading…'
export const LABEL_OPERATIONAL_STATUS_SESSION_REQUIRED = 'Operational context · Session required'
export const LABEL_OPERATIONAL_STATUS_FORBIDDEN = 'Operational context · Veterinarian access required'
export const LABEL_OPERATIONAL_STATUS_HOST_COMPOSITION_REQUIRED = 'Operational context · Not connected'
export const LABEL_OPERATIONAL_STATUS_UNAVAILABLE = 'Operational context · Unavailable'
export const ACTION_REFRESH_OPERATIONAL_CONTEXT = 'Refresh'

/**
 * GEO-AREA-02: Page 2 "My Area" -- combines the authorized operational
 * farm (GEO-INT-01/02) with real historical/model context
 * (GEO-AREA-01/01H) WITHOUT mixing their meanings. Every distance/
 * relation string below mirrors the backend's own hardened field names
 * exactly (`distance_basis`, `anchor_basis`) -- never a shorter/looser
 * paraphrase that could imply more than the backend actually proved.
 */
// GEO-MY-AREA-VISUAL-QA-REBUILD: page heading matches the reference
// "Area Risk Intelligence" composition; the persistent local-nav tab
// itself stays "My Area" (`GeospatialLayout.jsx`, unchanged) -- the same
// split the reference screenshots themselves show (tab says "My Area",
// page heading says "Area Risk Intelligence"). Tagline reworded from the
// reference's "...which outbreaks are responsible" to "...are relevant":
// this page never computes outbreak-level attribution/responsibility,
// only real origin relevance (`relevantOrigins`), so "responsible" would
// overstate what the real contract proves.
export const MY_AREA_PAGE_TITLE = 'Area Risk Intelligence'
export const MY_AREA_PAGE_TAGLINE = 'What may affect my area in the coming days, and which outbreaks are relevant.'

// Section 10: `distance_basis === 'NEAREST_T0_TRIGGER_SOURCE'` wording --
// never "outbreak"/"origin distance"/"threat" (Section 10's explicit
// forbidden examples).
export const LABEL_NEAREST_T0_TRIGGER_SOURCE = 'Nearest T0 trigger source'
export const LABEL_RELEVANT_ORIGINS = 'Relevant historical/model origins'
export const LABEL_DISTANCE_FROM_AREA = 'Distance from selected farm'

// Section 28: nearest-source-in-selected-analysis wording -- deliberately
// DIFFERENT label from LABEL_NEAREST_T0_TRIGGER_SOURCE (a different
// concept/source set, GEO-AREA-01H Section 7/9) -- never "nearest
// infection"/"nearest active outbreak"/"nearest live case".
export const LABEL_HISTORICAL_SOURCE_CONTEXT = 'Historical source context'

// Section 21: Relative Spatial Score honest-unavailable wording -- never
// 0%/Low/Green/Safe/"Unknown = 0".
export const LABEL_RELATIVE_SPATIAL_SCORE_UNAVAILABLE = 'Unavailable for this exact farm location'
export const DISCLAIMER_RELATIVE_SPATIAL_SCORE_UNAVAILABLE =
  'Point-to-cell containment is not exposed by the current scientific response.'

// Section 20: the exact required nominal-reach disclaimer -- also
// supplied verbatim by the backend on `nominal_reach_context.disclaimer`
// (preferred when present); this is the persistent footer/fallback copy,
// kept byte-identical to the backend's own string on purpose.
export const MY_AREA_NOMINAL_REACH_DISCLAIMER = 'Nominal reach — visualization only, not a disease boundary.'

// Section 30: compact, non-alarming empty/limitation states.
export const LABEL_MY_AREA_OPERATIONAL_NOT_CONNECTED = 'Operational context not connected'
export const LABEL_MY_AREA_CHOOSE_FARM = 'Choose an assigned farm'
export const LABEL_MY_AREA_LOCATION_REQUIRED = 'Farm location required'
export const LABEL_MY_AREA_NO_ASSIGNED_FARMS = 'No assigned farms are authorized for your account yet'
export const LABEL_MY_AREA_NO_RELEVANT_ORIGINS = 'No relevant historical/model origins available'
export const LABEL_MY_AREA_SELECT_ORIGIN = 'Select a historical/model origin to inspect context'
export const LABEL_MY_AREA_FORECAST_FRAME_UNAVAILABLE = 'Forecast frame unavailable'
export const LABEL_MY_AREA_UNSUPPORTED_DISEASE = 'Unsupported disease selection'
export const LABEL_MY_AREA_MODEL_NOT_READY = 'Scientific analysis unavailable for this disease'
export const LABEL_MY_AREA_HOST_NOT_CONNECTED = 'My Area is not connected yet'
export const LABEL_MY_AREA_SESSION_REQUIRED = 'Session required'
export const LABEL_MY_AREA_FORBIDDEN = 'Veterinarian access required'
export const LABEL_MY_AREA_AREA_NOT_FOUND = 'Selected farm is not authorized or unavailable'
export const LABEL_MY_AREA_ORIGIN_NOT_FOUND = 'Selected historical/model origin is unavailable'

// Section 15/16: the authorized-farm map marker -- never "outbreak"/
// "clinical case"/"risk zone"/"forecast origin".
export const LABEL_MY_AREA_FARM_MARKER = 'My assigned area'

// GEO-MY-AREA-VISUAL-QA-REBUILD: truthful badge wording for the
// "Outbreaks influencing my area" list -- keyed off the real
// `distance_basis` field already on each relevant origin, never a
// fabricated "trajectory intersects"/"active cluster" claim (neither
// trajectory nor clustering has a current Page runtime/API contract).
export const LABEL_BADGE_NEAREST_TRIGGER_SOURCE = 'NEAREST TRIGGER SOURCE'
export const LABEL_BADGE_RELEVANT_HISTORICAL_ORIGIN = 'RELEVANT HISTORICAL ORIGIN'

// Section 19: D0 wording -- never a fabricated "0 km".
export const LABEL_FORECAST_D0 = 'Observed / origin context'

/**
 * GEO-ANALYSIS-02: Page 3 "Analysis & Trends" -- real Sri Lanka
 * historical/model evidence, never a generic KPI dashboard. Every
 * "unavailable" label below describes an INTENTIONAL evidence state
 * (Section 34's "make unavailable evidence look intentional"), never an
 * error -- and every numeric-looking label stays a plain noun phrase,
 * never implying a percentage/score/grade the backend does not supply.
 */
export const ANALYSIS_TRENDS_PAGE_TITLE = 'Analysis & Trends'
export const ANALYSIS_TRENDS_PAGE_TAGLINE = 'Historical outbreak patterns and spatial intelligence'

// Section 16/17: KPI wording -- "Historical source records" (never
// "Cases today"/"Active cases"/"Current infections"), "Forecast
// origins" as its OWN separate card (never summed with the above), and
// "Observation coverage" (never "Active period"/"Epidemic duration").
export const LABEL_HISTORICAL_SOURCE_RECORDS = 'Historical source records'
export const LABEL_FORECAST_ORIGINS = 'Forecast origins'
export const LABEL_OBSERVATION_COVERAGE = 'Observation coverage'
export const LABEL_TREND_BASIS = 'Trend basis'
export const LABEL_HISTORICAL_TREND = 'Historical trend'
export const LABEL_NO_HISTORICAL_DATA = 'No historical data available for this disease'

// Section 8: compact scope chip -- "Sri Lanka · Retrospective evidence".
export const LABEL_SCOPE_RETROSPECTIVE_SUFFIX = 'Retrospective evidence'

// Section 12/21: origin selection -- never "live outbreaks"/"current
// outbreaks"/"active infections".
export const LABEL_ANALYSIS_ORIGIN_SELECTOR = 'Historical/model origin'
export const LABEL_SELECT_ORIGIN_FOR_CONTEXT = 'Select a historical/model origin for origin-level context'
export const LABEL_ANALYSIS_ORIGIN_UNAVAILABLE_FOR_DISEASE = 'Origin-level forecast analytics unavailable for this disease'

// Section 23: apparent rate -- never "virus speed"/"spread speed"/
// "future speed"/"transmission velocity".
export const LABEL_ANALYSIS_APPARENT_RATE = 'Apparent rate'
export const APPARENT_RATE_HELP_TEXT = 'Frozen retrospective apparent-rate context.'
export const APPARENT_RATE_UNIT = 'km/day'

// Section 24: origin-level direction is per-cell only -- never a
// fabricated 0°/averaged bearing.
export const LABEL_ORIGIN_LEVEL_DIRECTION = 'Origin-level direction'
export const LABEL_DIRECTION_NOT_DEFINED = 'Not defined by current runtime contract'

// Section 25/27: nominal reach / RSS distribution -- disclaimer text is
// kept BYTE-IDENTICAL to `MY_AREA_NOMINAL_REACH_DISCLAIMER` above (same
// backend field, same required sentence) rather than redeclared.
export const LABEL_NOMINAL_REACH_D1_D7 = 'Nominal reach (D+1 – D+7)'
export const LABEL_RSS_DISTRIBUTION = 'Relative Spatial Score distribution'
export const LABEL_RSS_TEMPORAL_BASIS = 'Static T0 frozen spatial-rank context'
export const LABEL_RSS_MIN = 'Minimum'
export const LABEL_RSS_MEDIAN = 'Median'
export const LABEL_RSS_MAX = 'Maximum'
export const LABEL_CROSS_SNAPSHOT_UNSUPPORTED = 'Cross-snapshot comparison is not supported.'

// Section 30-34: evidence-availability panel -- every one of these is an
// intentional, explicit "not available" statement, never a placeholder
// number/gauge/percentage.
export const LABEL_EVIDENCE_AVAILABILITY = 'Evidence availability'
export const LABEL_MODEL_EVALUATION = 'Model evaluation'
export const LABEL_MODEL_EVALUATION_NOT_AVAILABLE = 'Not exposed by current runtime evidence'
export const LABEL_MODEL_EVALUATION_MODEL_NOT_READY = 'Model not ready for this disease'
export const LABEL_MODEL_RUN_COMPARISON = 'Model-run comparison'
export const LABEL_MODEL_RUN_COMPARISON_NOT_AVAILABLE = 'Not available'
export const LABEL_CONFIDENCE = 'Confidence'
export const LABEL_CONFIDENCE_NOT_AVAILABLE = 'Not available'
export const LABEL_DRIVERS = 'Environmental / model drivers'
export const LABEL_DRIVERS_NOT_AVAILABLE = 'Not available'

// Section 35: FMD must not look broken -- a distinct, visible statement,
// never a hidden/blank page.
export const LABEL_SCIENTIFIC_MODEL = 'Scientific model'
export const LABEL_MODEL_NOT_READY_FOR_DISEASE = 'Not ready for this disease'

// Section 6/48: failure / host-composition states.
export const LABEL_ANALYSIS_TRENDS_SESSION_REQUIRED = 'Session required'
export const LABEL_ANALYSIS_TRENDS_FORBIDDEN = 'Veterinarian access required'
export const LABEL_ANALYSIS_TRENDS_HOST_NOT_CONNECTED = 'Analysis & Trends service not connected'
export const LABEL_ANALYSIS_TRENDS_UNSUPPORTED_DISEASE = 'Unsupported disease selection'
export const LABEL_ANALYSIS_TRENDS_ORIGIN_NOT_FOUND = 'Selected historical/model origin is unavailable'
export const LABEL_ANALYSIS_TRENDS_INTERNAL_ERROR = 'Analysis temporarily unavailable'
export const LABEL_ANALYSIS_TRENDS_INVALID_REQUEST = 'Invalid Analysis & Trends request'
export const LABEL_ANALYSIS_TRENDS_NETWORK_ERROR = 'Could not reach the backend'

/**
 * FMD-10C: Page 1's FMD-only scalar spatial score panel. `risk_score` is
 * a DIMENSIONLESS relative origin-level spatial score
 * (`RISK_SCORE_SEMANTICS_9` on the backend) -- shown as a raw number,
 * never `%`, never multiplied by 100, never "probability"/"confidence",
 * never clamped to [0,1], and never reclassified against the backend's
 * own 0.05 threshold on the frontend (Section rules for this checkpoint).
 */
export const LABEL_RELATIVE_ORIGIN_SPATIAL_SCORE = 'Relative Origin Spatial Score'
export const DISCLAIMER_RELATIVE_ORIGIN_SPATIAL_SCORE =
  'Dimensionless relative spatial score for this origin only -- not infection probability, not a percentage, not confidence.'
export const LABEL_FMD_RISK_LOADING = 'Loading spatial score…'
export const LABEL_FMD_RISK_UNAVAILABLE = 'Unavailable for this origin'
export const LABEL_FMD_RISK_NOT_FOUND = 'Selected origin is unavailable'
export const LABEL_FMD_RISK_ERROR = 'Could not load the spatial score'
export const LABEL_FMD_HISTORICAL_ORIGINS = 'Historical FMD origins'
// FMD-10C1: real FMD trigger-source points are now rendered on the map
// itself (`/origins/{id}/trigger-sources`) -- this panel is a secondary,
// accessible/selectable list over the same real origins, never the only
// representation.
export const LABEL_FMD_ORIGIN_PANEL_SUBTITLE = 'Also shown as real points on the map (circle marker).'

/**
 * Wording that must NEVER appear in any user-facing string exported
 * from this module (Part 6 forbidden list) -- checked by a dedicated
 * test, case-insensitively.
 */
export const FORBIDDEN_WORDING = [
  'infection probability',
  'chance of infection',
  'prediction accuracy',
  'live disease prediction',
  'live disease feed',
  'real-time epidemiological forecasting',
  'predicted disease spread direction',
  'confidence score',
  // LSD-UI-03 / LSD-PAGE1-HARDENING (plan Section 9): neither the
  // connection-status chip nor the page tagline may claim a true
  // live/current state -- the real transport is historical
  // retrospective replay.
  'live current',
  'live outbreak feed',
  'live outbreak surveillance',
  // GEO-INT-03 Section 8: the operational verified-clinical-context
  // overlay must never be labelled with any of these stronger claims.
  'confirmed outbreak',
  'current outbreak',
  'official outbreak',
  'live outbreak',
  'live clinical',
  // GEO-AREA-02 Section 40: Page 2 must never derive a containment/
  // safety claim from the backend's intentionally-NOT_APPLICABLE
  // nominal-reach relation or the intentionally-unavailable Relative
  // Spatial Score.
  'farm is safe',
  'farm infected',
  'will reach your farm',
  'will not reach your farm',
  'inside outbreak',
  'outside outbreak',
  'quarantine radius',
  'nearest infection',
  'nearest active outbreak',
  'nearest live case',
  'outbreak distance',
  'distance to outbreak',
  'distance to origin',
  // GEO-ANALYSIS-02 Section 49: Page 3 must never introduce an
  // unsupported KPI/evaluation/driver/live-count claim the backend does
  // not genuinely expose.
  'infection %',
  'accuracy %',
  'confidence %',
  'active outbreak count',
  'current outbreak count',
  'live cases',
  'safe area',
  'high-risk farm',
  'virus speed',
  'spread speed',
  'future speed',
  'transmission velocity',
  'predicted infection radius',
  'infection radius',
  'top environmental driver',
  '92% accuracy',
  'rainfall 40%',
  'humidity 30%',
  'wind 30%',
  'this month',
  'improved by',
]
