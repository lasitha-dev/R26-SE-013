import React from 'react'

import { AREA_RISK_COLORS } from '../adapters/myAreaPresentationForecast'
import { formatDisplayDate } from '../adapters/forecastDate'

const RISK_HEIGHT = { low: 31, moderate: 46, elevated: 60, high: 72 }
const RISK_FILL_COLOR = {
  low: AREA_RISK_COLORS.green,
  moderate: AREA_RISK_COLORS.yellow,
  elevated: AREA_RISK_COLORS.orange,
  high: AREA_RISK_COLORS.red,
}
const UNREVEALED_HEIGHT_PERCENT = 6
const UNREVEALED_FILL_COLOR = 'rgba(148, 163, 184, 0.16)'
const LABELLED_INDEXES = new Set([0, 2, 4, 6, 8, 10, 13])

function compactDate(date) {
  const [, month, day] = date.split('-')
  return `${day} ${month === '09' ? 'SEP' : month}`
}

/** Qualitative presentation outlook driven by the same activeIndex and
 * risk sequence as the map. A Sep date's color and risk label only reveal
 * once the timeline reaches it -- future frames render as a dark neutral
 * placeholder so the chart never exposes risk information ahead of
 * playback, and seeking backward re-hides any later frame. The bar for a
 * newly revealed frame softly grows/fills via a CSS transition on its own
 * height value; already-revealed bars never change again, so nothing
 * re-animates on later ticks. */
export default function MyAreaTemporalOutlook({ areaLabel = 'Matara', activeIndex, onSelectIndex, frames = [], disabled = false }) {
  return (
    <section className="rounded-xl border border-outline-variant/30 bg-surface-container/70 p-3 shadow-card-subtle" aria-labelledby="future-risk-outlook-title">
      <div className="flex items-center justify-between gap-2">
        <div id="future-risk-outlook-title" className="truncate text-sm font-semibold text-on-surface" title={`Future Risk Outlook — ${areaLabel}`}>
          Future Risk Outlook — {areaLabel}
        </div>
        <div className="shrink-0 text-[10px] font-mono uppercase tracking-wide text-on-surface-variant/50">14 Sep-date frames</div>
      </div>

      <div className="mt-3 grid h-[154px] items-end gap-1" style={{ gridTemplateColumns: `repeat(${frames.length || 1}, minmax(0, 1fr))` }} role="group" aria-label="Matara qualitative risk by Sep date">
        {frames.map((frame, index) => {
          const active = index === activeIndex
          const revealed = index <= activeIndex
          const label = compactDate(frame.date)
          const riskLabel = frame.riskLevel.toUpperCase()
          const ariaLabel = revealed
            ? `${formatDisplayDate(frame.date)} - ${riskLabel} district risk`
            : `${formatDisplayDate(frame.date)} - not yet revealed`
          return (
            <button
              key={frame.date}
              type="button"
              disabled={disabled}
              aria-label={ariaLabel}
              aria-current={active ? 'date' : undefined}
              onClick={() => onSelectIndex(index)}
              className={active ? 'group flex h-full min-w-0 flex-col items-center justify-end gap-1 rounded-md border border-primary/70 bg-primary/[0.06] px-0.5 pb-1 shadow-[0_0_12px_rgba(78,222,163,0.16)] focus:outline-none focus-visible:ring-2 focus-visible:ring-primary' : 'group flex h-full min-w-0 flex-col items-center justify-end gap-1 rounded-md border border-transparent px-0.5 pb-1 hover:bg-white/[0.03] focus:outline-none focus-visible:ring-2 focus-visible:ring-primary'}
            >
              <span className={active ? 'text-[8px] font-bold text-primary' : 'text-[8px] font-semibold text-on-surface-variant/55'}>{revealed ? riskLabel : ' '}</span>
              <span className="flex h-[96px] w-full items-end overflow-hidden rounded-sm bg-surface-container-lowest/55">
                <span
                  className="block w-full rounded-t-sm transition-[height,background-color,filter] duration-[350ms] ease-out group-hover:brightness-110"
                  style={{
                    height: `${revealed ? RISK_HEIGHT[frame.riskLevel] : UNREVEALED_HEIGHT_PERCENT}%`,
                    backgroundColor: revealed ? RISK_FILL_COLOR[frame.riskLevel] : UNREVEALED_FILL_COLOR,
                  }}
                />
              </span>
              <span className={active ? 'min-h-[18px] text-center text-[8px] font-bold leading-tight text-primary' : 'min-h-[18px] text-center text-[8px] font-semibold leading-tight text-on-surface-variant/55'}>
                {LABELLED_INDEXES.has(index) ? label : ' '}
              </span>
            </button>
          )
        })}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[9.5px] text-on-surface-variant/65">
        {[
          ['Low', AREA_RISK_COLORS.green],
          ['Moderate', AREA_RISK_COLORS.yellow],
          ['Elevated', AREA_RISK_COLORS.orange],
          ['High', AREA_RISK_COLORS.red],
        ].map(([label, color]) => <span key={label} className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ backgroundColor: color }} />{label}</span>)}
        <span className="ml-auto">Qualitative presentation outlook - no probability</span>
      </div>
    </section>
  )
}
