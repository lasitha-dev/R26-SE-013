import React from 'react'

import './myAreaChrome.css'
import { formatDisplayDate } from '../adapters/forecastDate'

const MAJOR_LABELS = new Map([
  [0, '01 SEP'],
  [6, '07 SEP'],
  [13, '14 SEP'],
])

function ControlButton({ label, icon, onClick, disabled = false, pressed }) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
      className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-on-surface transition hover:border-primary/40 hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-30"
    >
      <span aria-hidden="true" className="material-symbols-outlined text-[18px]">{icon}</span>
    </button>
  )
}

/** Compact Page-2 master timeline. Dates and activeIndex are controlled
 * entirely by MyAreaPage; this component owns no secondary clock. */
export default function MyAreaForecastStrip({
  dates = [],
  activeIndex = 0,
  onSelectIndex,
  isPlaying,
  onTogglePlayback,
  playbackSpeed = 1,
  onPlaybackSpeedChange,
  currentRisk = null,
  disabled = false,
}) {
  const finalIndex = Math.max(0, dates.length - 1)
  const atStart = activeIndex <= 0
  const atEnd = activeIndex >= finalIndex
  const currentDate = dates[activeIndex]

  return (
    <div className="my-area-timeline flex min-w-0 flex-col gap-2 rounded-xl border border-primary/20 px-2.5 py-2 shadow-2xl" aria-label="My Area Sep 01 to Sep 14 forecast timeline">
      <div className="flex min-w-0 items-center gap-2">
        <div className="flex shrink-0 items-center gap-1">
          <ControlButton label="Previous area forecast date" icon="skip_previous" onClick={() => onSelectIndex(activeIndex - 1)} disabled={disabled || atStart} />
          <ControlButton
            label={isPlaying ? 'Pause area forecast playback' : atEnd ? 'Forecast complete at 14 Sep 2026' : 'Play area forecast playback'}
            icon={isPlaying ? 'pause' : 'play_arrow'}
            onClick={onTogglePlayback}
            disabled={disabled || atEnd}
            pressed={isPlaying}
          />
          <ControlButton label="Next area forecast date" icon="skip_next" onClick={() => onSelectIndex(activeIndex + 1)} disabled={disabled || atEnd} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2 px-1">
            <div className="truncate text-[10px] font-semibold uppercase tracking-[0.12em] text-primary">Future impact - {currentDate ? formatDisplayDate(currentDate) : 'Date unavailable'}</div>
            {currentRisk && <div className="shrink-0 text-[9px] font-semibold uppercase tracking-wide text-on-surface-variant">{currentRisk} district risk</div>}
          </div>
          <div className="mt-1 grid gap-0.5" style={{ gridTemplateColumns: 'repeat(14, minmax(0, 1fr))' }} role="group" aria-label="Sep 01 to Sep 14 dates">
            {dates.map((date, index) => {
              const active = index === activeIndex
              const majorLabel = MAJOR_LABELS.get(index)
              return (
                <button
                  key={date}
                  type="button"
                  disabled={disabled}
                  aria-label={`Select ${formatDisplayDate(date)}`}
                  aria-current={active ? 'date' : undefined}
                  onClick={() => onSelectIndex(index)}
                  className="group flex min-w-0 flex-col items-center gap-0.5 rounded py-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed"
                >
                  <span className={active ? 'grid h-4 w-4 place-items-center rounded-full border border-white bg-primary text-[8px] font-bold text-slate-950 shadow-[0_0_10px_rgba(78,222,163,0.6)]' : 'grid h-4 w-4 place-items-center rounded-full border border-white/15 bg-slate-700/80 text-[8px] font-semibold text-slate-300 transition group-hover:border-primary/60'}>
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className={active ? 'whitespace-nowrap text-[7px] font-bold text-primary' : 'whitespace-nowrap text-[7px] font-semibold text-on-surface-variant/55'}>{majorLabel ?? '\u00a0'}</span>
                </button>
              )
            })}
          </div>
        </div>

        <div className="hidden shrink-0 items-center gap-0.5 sm:flex" role="group" aria-label="Area forecast playback speed">
          {[0.5, 1, 2].map((speed) => (
            <button
              key={speed}
              type="button"
              disabled={disabled}
              aria-pressed={playbackSpeed === speed}
              onClick={() => onPlaybackSpeedChange(speed)}
              className={playbackSpeed === speed ? 'rounded-md bg-primary px-1.5 py-1 text-[9px] font-bold text-slate-950' : 'rounded-md px-1.5 py-1 text-[9px] font-semibold text-on-surface-variant hover:bg-white/[0.06] hover:text-on-surface'}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
