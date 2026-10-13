import { describe, expect, it } from 'vitest'

import { isEventRelevantToMyArea } from '../adapters/operationalEventRelevance'

const EVENT = { event_id: 'vcc:C1:x', case_id: 'C1', farm_id: 'F1', disease: 'LSD', verified_at: '2026-01-02 10:00:00' }

describe('GEO-LIVE-05-RELEVANCE-01: My Area event relevance is farm-scoped only', () => {
  it('an event for the currently selected farm is relevant', () => {
    expect(isEventRelevantToMyArea(EVENT, { selectedAreaId: 'F1' })).toBe(true)
  })

  it('an event for a DIFFERENT assigned farm is not relevant to the currently displayed one', () => {
    expect(isEventRelevantToMyArea(EVENT, { selectedAreaId: 'F2' })).toBe(false)
  })

  it('no selected farm yet -- never relevant', () => {
    expect(isEventRelevantToMyArea(EVENT, { selectedAreaId: null })).toBe(false)
  })

  it('no event -- never relevant', () => {
    expect(isEventRelevantToMyArea(null, { selectedAreaId: 'F1' })).toBe(false)
  })
})
