import { describe, expect, it } from 'vitest'
import * as semanticLabels from '../semanticLabels'
import { FORBIDDEN_WORDING } from '../semanticLabels'

function allExportedStrings() {
  const values = []
  for (const [key, value] of Object.entries(semanticLabels)) {
    if (key === 'FORBIDDEN_WORDING') continue // the forbidden list itself legitimately CONTAINS the forbidden phrases
    if (typeof value === 'string') values.push(value)
    if (value && typeof value === 'object') {
      for (const v of Object.values(value)) {
        if (typeof v === 'string') values.push(v)
      }
    }
  }
  return values
}

// Negation-aware check: a forbidden phrase is fine when it appears
// inside a legitimate DISCLAIMER that explicitly negates it ("not
// infection probability", "not a predicted disease-spread direction").
// What must never happen is the phrase appearing WITHOUT a negation
// word in the ~20 characters immediately before it -- i.e. asserted
// affirmatively. A blunt substring-absence check would false-positive
// on the module's own correct disclaimer text.
function assertOnlyNegatedOccurrences(lowered, phrase) {
  let searchFrom = 0
  while (true) {
    const idx = lowered.indexOf(phrase, searchFrom)
    if (idx === -1) return
    const window = lowered.slice(Math.max(0, idx - 20), idx)
    const negated = /\b(not|never|no)\b/.test(window)
    expect(negated, `"${phrase}" appears without a preceding negation in: "${lowered}"`).toBe(true)
    searchFrom = idx + phrase.length
  }
}

describe('11A-SEM-01: risk never labelled probability/accuracy', () => {
  it('DISCLAIMER_RISK explicitly denies probability/accuracy framing', () => {
    const lowered = semanticLabels.DISCLAIMER_RISK.toLowerCase()
    expect(lowered).toContain('not infection probability')
  })

  it('no exported string affirmatively claims risk is a probability or accuracy metric', () => {
    for (const value of allExportedStrings()) {
      const lowered = value.toLowerCase()
      assertOnlyNegatedOccurrences(lowered, 'infection probability')
      assertOnlyNegatedOccurrences(lowered, 'prediction accuracy')
    }
  })
})

describe('11A-SEM-02: direction never labelled predicted disease spread', () => {
  it('DISCLAIMER_DIRECTION explicitly denies predicted-direction framing', () => {
    expect(semanticLabels.DISCLAIMER_DIRECTION.toLowerCase()).toContain('not a predicted disease-spread direction')
  })

  it('no exported string affirmatively claims a predicted disease-spread direction', () => {
    for (const value of allExportedStrings()) {
      assertOnlyNegatedOccurrences(value.toLowerCase(), 'predicted disease-spread direction')
    }
  })
})

describe('11A-SEM-03: clarity never labelled confidence', () => {
  it('DISCLAIMER_CLARITY explicitly denies confidence framing', () => {
    expect(semanticLabels.DISCLAIMER_CLARITY.toLowerCase()).toContain('not confidence')
  })

  it('LABEL_CLARITY itself is never named "confidence"', () => {
    expect(semanticLabels.LABEL_CLARITY.toLowerCase()).not.toContain('confidence')
  })
})

describe('11A-SEM-04: historical replay / not-live-operational status visible', () => {
  it('DISCLAIMER_RUNTIME_MODE states historical replay and live-forecasting non-implementation', () => {
    const lowered = semanticLabels.DISCLAIMER_RUNTIME_MODE.toLowerCase()
    expect(lowered).toContain('historical retrospective replay')
    expect(lowered).toContain('live operational forecasting is not implemented')
  })
})

describe('LSD-UI-03: connection-status labels never claim LIVE (plan Section 9)', () => {
  it('none of the three real status labels is or contains the bare word "LIVE"', () => {
    for (const label of [semanticLabels.LABEL_SNAPSHOT_CONNECTED, semanticLabels.LABEL_SNAPSHOT_LOADING, semanticLabels.LABEL_SNAPSHOT_UNAVAILABLE]) {
      expect(label.toUpperCase()).not.toMatch(/\bLIVE\b/)
    }
  })

  it('the page tagline is context-honest for a historical-replay page, never claiming live operational surveillance (LSD-PAGE1-HARDENING)', () => {
    expect(semanticLabels.PAGE_TAGLINE).toBe('Historical outbreak replay and spatial model context')
    expect(semanticLabels.PAGE_TAGLINE.toUpperCase()).not.toMatch(/\bLIVE\b/)
  })
})

