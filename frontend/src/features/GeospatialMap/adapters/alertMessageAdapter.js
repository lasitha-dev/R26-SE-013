/**
 * GEO-LIVE-05 Section 13: deterministic, evidence-backed alert copy for a
 * `VerifiedClinicalEvent` notification. Explicitly NOT an "AI Explainer" --
 * this feature has no LLM/AI-backed explanation concept anywhere in its
 * source (verified read-only, this checkpoint's own audit), so this
 * module invents no such label; every string below is built from real
 * event fields only (Section 13 "Every statement must derive from actual
 * fields ... If evidence cannot support a sentence: omit it"). Never
 * invents probability, confidence, cause, disease direction, risk class,
 * or treatment advice.
 */

import { getDiseaseConfig } from '../disease/diseaseRegistry'

function diseaseLabel(diseaseCode) {
  try {
    return getDiseaseConfig(diseaseCode).label
  } catch {
    return diseaseCode // Section 13: never fabricate a friendlier label for an unrecognized code
  }
}

/**
 * `count`: how many undismissed notifications are currently queued --
 * Section 10's compact banner text ("1 new verified clinical update" /
 * "N new verified clinical updates"). `mostRecentEvent` supplies the
 * "What changed / Why this matters / What should I review" body for the
 * newest one; older queued events are summarized by count alone (Section
 * 10: non-blocking, never a wall of stacked detail).
 */
export function buildAlertBannerTitle(count) {
  if (count <= 0) return ''
  return count === 1 ? '1 new verified clinical update' : `${count} new verified clinical updates`
}

/**
 * Section 13's allowed structure. Any line whose evidence is missing on
 * the event is simply omitted from the returned object (never a guessed
 * placeholder) -- callers should render only the keys that are present.
 */
export function buildAlertExplanation(event) {
  if (!event) return null
  const disease = diseaseLabel(event.disease)
  const explanation = {}

  if (event.disease && event.verified_at) {
    explanation.whatChanged = `A ${disease} case was verified for this farm at ${event.verified_at}.`
  }

  if (event.farm_id) {
    explanation.whyThisMatters = `This farm (${event.farm_id}) is in your assigned area -- verified clinical evidence here may be relevant to what you are currently reviewing.`
  }

  explanation.whatToReview = 'Open the case for details, or dismiss if you have already reviewed it.'

  return explanation
}
