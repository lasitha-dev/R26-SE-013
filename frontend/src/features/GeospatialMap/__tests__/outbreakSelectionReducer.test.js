import { describe, expect, it } from 'vitest'

import {
  ANALYSIS_MODE,
  initialOutbreakSelectionState,
  isPlaybackAtEnd,
  outbreakSelectionReducer,
} from '../context/outbreakSelectionReducer'

describe('outbreakSelectionReducer', () => {
  it('starts on LSD, no outbreak, day 0, Cases mode', () => {
    expect(initialOutbreakSelectionState.selectedDisease).toBe('LSD')
    expect(initialOutbreakSelectionState.selectedOutbreakId).toBeNull()
    expect(initialOutbreakSelectionState.selectedForecastDay).toBe(0)
    expect(initialOutbreakSelectionState.analysisMode).toBe(ANALYSIS_MODE.CASES)
  })

  it('SELECT_OUTBREAK resets day to 0, pauses playback, adopts the real availableForecastFrames', () => {
    const midPlayback = { ...initialOutbreakSelectionState, selectedForecastDay: 4, isPlaybackActive: true }
    const next = outbreakSelectionReducer(midPlayback, {
      type: 'SELECT_OUTBREAK',
      payload: { outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', modelRunId: 'snap-1', availableForecastFrames: [0, 1, 2, 3, 4, 5, 6, 7] },
    })
    expect(next.selectedOutbreakId).toBe('ORIGIN:Sri Lanka:2020-09-28')
    expect(next.selectedForecastDay).toBe(0)
    expect(next.isPlaybackActive).toBe(false)
    expect(next.availableForecastFrames).toEqual([0, 1, 2, 3, 4, 5, 6, 7])
  })

  it('SELECT_DISEASE clears outbreak/model-run/day/playback -- never carries context across diseases', () => {
    const lsdSelected = outbreakSelectionReducer(initialOutbreakSelectionState, {
      type: 'SELECT_OUTBREAK',
      payload: { outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', modelRunId: 'snap-1', availableForecastFrames: [0, 1] },
    })
    const afterDiseaseSwitch = outbreakSelectionReducer(lsdSelected, { type: 'SELECT_DISEASE', payload: { disease: 'FMD' } })
    expect(afterDiseaseSwitch.selectedDisease).toBe('FMD')
    expect(afterDiseaseSwitch.selectedOutbreakId).toBeNull()
    expect(afterDiseaseSwitch.selectedModelRunId).toBeNull()
    expect(afterDiseaseSwitch.availableForecastFrames).toEqual([0])
  })

  it('SELECT_DAY only accepts a day that exists in availableForecastFrames', () => {
    const withFrames = { ...initialOutbreakSelectionState, availableForecastFrames: [0, 1, 2] }
    const accepted = outbreakSelectionReducer(withFrames, { type: 'SELECT_DAY', payload: { day: 2 } })
    expect(accepted.selectedForecastDay).toBe(2)

    const rejected = outbreakSelectionReducer(withFrames, { type: 'SELECT_DAY', payload: { day: 5 } })
    expect(rejected.selectedForecastDay).toBe(0) // unchanged -- day 5 isn't in this outbreak's real horizon
  })

  it('SET_MODE never touches outbreak/day/playback state (mode switch must not reset the timeline)', () => {
    const midState = { ...initialOutbreakSelectionState, selectedOutbreakId: 'ORIGIN:Sri Lanka:2020-09-28', selectedForecastDay: 3, isPlaybackActive: true }
    const next = outbreakSelectionReducer(midState, { type: 'SET_MODE', payload: { mode: ANALYSIS_MODE.RISK_ZONES } })
    expect(next.analysisMode).toBe(ANALYSIS_MODE.RISK_ZONES)
    expect(next.selectedOutbreakId).toBe('ORIGIN:Sri Lanka:2020-09-28')
    expect(next.selectedForecastDay).toBe(3)
    expect(next.isPlaybackActive).toBe(true)
  })

  it('PLAY is a no-op when there is only one real frame (day 0 alone)', () => {
    const singleFrame = { ...initialOutbreakSelectionState, availableForecastFrames: [0] }
    const next = outbreakSelectionReducer(singleFrame, { type: 'PLAY' })
    expect(next.isPlaybackActive).toBe(false)
  })

  it('SET_AVAILABLE_FRAMES applies the real late-arriving frame horizon once the outbreak summary loads', () => {
    const afterClick = outbreakSelectionReducer(initialOutbreakSelectionState, {
      type: 'SELECT_OUTBREAK',
      payload: { outbreakId: 'ORIGIN:Sri Lanka:2020-09-28' }, // clicked, data not loaded yet
    })
    expect(afterClick.availableForecastFrames).toEqual([0])

    const afterLoad = outbreakSelectionReducer(afterClick, {
      type: 'SET_AVAILABLE_FRAMES',
      payload: { outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', availableForecastFrames: [0, 1, 2, 3, 4, 5, 6, 7], modelRunId: 'snap-1' },
    })
    expect(afterLoad.availableForecastFrames).toEqual([0, 1, 2, 3, 4, 5, 6, 7])
    expect(afterLoad.selectedModelRunId).toBe('snap-1')
  })

  it('SET_AVAILABLE_FRAMES is ignored if a different outbreak was selected in the meantime (stale-response guard)', () => {
    const afterClick = outbreakSelectionReducer(initialOutbreakSelectionState, {
      type: 'SELECT_OUTBREAK',
      payload: { outbreakId: 'ORIGIN:Sri Lanka:2020-09-28' },
    })
    const userClickedAnotherOutbreak = outbreakSelectionReducer(afterClick, {
      type: 'SELECT_OUTBREAK',
      payload: { outbreakId: 'ORIGIN:Sri Lanka:2020-10-28' },
    })
    const staleResponseArrives = outbreakSelectionReducer(userClickedAnotherOutbreak, {
      type: 'SET_AVAILABLE_FRAMES',
      payload: { outbreakId: 'ORIGIN:Sri Lanka:2020-09-28', availableForecastFrames: [0, 1, 2, 3, 4, 5, 6, 7], modelRunId: 'stale-snap' },
    })
    expect(staleResponseArrives).toBe(userClickedAnotherOutbreak) // unchanged
  })

  it('ADVANCE_DAY walks the real frame list and stops playback at the end', () => {
    let state = { ...initialOutbreakSelectionState, availableForecastFrames: [0, 1, 2], selectedForecastDay: 0, isPlaybackActive: true }
    state = outbreakSelectionReducer(state, { type: 'ADVANCE_DAY' })
    expect(state.selectedForecastDay).toBe(1)
    expect(isPlaybackAtEnd(state)).toBe(false)

    state = outbreakSelectionReducer(state, { type: 'ADVANCE_DAY' })
    expect(state.selectedForecastDay).toBe(2)
    expect(isPlaybackAtEnd(state)).toBe(true)

    state = outbreakSelectionReducer(state, { type: 'ADVANCE_DAY' })
    expect(state.selectedForecastDay).toBe(2) // stays put
    expect(state.isPlaybackActive).toBe(false) // playback stops itself
  })
})
