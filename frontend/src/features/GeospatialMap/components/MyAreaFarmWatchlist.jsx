import React from 'react'
import { Link } from 'react-router-dom'

import { formatVerificationTime } from '../adapters/verificationTime'
import './myAreaChrome.css'

const TIER_CHIP = {
  highest: 'border-red-400/40 bg-red-400/10 text-red-200',
  high: 'border-orange-400/40 bg-orange-400/10 text-orange-200',
  moderate: 'border-amber-300/40 bg-amber-300/10 text-amber-100',
  lower: 'border-emerald-400/35 bg-emerald-400/10 text-emerald-200',
}

/**
 * Assigned farms, each with the facts a vet checks first: verified cases,
 * GPS status, the static relative tier at the farm, and whether it lies
 * inside the selected day's nominal-reach outline. Rows come from
 * `buildFarmWatchlist` -- real farms, real cases, backend geometry only.
 */
export default function MyAreaFarmWatchlist({ rows = [], diseaseShortLabel = '', reachDay = null, modelReady = true, onFocusFarm, focusedFarmId = null }) {
  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container/70 shadow-card-subtle" aria-labelledby="farm-watchlist-title">
      <div className="flex flex-wrap items-start justify-between gap-2 p-4 pb-2">
        <div>
          <div id="farm-watchlist-title" className="text-sm font-semibold text-on-surface">Assigned farms to review</div>
          <div className="mt-0.5 text-[10.5px] text-on-surface-variant/60">
            Ordered by verified {diseaseShortLabel} cases, then relative-score zone at the farm GPS{reachDay ? `, then inside the Day ${reachDay} reach outline` : ''}.
          </div>
        </div>
        <Link to="/vet/assigned-farms" className="text-[10.5px] font-semibold text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">All assigned farms -&gt;</Link>
      </div>

      {rows.length === 0 ? (
        <div className="px-4 pb-4 text-xs text-on-surface-variant">No farms are assigned to you yet. Farms appear here once a farm owner links you in ADRS.</div>
      ) : (
        <div className="my-area-scroll overflow-x-auto px-4 pb-4">
          <table className="w-full min-w-[560px] border-separate border-spacing-y-1 text-left text-[11px]">
            <thead>
              <tr className="text-[9.5px] uppercase tracking-wide text-on-surface-variant/55">
                <th className="px-2 py-1 font-semibold">Farm</th>
                <th className="px-2 py-1 font-semibold">Verified cases</th>
                <th className="px-2 py-1 font-semibold">Relative zone at farm</th>
                <th className="px-2 py-1 font-semibold">{reachDay ? `Day ${reachDay} reach` : 'Reach'}</th>
                <th className="px-2 py-1"><span className="sr-only">Map</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const active = row.farmId === focusedFarmId
                return (
                  <tr key={row.farmId} className={active ? 'bg-primary/10' : 'bg-surface-container-lowest/40'}>
                    <td className="rounded-l-md px-2 py-2 align-top">
                      <div className="font-semibold text-on-surface">{row.name ?? 'Assigned farm'}</div>
                      <div className="font-mono text-[9.5px] text-on-surface-variant/45" title={row.farmId}>
                        {row.hasGps ? `${row.latitude.toFixed(4)}, ${row.longitude.toFixed(4)}` : 'No GPS on record'}
                      </div>
                    </td>
                    <td className="px-2 py-2 align-top">
                      {row.cases.length === 0 ? (
                        <span className="text-on-surface-variant/55">None verified</span>
                      ) : (
                        <ul className="flex flex-col gap-0.5">
                          {row.cases.map((c) => (
                            <li key={c.caseId} className="text-on-surface">
                              <span className="mr-1 inline-block rounded border border-red-400/40 bg-red-400/10 px-1 text-[9.5px] font-bold text-red-200">{c.disease}</span>
                              <span className="text-on-surface-variant">verified {formatVerificationTime(c.verificationTime) ?? 'date unavailable'}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                    <td className="px-2 py-2 align-top">
                      {!row.hasGps ? (
                        <span className="text-on-surface-variant/55">Not placed</span>
                      ) : !modelReady ? (
                        <span className="text-on-surface-variant/55">No validated model</span>
                      ) : row.tier ? (
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${TIER_CHIP[row.tier]}`}>{row.tierLabel}</span>
                      ) : (
                        <span className="text-on-surface-variant/55">Outside scored area</span>
                      )}
                    </td>
                    <td className="px-2 py-2 align-top text-on-surface-variant">
                      {!row.hasGps || !reachDay ? '—' : row.withinReach ? 'Inside outline' : 'Outside'}
                    </td>
                    <td className="rounded-r-md px-2 py-2 text-right align-top">
                      {row.focusAnchorId && onFocusFarm && (
                        <button type="button" onClick={() => onFocusFarm(row)} aria-pressed={active} className="text-[10.5px] font-semibold text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                          {active ? 'Shown on map' : 'Show case'}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="mt-2 text-[9.5px] leading-relaxed text-on-surface-variant/50">
            Relative zone = snapshot-relative C0 quartile at the farm GPS (same on every day; not an infection probability). Reach outline = distance-only visualisation, not an infection boundary.
          </p>
        </div>
      )}
    </section>
  )
}