describe('GEO-INT-03: operational verified-clinical-context wording', () => {
  it('the approved label is exactly "Verified clinical context" (Section 8) -- never "Confirmed"', () => {
    expect(semanticLabels.LABEL_OPERATIONAL_CONTEXT).toBe('Verified clinical context')
    expect(semanticLabels.LABEL_OPERATIONAL_CONTEXT.toLowerCase()).not.toContain('confirmed')
  })

  it('DISCLAIMER_OPERATIONAL explicitly denies confirmed-outbreak framing', () => {
    const lowered = semanticLabels.DISCLAIMER_OPERATIONAL.toLowerCase()
    expect(lowered).toContain('not a confirmed outbreak')
  })

  it('none of the operational status labels contain the bare word "LIVE"', () => {
    const operationalLabels = [
      semanticLabels.LABEL_OPERATIONAL_STATUS_CONNECTED,
      semanticLabels.LABEL_OPERATIONAL_STATUS_STALE,
      semanticLabels.LABEL_OPERATIONAL_STATUS_LOADING,
      semanticLabels.LABEL_OPERATIONAL_STATUS_SESSION_REQUIRED,
      semanticLabels.LABEL_OPERATIONAL_STATUS_FORBIDDEN,
      semanticLabels.LABEL_OPERATIONAL_STATUS_HOST_COMPOSITION_REQUIRED,
      semanticLabels.LABEL_OPERATIONAL_STATUS_UNAVAILABLE,
    ]
    for (const label of operationalLabels) {
      expect(label.toUpperCase()).not.toMatch(/\bLIVE\b/)
      expect(label.toUpperCase()).not.toMatch(/\bREAL-TIME\b/)
      expect(label.toUpperCase()).not.toMatch(/\bSTREAMING\b/)
    }
  })

  it('the forbidden list now also rejects confirmed/current/official/live outbreak wording', () => {
    expect(semanticLabels.FORBIDDEN_WORDING).toContain('confirmed outbreak')
    expect(semanticLabels.FORBIDDEN_WORDING).toContain('current outbreak')
    expect(semanticLabels.FORBIDDEN_WORDING).toContain('official outbreak')
  })
})

describe('GEO-AREA-02: My Area wording', () => {
  it('the nominal-reach disclaimer is byte-identical to the backend\'s own required sentence', () => {
    expect(semanticLabels.MY_AREA_NOMINAL_REACH_DISCLAIMER).toBe('Nominal reach — visualization only, not a disease boundary.')
  })

  it('the relevant-origin distance wording is "Nearest T0 trigger source", never "outbreak"/"origin distance"/"threat"', () => {
    expect(semanticLabels.LABEL_NEAREST_T0_TRIGGER_SOURCE).toBe('Nearest T0 trigger source')
    const lowered = semanticLabels.LABEL_NEAREST_T0_TRIGGER_SOURCE.toLowerCase()
    expect(lowered).not.toContain('outbreak')
    expect(lowered).not.toContain('threat')
  })

  it('the Relative Spatial Score unavailable wording never claims a numeric/qualitative value', () => {
    const lowered = semanticLabels.LABEL_RELATIVE_SPATIAL_SCORE_UNAVAILABLE.toLowerCase()
    for (const forbidden of ['0%', 'low', 'safe', 'green', 'zero']) {
      expect(lowered).not.toContain(forbidden)
    }
  })

  it('the farm marker label is never an outbreak/clinical/risk term', () => {
    const lowered = semanticLabels.LABEL_MY_AREA_FARM_MARKER.toLowerCase()
    for (const forbidden of ['outbreak', 'clinical', 'risk', 'forecast origin']) {
      expect(lowered).not.toContain(forbidden)
    }
  })

  it('none of the My Area status labels contain the bare word "LIVE"', () => {
    const labels = [
      semanticLabels.LABEL_MY_AREA_OPERATIONAL_NOT_CONNECTED,
      semanticLabels.LABEL_MY_AREA_CHOOSE_FARM,
      semanticLabels.LABEL_MY_AREA_LOCATION_REQUIRED,
      semanticLabels.LABEL_MY_AREA_HOST_NOT_CONNECTED,
    ]
    for (const label of labels) {
      expect(label.toUpperCase()).not.toMatch(/\bLIVE\b/)
    }
  })
})

