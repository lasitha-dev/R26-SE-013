import React from 'react'

import './myAreaChrome.css'
import { formatDisplayDate } from '../adapters/forecastDate'

const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

function shortDate(isoDate) {
  const [, month, day] = String(isoDate).split('-')
  const monthLabel = MONTHS[Number(month) - 1]
  return monthLabel && day ? `${day} ${monthLabel}` : String(isoDate)
}

/** First, Day-7 (end of the D1-D7 reach horizon) and last backend frame. */
function majorLabels(dates) {
  const last = dates.length - 1
  const indexes = [0, Math.min(7, last), last]
  return new Map(indexes.map((index) => [index, shortDate(dates[index])]))
}

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
  onRestartPlayback = null,
  playbackSpeed = 1,
  onPlaybackSpeedChange,
  currentRisk = null,
  horizonStatus = null,
  plateauNote = null,
  disabled = false,
  // Observed case history (Verified Cases mode): real verification dates,
  // never model days -- each step shows its day of month, not a model index.
  observed = false,
  heading = 'Reach horizon',
}) {
  const finalIndex = Math.max(0, dates.length - 1)
  const labels = majorLabels(dates)
  const exploratory = horizonStatus === 'EXPLORATORY_BEYOND_D7_REACH_HORIZON'
  const atStart = activeIndex <= 0
  const atEnd = activeIndex >= finalIndex
  const currentDate = dates[activeIndex]
  // Left/Right step a frame, Home/End jump -- same handler as a click.
  const handleKeyDown = (event) => {
    if (disabled || event.altKey || event.ctrlKey || event.metaKey) return
    const target = { ArrowLeft: activeIndex - 1, ArrowRight: activeIndex + 1, Home: 0, End: finalIndex }[event.key]
    if (target === undefined) return
    event.preventDefault()
    const clamped = Math.max(0, Math.min(finalIndex, target))
    if (clamped !== activeIndex) onSelectIndex(clamped)
  }

  return (
    <div className="my-area-timeline flex min-w-0 flex-col gap-2 rounded-xl border border-primary/20 px-2.5 py-2 shadow-2xl" aria-label={observed ? 'My Area observed case history' : 'My Area spatial risk timeline'} aria-keyshortcuts="ArrowLeft ArrowRight Home End" onKeyDown={handleKeyDown}>
      <div className="flex min-w-0 items-center gap-2">
        <div className="flex shrink-0 items-center gap-1">
          <ControlButton label="Previous area forecast date" icon="skip_previous" onClick={() => onSelectIndex(activeIndex - 1)} disabled={disabled || atStart} />
          <ControlButton
            label={isPlaying ? 'Pause area forecast playback' : atEnd && onRestartPlayback ? 'Restart area forecast playback' : atEnd ? `Timeline complete at ${dates[finalIndex] ? formatDisplayDate(dates[finalIndex]) : 'final frame'}` : 'Play area forecast playback'}
            icon={isPlaying ? 'pause' : atEnd && onRestartPlayback ? 'replay' : 'play_arrow'}
            onClick={atEnd && onRestartPlayback ? onRestartPlayback : onTogglePlayback}
            disabled={disabled || (atEnd && !onRestartPlayback)}
            pressed={isPlaying}
          />
          <ControlButton label="Next area forecast date" icon="skip_next" onClick={() => onSelectIndex(activeIndex + 1)} disabled={disabled || atEnd} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2 px-1">
            <div className="truncate text-[10px] font-semibold uppercase tracking-[0.12em] text-primary">{heading} - {currentDate ? formatDisplayDate(currentDate) : 'Date unavailable'}</div>
            <div className="flex shrink-0 items-center gap-1.5">
              {plateauNote && <span className="hidden rounded border border-teal-300/35 px-1 text-[8px] font-bold uppercase tracking-wide text-teal-200 md:inline" title="The nominal reach now extends past the scored 25 km source area, so later days draw the same backend risk zones. The reach distance itself keeps growing.">{plateauNote}</span>}
              {exploratory && <span className="rounded border border-amber-400/40 px-1 text-[8px] font-bold uppercase tracking-wide text-amber-300" title="Days 8-14 extend the Day 1-7 reach formula">Exploratory</span>}
              {currentRisk && <div className="text-[9px] font-semibold uppercase tracking-wide text-on-surface-variant">{currentRisk} within reach</div>}
            </div>
          </div>
          <div className="mt-1 grid gap-0.5" style={{ gridTemplateColumns: `repeat(${Math.max(1, dates.length)}, minmax(0, 1fr))` }} role="group" aria-label="Timeline dates">
            {dates.map((date, index) => {
              const active = index === activeIndex
              const majorLabel = labels.get(index)
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
                    {/* Day of month: the real date, never a "D0/D1" index. */}
                    {String(date).slice(8, 10)}
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
