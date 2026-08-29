import React from 'react'

import { buildAlertBannerTitle, buildAlertExplanation } from '../adapters/alertMessageAdapter'

/**
 * GEO-LIVE-05 Section 10/11: the compact, non-blocking alert a vet sees
 * when a new verified clinical event arrives. Deliberately the ONLY thing
 * that changes on the screen when an event arrives -- it never resets the
 * map, calls fitBounds/flyTo, changes the selected disease/outbreak/day,
 * or interrupts timeline playback (Section 10); those are all owned by
 * the page, not this component, and this component itself touches none of
 * them.
 *
 * `onViewUpdate`/`onDismiss` receive the newest notification's `eventId`
 * -- the page decides what "View update" means for its own deep-link
 * semantics (Section 12), this component only renders and delegates.
 */
export default function GeospatialAlertBanner({ notifications, onViewUpdate, onDismiss }) {
  if (!notifications || notifications.length === 0) return null

  const newest = notifications[0]
  const title = buildAlertBannerTitle(notifications.length)
  const explanation = buildAlertExplanation(newest.event)

  return (
    <div
      role="status"
      className="pointer-events-auto flex max-w-sm flex-col gap-1 rounded-lg border border-emerald-400/30 bg-slate-900/90 px-3 py-2 text-xs text-slate-200 shadow-lg backdrop-blur"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium text-emerald-200">{title}</span>
        <button
          type="button"
          onClick={() => onDismiss?.(newest.eventId)}
          aria-label="Dismiss update"
          className="text-slate-400 hover:text-white"
        >
          &times;
        </button>
      </div>

      {explanation?.whatChanged && <p className="text-slate-300">{explanation.whatChanged}</p>}
      {explanation?.whyThisMatters && <p className="text-slate-400">{explanation.whyThisMatters}</p>}

      <div className="mt-1 flex items-center gap-3">
        <button
          type="button"
          onClick={() => onViewUpdate?.(newest.event)}
          className="rounded border border-emerald-300/40 px-2 py-0.5 font-medium text-emerald-100 hover:bg-emerald-400/20"
        >
          View update
        </button>
        <button type="button" onClick={() => onDismiss?.(newest.eventId)} className="text-slate-400 hover:text-slate-200">
          Dismiss
        </button>
      </div>
    </div>
  )
}
