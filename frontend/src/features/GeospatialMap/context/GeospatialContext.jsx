/**
 * LSD-UI-01: the shared state Pages 1-3 all read from and write to
 * (plan Section K). Composes two independent, separately-testable
 * reducers rather than merging them:
 *  - `useGeospatialSnapshot()` (Checkpoint 11A/11B, unchanged) -- the WS
 *    transport/snapshot-assembly machine.
 *  - `outbreakSelectionReducer` (LSD-UI-01, new) -- disease/outbreak/
 *    area/day/mode/playback selection.
 * `connectionState` is a direct pass-through of the transport's `PHASE`
 * enum, never a second parallel connection-state (plan Section H).
 */
import React, { createContext, useCallback, useContext, useMemo, useReducer } from 'react'

import {
  ANALYSIS_MODE,
  initialOutbreakSelectionState,
  outbreakSelectionReducer,
} from './outbreakSelectionReducer'
import { useGeospatialSnapshot } from '../state/useGeospatialSnapshot'

const GeospatialContext = createContext(null)

export function GeospatialProvider({ children }) {
  const transport = useGeospatialSnapshot()
  const [selection, dispatch] = useReducer(outbreakSelectionReducer, initialOutbreakSelectionState)

  const selectDisease = useCallback((disease) => dispatch({ type: 'SELECT_DISEASE', payload: { disease } }), [])
  const selectArea = useCallback((areaId) => dispatch({ type: 'SELECT_AREA', payload: { areaId } }), [])
  const selectOutbreak = useCallback(
    (outbreakId, { modelRunId, availableForecastFrames } = {}) =>
      dispatch({ type: 'SELECT_OUTBREAK', payload: { outbreakId, modelRunId, availableForecastFrames } }),
    [],
  )
  const clearOutbreakSelection = useCallback(() => dispatch({ type: 'CLEAR_OUTBREAK_SELECTION' }), [])
  const selectDay = useCallback((day) => dispatch({ type: 'SELECT_DAY', payload: { day } }), [])
  const setModelRun = useCallback((modelRunId) => dispatch({ type: 'SET_MODEL_RUN', payload: { modelRunId } }), [])
  const setAvailableFrames = useCallback(
    (outbreakId, availableForecastFrames, modelRunId) => dispatch({ type: 'SET_AVAILABLE_FRAMES', payload: { outbreakId, availableForecastFrames, modelRunId } }),
    [],
  )
  const setMode = useCallback((mode) => dispatch({ type: 'SET_MODE', payload: { mode } }), [])
  const play = useCallback(() => dispatch({ type: 'PLAY' }), [])
  const pause = useCallback(() => dispatch({ type: 'PAUSE' }), [])
  const advanceDay = useCallback(() => dispatch({ type: 'ADVANCE_DAY' }), [])

  const value = useMemo(
    () => ({
      ...selection,
      connectionState: transport.state.phase,
      // Reserved, not yet real (plan Section H/O) -- there is no live
      // push mechanism to increment this. Kept in the shape now so
      // consuming components don't need a state-shape change later.
      liveSnapshotVersion: 0,
      transport,
      dispatch,
      selectDisease,
      selectArea,
      selectOutbreak,
      clearOutbreakSelection,
      selectDay,
      setModelRun,
      setAvailableFrames,
      setMode,
      play,
      pause,
      advanceDay,
    }),
    [
      selection,
      transport,
      selectDisease,
      selectArea,
      selectOutbreak,
      clearOutbreakSelection,
      selectDay,
      setModelRun,
      setAvailableFrames,
      setMode,
      play,
      pause,
      advanceDay,
    ],
  )

  return <GeospatialContext.Provider value={value}>{children}</GeospatialContext.Provider>
}

export function useGeospatialContext() {
  const ctx = useContext(GeospatialContext)
  if (!ctx) {
    throw new Error('useGeospatialContext must be used within a <GeospatialProvider>')
  }
  return ctx
}

export { ANALYSIS_MODE }
