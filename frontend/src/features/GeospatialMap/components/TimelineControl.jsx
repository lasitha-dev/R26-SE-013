import React from 'react'

import { addDaysToIsoDate, forecastDayLabel, formatDisplayDate } from '../adapters/forecastDate'
import { LABEL_FORECAST_RISK_TIMELINE } from '../semanticLabels'

// GEO-UI-TIMELINE-01: the compact per-pill date label, day+month only
// (the always-visible header above already states the full date with
// year for the currently-selected pill, so repeating the year on every
// pill in a tight horizontal row is redundant, not informative). Purely
// a display trim of `formatDisplayDate`'s own real value -- never a
// second date computation.
function shortDisplayDate(isoDate) {
  return formatDisplayDate(isoDate).replace(/\s\d{4}$/, '')
}

/**
 * LSD-UI-04: bottom-docked timeline inside the map (plan Section 23,
 * MSN-style interaction adapted to this domain). Collapsed (not
 * rendered) until an outbreak is selected; shows ONLY the real
 * available day range (`availableDays`, e.g. `[0..7]` for a real
 * origin, never a hardcoded 14/15 -- plan Section 24). Active-day
 * transition ~180-250ms, expand-in ~250-350ms (plan Section 27),
 * skipped entirely under `prefers-reduced-motion`.
 *
 * GEO31A Section 12: a real origin with EXACTLY one available frame
 * (`availableDays.length === 1`) still renders -- as a non-playable
 * "FORECAST RISK · <real date>" status bar, never `null`. Only
 * `availableDays.length === 0` (no outbreak selected at all) hides this
 * control entirely -- `OutbreakMapPage.jsx`'s Cases-mode
 * `ObservedTimelineControl` is the always-visible surface for that case.
 *
 * GEO-UI-TIMELINE-01: the real calendar date (derived from the backend's
 * own `t0`, never the browser clock -- `forecastDate.js`) is now the
 * PRIMARY visible label everywhere in this control; the model's internal
 * `D0`/`D+N` horizon index is demoted to a secondary/tooltip detail. A
 * vet scanning this control must see "this is what date it is", not "this
 * is model-internal horizon math" -- the D-index is still shown (never
 * hidden), just no longer the loudest text on screen.
 */
