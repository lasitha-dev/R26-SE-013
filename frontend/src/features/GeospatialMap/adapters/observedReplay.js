/**
 * GEO31A Section 5/6/13: Cases-mode "Observed Replay" -- pure functions
 * only, no hook/component code (matches this codebase's convention of
 * keeping timeline/date-derivation logic independently unit-testable,
 * see `observationWindow.js`).
 *
 * Section 6: "Build replay dates ONLY from real event timestamps... Do
 * not generate arbitrary dates between events." `buildObservedReplayDates`
 * derives its dates EXCLUSIVELY from each real context's own
 * `verificationTime` -- it never interpolates, pads, or invents a day
 * that no real verified case actually has.
 *
 * Section 7/13: this is entirely independent of the SCIENTIFIC D0/D+N
 * timeline (`useSelectedOutbreakFrames.js`/`TimelineControl.jsx`) and of
 * the camera/location scope (Sri Lanka vs My District) -- it operates
 * purely on whatever `clinicalContexts` the caller already resolved
 * (disease + observation-window filtered), never on farm/district
 * selection itself.
 */
import { parseVerificationTime } from './verificationTime'

function toDateKey(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/**
 * Returns every distinct real verification DATE (day granularity, local
 * time -- matching `observationWindow.js`'s own day-boundary convention)
 * present in `clinicalContexts`, ascending, as `YYYY-MM-DD` strings.
 * A context with a missing/unparseable `verificationTime` is silently
 * excluded (never treated as "today" or "oldest") -- mirrors
 * `isWithinObservationWindow`'s own null-handling.
 */
export function buildObservedReplayDates(clinicalContexts) {
  const seen = new Set()
  for (const context of clinicalContexts ?? []) {
    const date = parseVerificationTime(context?.verificationTime)
    if (date) seen.add(toDateKey(date))
  }
  return Array.from(seen).sort()
}

/**
 * Section 6: "At replay date Aug 24: only records observed by Aug 24
 * appear." A context is "revealed" at `replayDateKey` when its own real
 * verification date is on or before that date -- never a future one.
 * `replayDateKey` of `null`/`undefined` means "no replay in progress",
 * which callers should treat as "everything in the current window is
 * revealed" (this function is not consulted at all in that case).
 */
export function isRevealedByReplayDate(verificationTime, replayDateKey) {
  if (!replayDateKey) return true
  const date = parseVerificationTime(verificationTime)
  if (!date) return false
  return toDateKey(date) <= replayDateKey
}

/** Pure filter: keeps only contexts revealed by `replayDateKey` (or all of
 * them, unfiltered, when `replayDateKey` is nullish -- "at latest"). */
export function filterContextsByReplayDate(clinicalContexts, replayDateKey) {
  if (!replayDateKey) return clinicalContexts ?? []
  return (clinicalContexts ?? []).filter((c) => isRevealedByReplayDate(c?.verificationTime, replayDateKey))
}
