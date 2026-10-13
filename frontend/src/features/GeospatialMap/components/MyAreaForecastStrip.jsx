import React from 'react'

import { addDaysToIsoDate, forecastDayLabel, formatDisplayDate } from '../adapters/forecastDate'
import { LABEL_FORECAST_D0 } from '../semanticLabels'

/**
 * GEO-AREA-02 Section 19: a compact local forecast-day strip --
 * deliberately NOT a reuse of `TimelineControl.jsx` (that component is
 * wired to Page 1's playback semantics -- `isPlaybackActive`/`onPlay`/
 * `onPause` -- which have no meaning here; My Area has no playback, only
 * a day picker).
 *
 * Section 19/45: D+N calendar labels use the EXISTING tested
 * `forecastDate.js::addDaysToIsoDate(t0, day)` -- never the browser's own
 * current-moment clock, and never a second date-arithmetic
 * implementation. `t0` must be the real `SelectedOriginContext.t0`; if
 * it is not yet available (no origin selected), only day numbers are
 * shown, never a guessed date.
 *
 * GEO-MY-AREA-STITCH-16: `availableDays` replaces a previously hardcoded
 * `[0..7]` -- the real per-origin horizon (`deriveAvailableForecastDays`,
 * the same adapter Page 1's `TimelineControl` uses over the origin's own
 * real `nominal_reach_by_day`) is passed in by `MyAreaPage.jsx` instead,
 * so this never offers a day the selected origin does not genuinely have
 * a real frame for. `disabled` still covers the "no origin selected yet"
 * shell state (no data implied either way); once an origin IS selected
 * but its real horizon is D0-only (or the disease has no forecast
 * capability at all -- FMD), `availableDays.length <= 1` and this renders
 * the honest static state instead of a dead multi-day control.
 */
export default function MyAreaForecastStrip({ selectedDay, onSelectDay, t0 = null, availableDays = [0], disabled = false }) {
  if (availableDays.length <= 1) {
    return (
      <div className="rounded-lg border border-outline-variant/30 bg-surface-container/90 px-3 py-2 text-xs text-on-surface-variant/70" role="status">
        No time-varying local forecast is available for this selection.
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1 overflow-x-auto rounded-lg border border-outline-variant/30 bg-surface-container/90 p-1.5" role="group" aria-label="Forecast day">
      {availableDays.map((day) => {
        const active = day === selectedDay
        const dateLabel = t0 ? formatDisplayDate(addDaysToIsoDate(t0, day)) : null
        return (
          <button
            key={day}
            type="button"
            disabled={disabled}
            aria-pressed={active}
            title={day === 0 ? LABEL_FORECAST_D0 : dateLabel ?? undefined}
            onClick={() => onSelectDay(day)}
            className={
              active
                ? 'flex shrink-0 flex-col items-center rounded-md bg-primary/20 px-2.5 py-1 text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-40'
                : 'flex shrink-0 flex-col items-center rounded-md px-2.5 py-1 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-40'
            }
          >
            <span className="font-mono text-xs font-medium">{forecastDayLabel(day)}</span>
            {dateLabel && <span className="text-[10px] text-on-surface-variant/70">{dateLabel}</span>}
          </button>
        )
      })}
    </div>
  )
}
