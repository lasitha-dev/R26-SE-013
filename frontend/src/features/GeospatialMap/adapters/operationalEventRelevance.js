/**
 * GEO-LIVE-05 Section 9/10: pure relevance decisions for a
 * `VerifiedClinicalEvent` -- kept out of the pages themselves so "does
 * this event matter to what I'm currently looking at" is independently
 * unit-testable without rendering `OutbreakMapPage.jsx`/`MyAreaPage.jsx`.
 *
 * Page 1 always refetches on ANY authorized event (its marker layer
 * already filters by the currently-selected disease downstream -- Section
 * 9 "Page 1: refetch operational-context, update Verified Clinical
 * Context marker layer", unconditionally), so there is no Page-1-specific
 * relevance function here.
 */

/**
 * Section 9 "Page 2: if event disease/farm is relevant to current
 * authorized context, refetch My Area operational context" -- relevant
 * only when the event's farm IS the vet's currently selected farm. An
 * event for a farm the vet is assigned but has not selected must not
 * trigger a refetch of a DIFFERENT farm's on-screen context.
 */
export function isEventRelevantToMyArea(event, { selectedAreaId } = {}) {
  if (!event || !selectedAreaId) return false
  return event.farm_id === selectedAreaId
}
