import React from 'react'

import { addDaysToIsoDate, forecastDayLabel, formatDisplayDate } from '../adapters/forecastDate'
import { LABEL_FORECAST_D0 } from '../semanticLabels'

/**
 * GEO-AREA-02 Section 19: a compact D0-D+7 strip -- deliberately NOT a
 * reuse of `TimelineControl.jsx` (that component is wired to Page 1's
 * playback semantics -- `isPlaybackActive`/`onPlay`/`onPause` -- which
 * have no meaning here; My Area has no playback, only a day picker).
 *
 * Section 19/45: D+N calendar labels use the EXISTING tested
 * `forecastDate.js::addDaysToIsoDate(t0, day)` -- never the browser's own
 * current-moment clock, and never a second date-arithmetic
 * implementation. `t0` must be the real `SelectedOriginContext.t0`; if
 * it is not yet available (no origin selected), only day numbers are
 * shown, never a guessed date.
 */
export default function MyAreaForecastStrip({ selectedDay, onSelectDay, t0 = null, disabled = false }) {
  const days = [0, 1, 2, 3, 4, 5, 6, 7]

  return (
    <div className="flex items-center gap-1 overflow-x-auto rounded-lg border border-white/10 bg-slate-900/70 p-1.5" role="group" aria-label="Forecast day">
      {days.map((day) => {
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
                ? 'flex shrink-0 flex-col items-center rounded-md bg-emerald-400/20 px-2.5 py-1 text-emerald-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 disabled:cursor-not-allowed disabled:opacity-40'
                : 'flex shrink-0 flex-col items-center rounded-md px-2.5 py-1 text-slate-300 hover:bg-slate-800 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 disabled:cursor-not-allowed disabled:opacity-40'
            }
          >
            <span className="font-mono text-xs font-medium">{forecastDayLabel(day)}</span>
            {dateLabel && <span className="text-[10px] text-slate-500">{dateLabel}</span>}
          </button>
        )
      })}
    </div>
  )
}
