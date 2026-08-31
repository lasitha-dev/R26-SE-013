/**
 * GEO-LIVE-FINAL-PROOF-09: pure, framework-free case-IDENTITY
 * reconciliation -- extracted from `pages/OutbreakMapPage.jsx`'s
 * reconciliation-diff effect (same behavior, now independently
 * unit-testable in this repo's Node-only Vitest environment, matching
 * this feature's dominant pure-function-first pattern).
 *
 * Diffs the real backend case entity identity (`caseId`, never a
 * transport/event id -- see `context/operationalEventsReducer.js`'s
 * `EVENT_TYPE` docstring for why those are NOT the same thing) against
 * the previously known verification time per case, classifying each
 * CURRENTLY PRESENT case as NEW or CHANGED. "Changed" mirrors the
 * backend's own change-detection field exactly
 * (`event_stream_service.py`'s `_reconciliation_changes`: same case_id,
 * different `verified_at`).
 *
 * Never invents deletion semantics: a case's disappearance from
 * `currentContexts` is never classified here -- callers rebuild the
 * FeatureCollection fresh from whatever the current authoritative
 * snapshot contains, exactly as this feature always has.
 */

/** `Map<caseId, verificationTime>` snapshot of a context list, for the
 * caller to retain as "what was last seen" ahead of the next diff. */
export function verificationByCaseId(contexts) {
  return new Map(contexts.map((c) => [c.caseId, c.verificationTime]))
}

/**
 * `previousVerificationByCaseId` is a `Map<caseId, verificationTime>`
 * from a prior call to `verificationByCaseId` (or `null`/`undefined` for
 * "no baseline yet" -- the caller decides what to do with that; this
 * function itself always classifies against whatever map it is given).
 *
 * Returns `{ newCases, changedCases }`, each a plain array of the real
 * context objects from `currentContexts` (never a fabricated/partial
 * record) in their original order. A case present in both, with the SAME
 * `verificationTime`, appears in neither array (UNCHANGED).
 */
export function classifyOperationalCaseChanges(previousVerificationByCaseId, currentContexts) {
  const previous = previousVerificationByCaseId ?? new Map()
  const newCases = []
  const changedCases = []
  for (const context of currentContexts) {
    if (!previous.has(context.caseId)) {
      newCases.push(context)
    } else if (previous.get(context.caseId) !== context.verificationTime) {
      changedCases.push(context)
    }
  }
  return { newCases, changedCases }
}