export default function TimelineControl({
  availableDays,
  selectedDay,
  t0,
  isPlaybackActive,
  onSelectDay,
  onPlay,
  onPause,
  onPrev,
  onNext,
  reduceMotion,
  // GEO-UI-TIMELINE-01: which real model-frame dataset this timeline
  // replays -- mirrors `ObservedTimelineControl`'s own `datasetLabel`
  // prop/pattern. Defaults to Risk Zones, the only mode that currently
  // ever mounts this component (Clusters/Trajectory/Env stay honestly
  // disabled in `ModeToolbar.jsx` -- no real backend output to replay).
  datasetLabel = LABEL_FORECAST_RISK_TIMELINE,
  // GEO-VISUAL-POLISH-01 Section 9: real user-controlled TIMING only --
  // never affects which day/date is shown or how many real frames exist.
  // Optional (both default to a no-op single speed) so every existing
  // caller/test that doesn't pass them keeps rendering exactly as before.
  playbackSpeed = 1,
  onChangeSpeed,
  // GEO-PAGE1-FINAL Section 18/19/41: true while a real origin is
  // already the active focus but its `/summary` (which is what actually
  // supplies `t0`) hasn't resolved yet -- distinct from "no origin
  // focused at all" (still `null`/nothing rendered, exactly as before).
  // Renders a compact, honestly-worded loading dock IN THE SAME dock
  // position instead of vanishing, so a slow scientific fetch (the real,
  // documented backend latency this feature already works around
  // elsewhere) never reads as "the timeline is broken" -- and never as
  // "RECONNECTING", which this feature reserves for the operational
  // push-transport's own real connection health
  // (`StatusDiagnosticsMenu.jsx`), a genuinely different condition.
  // Optional/defaults to `false` so every existing caller/test that
  // omits it renders exactly as before.
  isLoadingFocus = false,
}) {
  // GEO-UI-TIMELINE-01: a REAL pre-existing crash, found while verifying
  // this checkpoint's changes in a live browser -- `outbreakSelectionReducer`'s
  // own initial state already sets `availableForecastFrames: [0]` (so
  // `availableDays.length === 1` is true) before any outbreak is ever
  // selected, but `t0` (`focus.summary?.analysis_metadata?.t0`) is only
  // ever a real value once a real summary has loaded -- it is `undefined`
  // at that exact moment. `addDaysToIsoDate(undefined, ...)` throws
  // (`forecastDate.js`'s own `parseIsoDateUtc` rejects a non-ISO-date
  // input), and this route mounts no error boundary above it, so the
  // exception unmounts the ENTIRE React tree -- including the host
  // VetLayout sidebar/header several levels up. Simply switching to Risk
  // Zones mode before picking an origin was enough to reproduce this.
  // The honest fix is to render nothing here (never a fabricated date
  // for a horizon that has no real origin yet) -- `OutbreakMapPage.jsx`
  // already shows its own "Select a historical outbreak origin..."
  // message elsewhere on the page for exactly this state.
  if (!availableDays || availableDays.length === 0) return null

  // GEO-VISUAL-POLISH-01 Section 7: a compact, dark-glass floating dock --
  // ~80% of the map's width (never the full width, so the map underneath
  // stays visually dominant), tight vertical padding, heavier blur/shadow
  // than the previous flat card.
  const DOCK_CLASS = 'pointer-events-auto w-[82%] max-w-3xl rounded-2xl border border-white/10 bg-slate-900/85 px-4 py-2.5 shadow-[0_20px_50px_-12px_rgba(0,0,0,0.6)] backdrop-blur-xl'

  if (!t0) {
    // GEO-PAGE1-FINAL Section 18: a real origin is focused, its summary
    // (the source of `t0`) simply hasn't arrived yet -- keep the dock
    // slot occupied with an honest, non-alarming status instead of
    // vanishing. `!isLoadingFocus` (no caller opted in, or genuinely no
    // origin is focused at all) preserves the exact prior behavior --
    // render nothing (GEO-UI-TIMELINE-01's own crash-prevention guard).
    if (!isLoadingFocus) return null
    return (
      <div className={DOCK_CLASS} role="status" aria-live="polite" aria-label={`${datasetLabel} timeline`}>
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className={reduceMotion ? 'h-1.5 w-1.5 rounded-full bg-primary' : 'h-1.5 w-1.5 animate-pulse rounded-full bg-primary'} />
          <span className="text-xs font-semibold text-on-surface-variant">Preparing spatial timeline…</span>
        </div>
      </div>
    )
  }

  if (availableDays.length === 1) {
    const onlyDay = availableDays[0]
    const onlyDate = formatDisplayDate(addDaysToIsoDate(t0, onlyDay))
    return (
      <div className={DOCK_CLASS} role="group" aria-label={`${datasetLabel} timeline`}>
        <div className="flex flex-col">
          <span className="text-xs font-semibold uppercase tracking-wide text-on-surface">
            {datasetLabel} · {onlyDate}
          </span>
          <span className="text-[11px] text-on-surface-variant/70" title={`Horizon index: ${forecastDayLabel(onlyDay)}`}>
            {forecastDayLabel(onlyDay)} · {onlyDay === 0 ? 'origin day' : `${onlyDay} day${onlyDay === 1 ? '' : 's'} ahead`}
          </span>
        </div>
      </div>
    )
  }

  const currentIndex = availableDays.indexOf(selectedDay)
  const atStart = currentIndex <= 0
  const atEnd = currentIndex >= availableDays.length - 1
  const selectedDate = formatDisplayDate(addDaysToIsoDate(t0, selectedDay))
  // GEO-VISUAL-POLISH-01: the track-fill's real progress -- how far
  // through the REAL available range the selected day sits, purely
  // presentational (never a second computation of the day itself).
  const progressPct = availableDays.length > 1 ? (currentIndex / (availableDays.length - 1)) * 100 : 0

  return (
    <div
      className={(reduceMotion ? '' : 'animate-[timelineExpand_300ms_ease-out] ') + DOCK_CLASS}
      role="group"
      aria-label={`${datasetLabel} timeline`}
    >
      {/* GEO-UI-TIMELINE-01: an ALWAYS-VISIBLE header naming the real
          dataset and the real selected calendar date -- mirrors
          `ObservedTimelineControl`'s own header so a vet reading either
          bottom timeline sees the same "dataset name · real date"
          language, never a bare row of D0/D+N pills with no date-first
          heading above them. */}
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="shrink-0 text-[11px] font-bold uppercase tracking-wide text-primary">
            {datasetLabel} · {selectedDate}
          </span>
          <span className="truncate text-[11px] text-on-surface-variant/70" title={`Horizon index: ${forecastDayLabel(selectedDay)}`}>
            {forecastDayLabel(selectedDay)} · {selectedDay === 0 ? 'origin day' : `${selectedDay} day${selectedDay === 1 ? '' : 's'} ahead`}
          </span>
        </div>
        {/* GEO-VISUAL-POLISH-01 Section 9: 0.5x/1x/2x -- only rendered
            when the caller actually wires a handler, so every pre-existing
            caller/test that omits it keeps the original header exactly. */}
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
                    ? 'rounded px-1.5 py-0.5 text-[10px] font-bold bg-primary text-on-primary'
                    : 'rounded px-1.5 py-0.5 text-[10px] font-bold text-on-surface-variant/60 hover:text-on-surface'
                }
              >
                {speed}×
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center gap-3">
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onPrev}
            disabled={atStart}
            aria-label="Previous day"
            className="text-on-surface-variant hover:text-on-surface disabled:opacity-30"
          >
            ◀
          </button>
          <button
            type="button"
            onClick={isPlaybackActive ? onPause : onPlay}
            disabled={atEnd && !isPlaybackActive}
            aria-label={isPlaybackActive ? 'Pause' : 'Play'}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary transition-colors hover:brightness-110 disabled:opacity-40"
          >
            {isPlaybackActive ? '❚❚' : '▶'}
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={atEnd}
            aria-label="Next day"
            className="text-on-surface-variant hover:text-on-surface disabled:opacity-30"
          >
            ▶
          </button>
        </div>

        {/* GEO-VISUAL-POLISH-01 Section 7: a thin track line with one
            small node per REAL available day and a larger highlighted
            node for the active one -- replacing the previous plain button
            row with the compact track/thumb look, while every pill stays
            the exact same clickable element with the exact same real
            date/D-index text. */}
        <div className="relative min-w-0 flex-1">
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-1 top-[7px] h-px bg-white/10">
            <div
              className={reduceMotion ? 'h-full bg-primary/60' : 'h-full bg-primary/60 transition-[width] duration-200'}
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <div className="relative flex items-center justify-between gap-0.5 overflow-x-auto">
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
                      ? 'flex shrink-0 flex-col items-center gap-1 rounded-md px-1 py-0.5 text-primary'
                      : 'flex shrink-0 flex-col items-center gap-1 rounded-md px-1 py-0.5 text-on-surface-variant/60 hover:text-on-surface')
                  }
                >
                  <span
                    aria-hidden="true"
                    className={active ? 'h-2.5 w-2.5 rounded-full border-2 border-primary bg-slate-900' : 'h-1.5 w-1.5 rounded-full bg-white/25'}
                  />
                  <span className={active ? 'text-[11px] font-bold' : 'text-[10px] font-semibold'}>{shortDisplayDate(addDaysToIsoDate(t0, day))}</span>
                  <span className="text-[9px] text-on-surface-variant/60">{forecastDayLabel(day)}</span>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
