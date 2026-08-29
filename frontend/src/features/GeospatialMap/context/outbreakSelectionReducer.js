/**
 * LSD-UI-01: pure reducer for the shared outbreak-selection state
 * (plan Section K) -- deliberately separate from `geospatialReducer.js`
 * (the WS transport/snapshot-assembly state machine, Checkpoint 11A/11B,
 * 32 existing tests). That file models "is a snapshot loaded and what
 * does it contain"; this one models "what is the vet currently looking
 * at" (disease/outbreak/area/day/mode/playback) -- a different, higher
 * layer that composes on top of it in `GeospatialContext.jsx`, not a
 * merge into the same machine.
 *
 * Kept framework-free (no React import) so it's unit-testable the same
 * way `geospatialReducer.js`/`snapshotAssembly.js` already are.
 */

import { CAPABILITY, DEFAULT_DISEASE_CODE, hasCapability } from '../disease/diseaseRegistry'

export const ANALYSIS_MODE = {
  CASES: 'cases',
  CLUSTERS: 'clusters',
  RISK_ZONES: 'riskZones',
  TRAJECTORY: 'trajectory',
  ENV: 'env',
}

/** FMD-10C: which capability an analysis mode depends on -- CASES/
 * CLUSTERS have no per-disease capability gate (Clusters stays globally
 * disabled in `ModeToolbar.jsx` regardless of disease, an unrelated
 * "not wired to any disease yet" reason). Used only to decide whether a
 * disease switch must fall back to Cases, never to decide whether a
 * mode is clickable at all (`ModeToolbar.jsx` owns that). */
const ANALYSIS_MODE_CAPABILITY = {
  [ANALYSIS_MODE.RISK_ZONES]: CAPABILITY.RISK_ZONES,
  [ANALYSIS_MODE.TRAJECTORY]: CAPABILITY.TRAJECTORY,
  [ANALYSIS_MODE.ENV]: CAPABILITY.ENVIRONMENTAL_VECTORS,
}

export const initialOutbreakSelectionState = {
  selectedDisease: DEFAULT_DISEASE_CODE,
  selectedOutbreakId: null,
  selectedAreaId: null,
  selectedForecastDay: 0,
  selectedModelRunId: null,
  analysisMode: ANALYSIS_MODE.CASES,
  isPlaybackActive: false,
  // Real backend horizon is 7 nominal-reach days (primary_horizon_days
  // in /api/geospatial/protocol), not 14/15 -- see plan Section D/Q.
  // Populated for real once an outbreak is selected and its
  // nominal_reach_by_day is fetched; [0] alone (Day 0/observed) until then.
  availableForecastFrames: [0],
}

export function outbreakSelectionReducer(state, action) {
  switch (action.type) {
    case 'SELECT_DISEASE': {
      // Changing disease invalidates any outbreak/day/model-run selection
      // from the previous disease -- never carry FMD context into an LSD
      // view or vice versa (plan Section D's onDiseaseChange pattern).
      const disease = action.payload.disease
      // FMD-10C: an analysis mode the NEW disease can't support (e.g.
      // Risk Zones, which needs nominalReach + spatial cells FMD doesn't
      // have) must never survive the switch -- reset to Cases rather
      // than silently keep drawing stale LSD-shaped geometry for FMD.
      const requiredCapability = ANALYSIS_MODE_CAPABILITY[state.analysisMode]
      const modeStillSupported = !requiredCapability || hasCapability(disease, requiredCapability)
      return {
        ...state,
        selectedDisease: disease,
        analysisMode: modeStillSupported ? state.analysisMode : ANALYSIS_MODE.CASES,
        selectedOutbreakId: null,
        selectedModelRunId: null,
        selectedForecastDay: 0,
        isPlaybackActive: false,
        availableForecastFrames: [0],
      }
    }

    case 'SELECT_AREA':
      return { ...state, selectedAreaId: action.payload.areaId }

    case 'SELECT_OUTBREAK':
      // Selecting a (new) outbreak always resets to Day 0/observed and
      // pauses playback -- plan Section D step 2 ("pause existing
      // playback") -- and adopts whatever real forecast-day horizon the
      // caller resolved for this outbreak (adapter-supplied, not assumed).
      return {
        ...state,
        selectedOutbreakId: action.payload.outbreakId,
        selectedModelRunId: action.payload.modelRunId ?? null,
        selectedForecastDay: 0,
        isPlaybackActive: false,
        availableForecastFrames: action.payload.availableForecastFrames ?? [0],
      }

    case 'CLEAR_OUTBREAK_SELECTION':
      return {
        ...state,
        selectedOutbreakId: null,
        selectedModelRunId: null,
        selectedForecastDay: 0,
        isPlaybackActive: false,
        availableForecastFrames: [0],
      }

    case 'SELECT_DAY': {
      const day = action.payload.day
      if (!state.availableForecastFrames.includes(day)) return state
      return { ...state, selectedForecastDay: day }
    }

    case 'SET_MODEL_RUN':
      return { ...state, selectedModelRunId: action.payload.modelRunId }

    case 'SET_AVAILABLE_FRAMES':
      // `SELECT_OUTBREAK` fires immediately on click (so the map can
      // dim/halo without waiting on the network); the real summary/
      // cells/sources fetch resolves slightly later and reports back
      // the outbreak's actual frame horizon + snapshot identity here.
      // Ignored if the vet has already selected a DIFFERENT outbreak by
      // the time this late response arrives (stale-response guard).
      if (action.payload.outbreakId !== state.selectedOutbreakId) return state
      return {
        ...state,
        availableForecastFrames: action.payload.availableForecastFrames,
        selectedModelRunId: action.payload.modelRunId ?? state.selectedModelRunId,
      }

    case 'SET_MODE':
      // Mode switch must never touch camera/outbreak/day/playback state
      // -- plan Section D toolbar requirement ("don't reset the timeline
      // on mode switch").
      return { ...state, analysisMode: action.payload.mode }

    case 'PLAY':
      if (state.availableForecastFrames.length <= 1) return state
      return { ...state, isPlaybackActive: true }

    case 'PAUSE':
      return { ...state, isPlaybackActive: false }

    case 'ADVANCE_DAY': {
      const idx = state.availableForecastFrames.indexOf(state.selectedForecastDay)
      const nextIdx = idx + 1
      if (nextIdx >= state.availableForecastFrames.length) {
        return { ...state, isPlaybackActive: false }
      }
      return { ...state, selectedForecastDay: state.availableForecastFrames[nextIdx] }
    }

    default:
      return state
  }
}

export function isPlaybackAtEnd(state) {
  const idx = state.availableForecastFrames.indexOf(state.selectedForecastDay)
  return idx === state.availableForecastFrames.length - 1
}