describe('GEO-ANALYSIS-02: Analysis & Trends wording', () => {
  it('the nominal-reach disclaimer used on Page 3 is byte-identical to My Area\'s own required sentence', () => {
    expect(semanticLabels.MY_AREA_NOMINAL_REACH_DISCLAIMER).toBe('Nominal reach — visualization only, not a disease boundary.')
  })

  it('the historical-source-records label never implies a live/active/current count', () => {
    const lowered = semanticLabels.LABEL_HISTORICAL_SOURCE_RECORDS.toLowerCase()
    expect(lowered).not.toContain('active')
    expect(lowered).not.toContain('current')
    expect(lowered).not.toContain('live')
  })

  it('apparent rate is never labelled virus/spread/transmission speed', () => {
    const lowered = semanticLabels.LABEL_ANALYSIS_APPARENT_RATE.toLowerCase()
    expect(lowered).not.toContain('speed')
    expect(lowered).not.toContain('velocity')
  })

  it('origin-level direction unavailable wording never claims a numeric bearing', () => {
    expect(semanticLabels.LABEL_DIRECTION_NOT_DEFINED.toLowerCase()).not.toMatch(/\d+°/)
  })

  it('evidence-availability labels are all explicit "not available" statements, never a placeholder number', () => {
    for (const label of [
      semanticLabels.LABEL_MODEL_EVALUATION_NOT_AVAILABLE,
      semanticLabels.LABEL_CONFIDENCE_NOT_AVAILABLE,
      semanticLabels.LABEL_DRIVERS_NOT_AVAILABLE,
      semanticLabels.LABEL_MODEL_RUN_COMPARISON_NOT_AVAILABLE,
    ]) {
      expect(label).not.toMatch(/^\d/)
      expect(label).not.toContain('%')
      expect(label).not.toBe('0')
      expect(label).not.toBe('—')
    }
  })

  it('none of the Analysis & Trends status labels contain the bare word "LIVE"', () => {
    const labels = [
      semanticLabels.LABEL_ANALYSIS_TRENDS_SESSION_REQUIRED,
      semanticLabels.LABEL_ANALYSIS_TRENDS_FORBIDDEN,
      semanticLabels.LABEL_ANALYSIS_TRENDS_HOST_NOT_CONNECTED,
      semanticLabels.LABEL_ANALYSIS_TRENDS_UNSUPPORTED_DISEASE,
      semanticLabels.LABEL_ANALYSIS_TRENDS_ORIGIN_NOT_FOUND,
      semanticLabels.LABEL_ANALYSIS_TRENDS_INTERNAL_ERROR,
    ]
    for (const label of labels) {
      expect(label.toUpperCase()).not.toMatch(/\bLIVE\b/)
    }
  })

  it('the forbidden list now also rejects the Page-3 fabricated-metric examples', () => {
    expect(semanticLabels.FORBIDDEN_WORDING).toContain('virus speed')
    expect(semanticLabels.FORBIDDEN_WORDING).toContain('top environmental driver')
    expect(semanticLabels.FORBIDDEN_WORDING).toContain('92% accuracy')
    expect(semanticLabels.FORBIDDEN_WORDING).toContain('rainfall 40%')
  })
})

describe('forbidden wording firewall (Part 6)', () => {
  it('no exported user-facing string affirmatively contains any forbidden phrase', () => {
    for (const value of allExportedStrings()) {
      const lowered = value.toLowerCase()
      for (const forbidden of FORBIDDEN_WORDING) {
        assertOnlyNegatedOccurrences(lowered, forbidden)
      }
    }
  })

  it('the forbidden list itself is non-empty and matches the checkpoint spec', () => {
    expect(FORBIDDEN_WORDING).toContain('infection probability')
    expect(FORBIDDEN_WORDING).toContain('confidence score')
    expect(FORBIDDEN_WORDING).toContain('live disease feed')
    expect(FORBIDDEN_WORDING.length).toBeGreaterThanOrEqual(8)
  })
})
