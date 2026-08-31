import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'
import { LABEL_OBSERVED_AT_LATEST, LABEL_OBSERVED_CASES_TIMELINE, LABEL_OBSERVED_TIMELINE_PREFIX } from '../semanticLabels'

/**
 * GEO31A Section 5/6/13/18: the Cases-mode "Observed Timeline/status"
 * surface -- ALWAYS present while Cases mode is active (never removed
 * just because the current window/district has zero verified events,
 * Section 5's explicit requirement), entirely independent of the
 * scientific D0/D+N `TimelineControl.jsx` (Section 7/13: never derives
 * from, or is derived by, that control or by the Sri-Lanka/My-District
 * camera scope).
 *
 * `dates` are real `YYYY-MM-DD` keys built ONLY from real verification
 * timestamps (`adapters/observedReplay.js::buildObservedReplayDates`) --
 * this component never invents a tick between two real dates.
 */
export default function ObservedTimelineControl({
  dates,
  selectedDateKey,
  isPlaybackActive,
  onSelectDate,
  onPlay,
  onPause,
  onPrev,
  onNext,
  windowLabel,
  emptyStateText,
  reduceMotion,
  // GEO33B Section 10: which real dataset this timeline is replaying.
  // Defaults to the verified-clinical ("Observed cases") replay, which is
  // what `OutbreakMapPage.jsx` actually wires in Cases mode -- never
  // "Forecast", and never a value that would let the national
  // historical/scientific dataset and the authorized clinical dataset be
  // presented under one ambiguous heading.
  datasetLabel = LABEL_OBSERVED_CASES_TIMELINE,
  // GEO-VISUAL-POLISH-01 Section 9: real user-controlled TIMING only --
  // optional, defaulting to a no-op single speed, so any existing caller/
  // test that omits it keeps rendering exactly as before.
  playbackSpeed = 1,
  onChangeSpeed,
}) {
  const hasDates = Array.isArray(dates) && dates.length > 0
  const currentIndex = hasDates ? (selectedDateKey ? dates.indexOf(selectedDateKey) : dates.length - 1) : -1
  const atStart = currentIndex <= 0
  const atEnd = currentIndex >= dates.length - 1
  const playDisabled = !hasDates || dates.length <= 1
  // The real date currently being replayed. "At latest" (no scrub in
  // progress) is stated as exactly that -- never rendered as today's date,
  // which would be a fabricated observation date.
  const activeDateKey = hasDates ? (selectedDateKey ?? dates[dates.length - 1]) : null
  // GEO-VISUAL-POLISH-01: the track-fill's real progress through the REAL
  // available dates -- purely presentational.
  const progressPct = hasDates && dates.length > 1 ? (currentIndex / (dates.length - 1)) * 100 : 0

  return (
    <div
      className={
        (reduceMotion ? '' : 'animate-[timelineExpand_300ms_ease-out] ') +
        'pointer-events-auto w-[82%] max-w-3xl rounded-2xl border border-white/10 bg-slate-900/85 px-4 py-2.5 shadow-[0_20px_50px_-12px_rgba(0,0,0,0.6)] backdrop-blur-xl'
      }
      role="group"
      aria-label={`${datasetLabel} timeline`}
    >
      {/* GEO33B Section 10: an ALWAYS-VISIBLE header naming the real
          dataset, the real date being replayed, and the real observation
          window. Previously a header only existed in the zero-events
          branch below, so the common case (real date pills rendered) gave
          a vet a row of bare dates with nothing saying what they were
          dates OF -- indistinguishable at a glance from the scientific
          D0/D+N forecast timeline that occupies the same screen position
          in other modes. */}
      {hasDates && (
        <div className="mb-1.5 flex items-baseline justify-between gap-2">
          <div className="flex min-w-0 items-baseline gap-2">
            <span className="shrink-0 text-[11px] font-bold uppercase tracking-wide text-red-300">
              {datasetLabel} · {activeDateKey ? formatDisplayDate(activeDateKey) : LABEL_OBSERVED_AT_LATEST}
            </span>
            <span className="truncate text-[11px] text-on-surface-variant/70">
              {selectedDateKey ? `${LABEL_OBSERVED_TIMELINE_PREFIX} · ${windowLabel}` : `${LABEL_OBSERVED_AT_LATEST} · ${windowLabel}`}
            </span>
          </div>
          {onChangeSpeed && (
            <div
              className="flex shrink-0 items-center gap-0.5 rounded-md border border-white/10 bg-black/25 p-0.5"
              role="group"
              aria-label="Playback speed"
            >
              {[0.5, 1, 2].map((speed) => (
                <button
                  key={speed}
                  type="button"
                  onClick={() => onChangeSpeed(speed)}
                  aria-pressed={playbackSpeed === speed}
                  className={
                    playbackSpeed === speed
                      ? 'rounded px-1.5 py-0.5 text-[10px] font-bold bg-red-400 text-slate-950'
                      : 'rounded px-1.5 py-0.5 text-[10px] font-bold text-on-surface-variant/60 hover:text-on-surface'
                  }
                >
                  {speed}×
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="flex items-center gap-3">
        <div className="flex shrink-0 items-center gap-2">
          {hasDates && (
            <button
              type="button"
              onClick={onPrev}
              disabled={atStart}
              aria-label="Previous observed date"
              className="text-on-surface-variant hover:text-on-surface disabled:opacity-30"
            >
              ◀
            </button>
          )}
          <button
            type="button"
            onClick={isPlaybackActive ? onPause : onPlay}
            disabled={playDisabled && !isPlaybackActive}
            aria-label={isPlaybackActive ? 'Pause' : 'Play'}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-400 text-slate-950 transition-colors hover:bg-red-300 disabled:opacity-40"
          >
            {isPlaybackActive ? '❚❚' : '▶'}
          </button>
          {hasDates && (
            <button
              type="button"
              onClick={onNext}
              disabled={atEnd}
              aria-label="Next observed date"
              className="text-on-surface-variant hover:text-on-surface disabled:opacity-30"
            >
              ▶
            </button>
          )}
        </div>

        {hasDates ? (
          // GEO-VISUAL-POLISH-01 Section 7: the same thin track + node
          // treatment as the scientific `TimelineControl` -- one small
          // node per real observed date, a larger highlighted node for the
          // active one. Every pill is still the exact same clickable
          // element carrying the exact same real date text.
          <div className="relative min-w-0 flex-1">
            <div aria-hidden="true" className="pointer-events-none absolute inset-x-1 top-[7px] h-px bg-white/10">
              <div
                className={reduceMotion ? 'h-full bg-red-400/60' : 'h-full bg-red-400/60 transition-[width] duration-200'}
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <div className="relative flex items-center justify-between gap-0.5 overflow-x-auto">
              {dates.map((dateKey, index) => {
                const active = index === currentIndex
                return (
                  <button
                    key={dateKey}
                    type="button"
                    onClick={() => onSelectDate(dateKey)}
                    aria-current={active ? 'true' : undefined}
                    className={
                      (reduceMotion ? '' : 'transition-all duration-200 ') +
                      (active
                        ? 'flex shrink-0 flex-col items-center gap-1 rounded-md px-1 py-0.5 text-red-300'
                        : 'flex shrink-0 flex-col items-center gap-1 rounded-md px-1 py-0.5 text-on-surface-variant/60 hover:text-on-surface')
                    }
                  >
                    <span
                      aria-hidden="true"
                      className={active ? 'h-2.5 w-2.5 rounded-full border-2 border-red-300 bg-slate-900' : 'h-1.5 w-1.5 rounded-full bg-white/25'}
                    />
                    <span className={active ? 'text-[11px] font-bold' : 'text-[10px] font-semibold'}>{formatDisplayDate(dateKey)}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ) : (
          <div className="flex flex-1 flex-col overflow-hidden">
            {/* GEO33B Section 10: names the real dataset here too, so the
                zero-events state is just as unambiguous as the populated
                one -- "Observed cases", never a bare "Observed". */}
            <span className="text-[11px] font-semibold uppercase tracking-wide text-on-surface-variant/70">
              {datasetLabel} · {windowLabel}
            </span>
            <span className="truncate text-xs text-on-surface-variant">{emptyStateText}</span>
          </div>
        )}
      </div>
    </div>
  )
}
