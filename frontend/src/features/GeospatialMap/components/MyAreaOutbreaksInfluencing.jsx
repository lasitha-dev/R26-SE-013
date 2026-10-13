import React from 'react'

import './myAreaChrome.css'
import {
  LABEL_BADGE_NEAREST_TRIGGER_SOURCE,
  LABEL_BADGE_RELEVANT_HISTORICAL_ORIGIN,
  LABEL_DISTANCE_FROM_AREA,
  LABEL_MY_AREA_NO_RELEVANT_ORIGINS,
  LABEL_MY_AREA_SELECT_ORIGIN,
  LABEL_NEAREST_T0_TRIGGER_SOURCE,
} from '../semanticLabels'

/**
 * GEO-MY-AREA-VISUAL-QA-REBUILD: "Outbreaks influencing my area" -- the
 * same real `relevantOrigins` list `MyAreaSummaryPanel.jsx` already
 * rendered, in the reference composition's row-card visual language.
 * Badges are derived ONLY from the real `distanceBasis` field the backend
 * already returns -- never the screenshot's "TRAJECTORY INTERSECTS AREA"/
 * "NEARBY ACTIVE CLUSTER" wording, since neither trajectory nor clustering
 * has a current Page runtime/API contract (`diseaseRegistry.js`).
 *
 * GEO-MY-AREA-LAYOUT-BALANCE (recalibrated -- rendered QA against a real
 * 5-origin payload proved the ORIGINAL 320px cap never actually
 * triggered: 5 real rows at their natural ~52-56px height plus gaps
 * total only ~290-300px, comfortably UNDER a 320px cap, so
 * `scrollHeight <= clientHeight` and the list just rendered at its full
 * natural size -- functionally motionless despite `overflow-y: auto`
 * being genuinely present and correct. The fix is a smaller viewport
 * (`lg:max-h-[260px]`, matched by the card's own `lg:max-h-[380px]`),
 * deliberately sized to show ~4 rows before scrolling is REQUIRED, so
 * the ONE deliberate internal scroll region on desktop (Section 2/13 of
 * the rebalance) actually engages for realistic 5/10/20-origin data
 * instead of only becoming visible past some much larger, rarely-hit
 * count. `overscroll-contain` on the list still ensures an exhausted
 * scroll never chains into the page underneath.
 *
 * Below `lg:` the cap/scroll is deliberately OFF (no `max-h`, no
 * `overflow-y-auto`): the RESPONSIVE contract explicitly calls for
 * "avoid small nested scroll regions if normal page scroll is better" on
 * tablet/mobile, where there is no sticky right-column panel competing
 * for vertical space in the first place -- the list just grows with the
 * page's own normal scroll there instead.
 *
 * `tabIndex={0}` makes the list itself a real keyboard-reachable scroll
 * target (Tab lands on it directly; arrow/Page/Home/End then scroll it
 * per every major browser's native behavior for a focused, overflowing
 * element) -- without it, a keyboard-only user had no way to reach this
 * region's scroll at all except by tabbing into one of its own "View on
 * map" buttons first.
 */
export default function MyAreaOutbreaksInfluencing({ relevantOrigins, selectedOriginId, onSelectOrigin }) {
  return (
    <div className="flex flex-col overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container/70 shadow-card-subtle lg:max-h-[380px]">
      <div className="shrink-0 p-4 pb-2">
        <div className="text-sm font-semibold text-on-surface">Outbreaks influencing my area</div>
        <div className="mt-0.5 text-[10.5px] text-on-surface-variant/60">
          Only genuinely available relevance is shown -- distance and origin type are not a model-computed confidence value.
        </div>
      </div>

      {relevantOrigins.length === 0 ? (
        <div className="px-4 pb-4 text-xs text-on-surface-variant">{LABEL_MY_AREA_NO_RELEVANT_ORIGINS}</div>
      ) : (
        <ul
          className="my-area-scroll flex min-h-0 flex-col gap-2 overscroll-contain px-4 pb-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary lg:max-h-[260px] lg:overflow-y-auto"
          role="list"
          aria-label="Outbreaks influencing my area"
          tabIndex={0}
        >
          {relevantOrigins.map((origin) => {
            const active = origin.originId === selectedOriginId
            const badge = origin.distanceBasis === 'NEAREST_T0_TRIGGER_SOURCE' ? LABEL_BADGE_NEAREST_TRIGGER_SOURCE : LABEL_BADGE_RELEVANT_HISTORICAL_ORIGIN
            const distanceLabel = origin.distanceBasis === 'NEAREST_T0_TRIGGER_SOURCE' ? LABEL_NEAREST_T0_TRIGGER_SOURCE : LABEL_DISTANCE_FROM_AREA
            return (
              <li
                key={origin.originId}
                className={active ? 'shrink-0 rounded-lg border border-primary/40 bg-primary/10 px-2.5 py-2' : 'shrink-0 rounded-lg border border-outline-variant/20 bg-surface-container-lowest/40 px-2.5 py-2'}
              >
                {/* GEO-MY-AREA-LAYOUT-BALANCE: `flex-nowrap` + a shrinkable
                    (`min-w-0 flex-1`) left segment -- not `flex-wrap` --
                    so a real origin ID/badge combination longer than the
                    mock's short "FMD-024" can never wrap this row onto a
                    3rd/4th line and inflate its height past the ~58-72px
                    target; the id itself still truncates with a full-value
                    `title` tooltip, it just never grows the row. */}
                <div className="flex flex-nowrap items-center justify-between gap-1.5">
                  <div className="flex min-w-0 flex-1 items-center gap-1.5">
                    <span className="truncate font-mono text-[11px] font-semibold text-on-surface" title={origin.originId}>
                      {origin.originId}
                    </span>
                    <span className="shrink-0 rounded-full border border-outline-variant/30 px-1.5 py-0.5 text-[9.5px] text-on-surface-variant">{origin.disease}</span>
                  </div>
                  <span className="shrink-0 rounded-full border border-primary/30 bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold tracking-wide text-primary">{badge}</span>
                </div>
                <div className="mt-1 flex flex-nowrap items-center justify-between gap-1.5">
                  <div className="min-w-0 flex-1 truncate text-[10.5px] text-on-surface-variant" title={origin.scientificMode ?? undefined}>
                    {origin.t0 && <span>t0: {origin.t0} · </span>}
                    <span>{distanceLabel}: {origin.distanceFromAreaKm.toFixed(1)} km</span>
                    {origin.scientificMode && <span className="text-on-surface-variant/50"> · {origin.scientificMode}</span>}
                  </div>
                  <button
                    type="button"
                    onClick={() => onSelectOrigin(origin.originId)}
                    aria-pressed={active}
                    className="shrink-0 text-[10.5px] font-medium text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    {active ? 'Selected on map' : 'View on map →'}
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
      {relevantOrigins.length > 0 && !selectedOriginId && (
        <div className="shrink-0 border-t border-outline-variant/10 px-4 py-2 text-[10.5px] text-on-surface-variant/70">{LABEL_MY_AREA_SELECT_ORIGIN}</div>
      )}
    </div>
  )
}
