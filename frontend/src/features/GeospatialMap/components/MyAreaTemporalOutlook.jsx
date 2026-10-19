import React from 'react'

import { formatDisplayDate } from '../adapters/forecastDate'
import { BAND_LABEL, BAND_RGBA } from '../adapters/riskFieldModel'
import { OUTLOOK_BANDS } from '../adapters/riskOutlook'

const BAND_SHORT = { high: 'HIGH', elevated: 'ELEV', moderate: 'MOD', low: 'LOW' }
const bandColour = (band) => `rgb(${BAND_RGBA[band].slice(0, 3).join(',')})`
const MIN_BAR_HEIGHT_PERCENT = 3
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

function compactDate(date) {
  const [, month, day] = String(date).split('-')
  return `${day} ${MONTHS[Number(month) - 1] ?? month}`
}

const formatArea = (km2) => `${Math.round(km2).toLocaleString('en-US')} km²`
const formatShare = (share) => `${(share * 100).toFixed(share > 0 && share < 0.1 ? 1 : 0)}%`

/**
 * Future Risk Outlook -- the SAME backend day rasters and selected day as the
 * Risk Zones map (adapters/riskOutlook.js). Bar = share of the district's own
 * area coloured on that day (one fixed denominator for every day), stacked by
 * the fixed display bands. Days 8-14 (exploratory) are dashed. A relative
 * spatial score, not an infection probability; no case counts are predicted.
 */
export default function MyAreaTemporalOutlook({ areaLabel = 'My district', activeIndex, onSelectIndex, rows = [], disabled = false, unavailableText = null }) {
  const lastIndex = rows.length - 1
  const selected = rows[activeIndex] ?? null
  // Track height = the largest daily share, rounded up to the next 10 %.
  const scaleShare = Math.max(0.1, Math.ceil(Math.max(0, ...rows.map((row) => row.coloredShare)) * 10) / 10)
  const handleKeyDown = (event) => {
    if (disabled || rows.length === 0 || event.altKey || event.ctrlKey || event.metaKey) return
    const target = { ArrowLeft: activeIndex - 1, ArrowRight: activeIndex + 1, Home: 0, End: lastIndex }[event.key]
    if (target === undefined) return
    event.preventDefault()
    const clamped = Math.max(0, Math.min(lastIndex, target))
    if (clamped !== activeIndex) onSelectIndex(clamped)
  }
  return (
    <section className="rounded-xl border border-outline-variant/30 bg-surface-container/70 p-3 shadow-card-subtle" aria-labelledby="future-risk-outlook-title">
      <div className="flex items-center justify-between gap-2">
        <div id="future-risk-outlook-title" className="truncate text-sm font-semibold text-on-surface">Future Risk Outlook — {areaLabel}</div>
      </div>
      {rows.length === 0 && <div className="mt-2 text-[11px] text-on-surface-variant">{unavailableText ?? 'No model frames for this analysis date.'}</div>}
      {rows.length > 0 && (
        <div className="mt-3 grid h-[154px] items-end gap-1" style={{ gridTemplateColumns: `repeat(${rows.length}, minmax(0, 1fr))` }} role="group" aria-label={`${areaLabel}: share of the district coloured by the risk surface, by date`} aria-keyshortcuts="ArrowLeft ArrowRight Home End" onKeyDown={handleKeyDown}>
          {rows.map((row, index) => {
            const active = index === activeIndex
            // Bars fill as the timeline reaches their date (Day 0 -> Day 14).
            const revealed = Number.isInteger(activeIndex) && index <= activeIndex
            const ariaLabel = `${formatDisplayDate(row.date)} - ${formatArea(row.coloredKm2)} (${formatShare(row.coloredShare)} of ${areaLabel}) coloured${row.maxBand ? `, highest ${BAND_LABEL[row.maxBand]}` : ''}${row.exploratory ? ' (exploratory)' : ''}`
            const height = row.coloredShare > 0 ? Math.max(MIN_BAR_HEIGHT_PERCENT, (row.coloredShare / scaleShare) * 100) : MIN_BAR_HEIGHT_PERCENT
            const firstExploratory = row.exploratory && !rows[index - 1]?.exploratory
            return (
              <button
                key={row.date ?? index}
                type="button"
                disabled={disabled}
                aria-label={ariaLabel}
                aria-current={active ? 'date' : undefined}
                title={ariaLabel}
                onClick={() => onSelectIndex(index)}
                className={`group relative flex h-full min-w-0 flex-col items-center justify-end gap-1 rounded-md border px-0.5 pb-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${active ? 'border-primary/70 bg-primary/[0.06] shadow-[0_0_12px_rgba(78,222,163,0.16)]' : 'border-transparent hover:bg-white/[0.03]'} ${row.exploratory ? 'bg-amber-300/[0.025]' : ''}`}
              >
                {firstExploratory && <span aria-hidden="true" className="absolute -left-[3px] top-0 h-full border-l border-dashed border-amber-300/45" />}
                <span className="text-[8px] font-extrabold tracking-wide" style={{ color: revealed && row.maxBand ? bandColour(row.maxBand) : 'transparent' }}>{revealed && row.maxBand ? BAND_SHORT[row.maxBand] : ' '}</span>
                <span className="relative flex h-[96px] w-full items-end overflow-hidden rounded-sm bg-surface-container-lowest/55">
                  <span className={`flex w-full flex-col-reverse overflow-hidden rounded-t-sm transition-[height] duration-[350ms] ease-out${row.exploratory ? ' border-t border-dashed border-white/70 opacity-75' : ''}`} style={{ height: revealed ? `${height}%` : '0%' }} data-bar="coloured-share" data-revealed={revealed ? 'true' : 'false'}>
                    {row.coloredKm2 > 0
                      ? [...OUTLOOK_BANDS].reverse().map((band) => (row.bandAreas[band] > 0 ? <span key={band} className="block w-full" style={{ height: `${(row.bandAreas[band] / row.coloredKm2) * 100}%`, backgroundColor: bandColour(band) }} /> : null))
                      : <span className="block h-full w-full bg-slate-400/25" />}
                  </span>
                </span>
                <span className={active ? 'min-h-[18px] text-center text-[8px] font-bold leading-tight text-primary' : 'min-h-[18px] text-center text-[8px] font-semibold leading-tight text-on-surface-variant/55'}>
                  {index === 0 || index === lastIndex || index % 2 === 0 ? compactDate(row.date) : ' '}
                </span>
              </button>
            )
          })}
        </div>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[9.5px] text-on-surface-variant/65">
        {OUTLOOK_BANDS.map((band) => <span key={band} className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ backgroundColor: bandColour(band) }} />{BAND_LABEL[band]}</span>)}
      </div>
    </section>
  )
}
