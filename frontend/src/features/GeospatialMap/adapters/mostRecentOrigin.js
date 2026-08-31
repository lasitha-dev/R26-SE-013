/**
 * GEO-PAGE1-FINAL Section 24: "choose the most recent real eligible
 * outbreak deterministically as the default scientific focus" -- pure,
 * framework-free selection over whatever real origins
 * `useNationalOutbreaks.js` has resolved so far. Never invents an origin;
 * an empty/undefined list simply has no default focus yet.
 *
 * `t0` is the real ISO `YYYY-MM-DD` date string every origin already
 * carries (`services/forecast_origin.py`'s `ForecastOrigin.t0`) -- plain
 * string comparison is a correct chronological ordering for that format
 * (no Date parsing needed, and none of the timezone ambiguity Date
 * parsing would introduce).
 *
 * Ties (two real origins sharing the exact same real t0 -- e.g. distinct
 * countries triggered the same day) are broken by `outbreakId` so the
 * choice is still deterministic and reproducible across renders, never
 * "whichever happened to resolve last over the network".
 */
export function selectMostRecentOrigin(originsWithSources) {
  if (!originsWithSources || originsWithSources.length === 0) return null
  return originsWithSources.reduce((best, origin) => {
    if (!best) return origin
    if (origin.t0 > best.t0) return origin
    if (origin.t0 === best.t0 && origin.outbreakId > best.outbreakId) return origin
    return best
  }, null)
}
