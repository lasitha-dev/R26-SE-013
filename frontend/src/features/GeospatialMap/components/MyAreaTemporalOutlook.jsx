import React from 'react'

import { addDaysToIsoDate, forecastDayLabel, formatDisplayDate } from '../adapters/forecastDate'
import { LABEL_FORECAST_D0, MY_AREA_NOMINAL_REACH_DISCLAIMER } from '../semanticLabels'

/**
 * GEO-MY-AREA-VISUAL-QA-REBUILD: the "Future Risk Outlook" card from the
 * reference composition, rebuilt on the real backend contract instead of
 * the screenshot's mock day-over-day risk bars.
 *
 * Traced (`lsdOutbreakAdapter.js::buildForecastFrame`): the only field
 * that genuinely varies by day in the current runtime is nominal reach
 * (`nominal_reach_by_day`) -- `riskSurface`/`cells` are the SAME
 * FeatureCollection reused across every day frame for an origin ("the
 * backend has no day-varying risk surface yet"). Turning that into a
 * day-by-day RISK chart would fabricate a value the backend does not
 * produce, so this renders the real, honestly-named concept instead:
 * nominal reach in real km per real forecast day, using the exact values
 * `nominal_reach_by_day` already supplies -- never a derived risk tier.
 *
 * GEO-MY-AREA-LAYOUT-BALANCE: the empty/no-selection state is a compact
 * ~112px body (the requested ~100-130px band, not a large standalone
 * block) -- it only grows to the requested ~180-240px band once a real
 * per-day chart actually has data to show. Never scrolls internally
 * (Section 13 of the rebalance).
 */
export default function MyAreaTemporalOutlook({
  areaLabel,
  selectedDay,
  onSelectDay,
  t0 = null,
  availableDays = [0],
  nominalReachByDay = [],
  disabled = false,
}) {
  const reachByDay = new Map(nominalReachByDay.map((entry) => [entry.day, entry.nominal_reach_km]))
  const maxReachKm = Math.max(0, ...nominalReachByDay.map((entry) => entry.nominal_reach_km ?? 0))
  const hasForecast = availableDays.length > 1

  return (
    <div className="rounded-xl border border-outline-variant/30 bg-surface-container/70 p-3 shadow-card-subtle">
      <div className="flex items-center justify-between gap-2">
        <div className="truncate text-sm font-semibold text-on-surface" title={`Nominal Reach Outlook${areaLabel ? ` — ${areaLabel}` : ''}`}>
          Nominal Reach Outlook{areaLabel ? ` — ${areaLabel}` : ''}
        </div>
        {hasForecast && <div className="shrink-0 text-[10px] font-mono uppercase tracking-wide text-on-surface-variant/50">D0 – D+{Math.max(...availableDays)}</div>}
      </div>

      {!hasForecast ? (
        <div className="mt-2 flex h-[112px] items-center justify-center rounded-lg border border-outline-variant/20 bg-surface-container-lowest/40 px-3 text-center text-xs text-on-surface-variant/70" role="status">
          {disabled ? 'Select a relevant origin to see its real nominal-reach horizon.' : 'No time-varying forecast frames are available for this selection.'}
        </div>
      ) : (
        <div className="mt-2 flex items-end gap-1.5" role="group" aria-label="Nominal reach by forecast day">
          {availableDays.map((day) => {
            const active = day === selectedDay
            const reachKm = reachByDay.get(day) ?? null
            const heightPct = day === 0 || reachKm === null || maxReachKm === 0 ? 0 : Math.max(8, (reachKm / maxReachKm) * 100)
            const dateLabel = t0 ? formatDisplayDate(addDaysToIsoDate(t0, day)) : null
            return (
              <button
                key={day}
                type="button"
                disabled={disabled}
                aria-pressed={active}
                title={day === 0 ? LABEL_FORECAST_D0 : dateLabel ?? undefined}
                onClick={() => onSelectDay(day)}
                className="flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-md p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed"
              >
                <div className="text-[9.5px] font-mono text-on-surface-variant/70">{day === 0 ? '—' : `${reachKm != null ? reachKm.toFixed(1) : '—'}km`}</div>
                <div className="flex h-14 w-full items-end overflow-hidden rounded bg-surface-container-lowest/50">
                  {day === 0 ? (
                    <div className="h-1 w-full bg-on-surface-variant/30" />
                  ) : (
                    <div
                      className={active ? 'w-full rounded-t bg-primary' : 'w-full rounded-t bg-teal-500/50'}
                      style={{ height: `${heightPct}%` }}
                    />
                  )}
                </div>
                <div className={active ? 'rounded-md bg-primary/20 px-1.5 py-0.5 text-[10.5px] font-medium text-primary' : 'px-1.5 py-0.5 text-[10.5px] font-medium text-on-surface-variant'}>
                  {forecastDayLabel(day)}
                </div>
                {dateLabel && <div className="text-[9px] text-on-surface-variant/50">{dateLabel}</div>}
              </button>
            )
          })}
        </div>
      )}

      <div className="mt-2 truncate text-[10px] text-on-surface-variant/50" title={MY_AREA_NOMINAL_REACH_DISCLAIMER}>
        {MY_AREA_NOMINAL_REACH_DISCLAIMER}
      </div>
    </div>
  )
}
