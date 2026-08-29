import React from 'react'

import { addDaysToIsoDate, forecastDayLabel, formatDisplayDate } from '../adapters/forecastDate'

/**
 * LSD-UI-04: bottom-docked timeline inside the map (plan Section 23,
 * MSN-style interaction adapted to this domain). Collapsed (not
 * rendered) until an outbreak is selected; shows ONLY the real
 * available day range (`availableDays`, e.g. `[0..7]` for a real
 * origin, never a hardcoded 14/15 -- plan Section 24). Active-day
 * transition ~180-250ms, expand-in ~250-350ms (plan Section 27),
 * skipped entirely under `prefers-reduced-motion`.
 */
export default function TimelineControl({ availableDays, selectedDay, t0, isPlaybackActive, onSelectDay, onPlay, onPause, onPrev, onNext, reduceMotion }) {
  if (!availableDays || availableDays.length <= 1) return null

  const currentIndex = availableDays.indexOf(selectedDay)
  const atStart = currentIndex <= 0
  const atEnd = currentIndex >= availableDays.length - 1

  return (
    <div
      className={
        reduceMotion
          ? 'pointer-events-auto w-full max-w-3xl rounded-xl border border-white/10 bg-slate-900/85 px-4 py-3 shadow-lg backdrop-blur'
          : 'pointer-events-auto w-full max-w-3xl animate-[timelineExpand_300ms_ease-out] rounded-xl border border-white/10 bg-slate-900/85 px-4 py-3 shadow-lg backdrop-blur'
      }
      role="group"
      aria-label="Forecast timeline"
    >
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={isPlaybackActive ? onPause : onPlay}
          disabled={atEnd && !isPlaybackActive}
          aria-label={isPlaybackActive ? 'Pause' : 'Play'}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-400 text-slate-950 transition-colors hover:bg-emerald-300 disabled:opacity-40"
        >
          {isPlaybackActive ? '❚❚' : '▶'}
        </button>
        <button
          type="button"
          onClick={onPrev}
          disabled={atStart}
          aria-label="Previous day"
          className="text-slate-300 hover:text-white disabled:opacity-30"
        >
          ◀
        </button>

        <div className="flex flex-1 items-center justify-between gap-1 overflow-x-auto">
          {availableDays.map((day) => {
            const active = day === selectedDay
            return (
              <button
                key={day}
                type="button"
                onClick={() => onSelectDay(day)}
                aria-current={active ? 'true' : undefined}
                className={
                  (reduceMotion ? '' : 'transition-all duration-200 ') +
                  (active
                    ? 'flex shrink-0 flex-col items-center rounded-md bg-emerald-400/20 px-2 py-1 text-emerald-300'
                    : 'flex shrink-0 flex-col items-center rounded-md px-2 py-1 text-slate-400 hover:text-white')
                }
              >
                <span className="text-xs font-semibold">{forecastDayLabel(day)}</span>
                <span className="text-[10px] text-slate-500">{formatDisplayDate(addDaysToIsoDate(t0, day))}</span>
              </button>
            )
          })}
        </div>

        <button
          type="button"
          onClick={onNext}
          disabled={atEnd}
          aria-label="Next day"
          className="text-slate-300 hover:text-white disabled:opacity-30"
        >
          ▶
        </button>
      </div>
    </div>
  )
}
