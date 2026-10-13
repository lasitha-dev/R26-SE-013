import { describe, expect, it } from 'vitest'

import { buildAlertBannerTitle, buildAlertExplanation } from '../adapters/alertMessageAdapter'

const EVENT = { event_id: 'vcc:C1:2026-01-02 10:00:00', case_id: 'C1', farm_id: 'F1', disease: 'LSD', verified_at: '2026-01-02 10:00:00' }

describe('GEO-LIVE-05-EXPLAINER-01: banner title wording', () => {
  it('singular for exactly one queued update', () => {
    expect(buildAlertBannerTitle(1)).toBe('1 new verified clinical update')
  })

  it('plural with count for more than one', () => {
    expect(buildAlertBannerTitle(3)).toBe('3 new verified clinical updates')
  })

  it('empty string for zero (nothing to show)', () => {
    expect(buildAlertBannerTitle(0)).toBe('')
  })
})

describe('GEO-LIVE-05-EXPLAINER-02: deterministic, evidence-backed explanation', () => {
  it('every line derives from real event fields -- no fabricated probability/confidence/cause/risk wording', () => {
    const explanation = buildAlertExplanation(EVENT)
    const serialized = JSON.stringify(explanation)
    for (const forbidden of ['probability', 'confidence', 'risk class', 'treatment', 'cause of', '%']) {
      expect(serialized.toLowerCase()).not.toContain(forbidden)
    }
  })

  it('whatChanged references the real disease label and verification time', () => {
    const explanation = buildAlertExplanation(EVENT)
    expect(explanation.whatChanged).toContain('Lumpy Skin Disease')
    expect(explanation.whatChanged).toContain(EVENT.verified_at)
  })

  it('whyThisMatters references the real farm id, never a different farm', () => {
    const explanation = buildAlertExplanation(EVENT)
    expect(explanation.whyThisMatters).toContain('F1')
  })

  it('returns null for no event -- never fabricates an explanation from nothing', () => {
    expect(buildAlertExplanation(null)).toBeNull()
  })

  it('omits whatChanged when the disease/verified_at evidence is missing, rather than guessing', () => {
    const explanation = buildAlertExplanation({ event_id: 'x', farm_id: 'F1' })
    expect(explanation.whatChanged).toBeUndefined()
  })
})

describe('GEO-LIVE-05-EXPLAINER-03: no "AI Explainer" label on the rendered output (Section 13 audit)', () => {
  it('the banner title and explanation text never claim to be AI-generated -- this feature has no LLM/AI-backed explanation concept', () => {
    const title = buildAlertBannerTitle(2)
    const explanation = buildAlertExplanation(EVENT)
    const rendered = `${title} ${JSON.stringify(explanation)}`
    expect(rendered).not.toMatch(/\bAI\b/)
    expect(rendered.toLowerCase()).not.toContain('artificial intelligence')
  })
})
