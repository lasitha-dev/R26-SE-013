import React from 'react'

import { FARM_LIST_STATUS } from '../adapters/myAreaFarmList'

const BADGE = {
  [FARM_LIST_STATUS.PENDING]: { text: 'PENDING', colour: '#f472b6' },
  [FARM_LIST_STATUS.AFFECTED]: { text: 'COULD BE AFFECTED', colour: '#fbbf24' },
  [FARM_LIST_STATUS.MONITORING]: { text: 'MONITORING', colour: '#94a3b8' },
  [FARM_LIST_STATUS.NO_LOCATION]: { text: 'LOCATION UNAVAILABLE', colour: '#64748b' },
}
const VERIFIED_COLOUR = '#f87171'

function StatusSquare({ status }) {
  if (status === FARM_LIST_STATUS.VERIFIED) return <span className="h-3 w-3 shrink-0 rounded-[3px] border-2 border-[#fca5a5] bg-[#b91c1c]" aria-hidden="true" />
  if (status === FARM_LIST_STATUS.PENDING) return <span className="grid h-3.5 w-3.5 shrink-0 place-items-center rounded-[3px] border-2 border-dashed border-[#f472b6]" aria-hidden="true"><span className="h-1.5 w-1.5 rounded-[1px] bg-[#f472b6]" /></span>
  if (status === FARM_LIST_STATUS.AFFECTED) return <span className="grid h-3.5 w-3.5 shrink-0 place-items-center rounded-[3px] border-2 border-[#f59e0b]" aria-hidden="true"><span className="h-1.5 w-1.5 rounded-[1px] bg-white" /></span>
  if (status === FARM_LIST_STATUS.NO_LOCATION) return <span className="h-3 w-3 shrink-0 rounded-[3px] border border-dashed border-slate-500" aria-hidden="true" />
  return <span className="h-2.5 w-2.5 shrink-0 rounded-[2px] bg-slate-300/80" aria-hidden="true" />
}

function herdText(row) {
  if (row.animals !== null) return `${row.animals} head`
  if (row.animalCountStatus === 'INVALID') return 'herd size invalid'
  if (row.animalCountStatus === 'NOT_SHARED') return '– head'
  return 'herd size missing'
}

/**
 * Farms in my district (adapters/myAreaFarmList.js): authorised farms of the
 * vet's district only, status for the selected day; click = focus on the map.
 */
export default function MyAreaFarmList({ districtLabel = 'district', farmList = null, futureMode = true, day = 0, focusedFarmId = null, onFocusFarm = null }) {
  const rows = farmList?.rows ?? []
  const summary = farmList?.summary ?? { total: 0, verified: 0, affected: 0, noLocation: 0, assignedOutsideDistrict: 0 }
  return (
    <section aria-labelledby="farms-in-district-title" className="rounded-xl border border-outline-variant/30 bg-surface-container/70 p-3.5 shadow-card-subtle">
      <div className="mb-2 flex items-center gap-2">
        <span id="farms-in-district-title" className="text-[12px] font-bold uppercase tracking-wider text-on-surface/80">Farms in {districtLabel}</span>
        <span className="rounded bg-surface-container-high/70 px-1.5 py-0.5 font-mono text-[10px] text-on-surface" data-value="farm-total">{summary.total}</span>
      </div>
      {rows.length === 0 ? (
        <div className="text-[10.5px] text-on-surface-variant">No authorised registered farm on record in {districtLabel}.</div>
      ) : (
        <ul className="flex max-h-[460px] flex-col gap-1.5 overflow-y-auto pr-0.5" role="list" aria-label={`Farms in ${districtLabel}`}>
          {rows.map((row) => {
            const focused = row.farmId === focusedFarmId
            const badge = row.status === FARM_LIST_STATUS.VERIFIED
              ? { text: `${row.caseCount} ACTIVE CASE${row.caseCount === 1 ? '' : 'S'}`, colour: VERIFIED_COLOUR }
              : BADGE[row.status]
            return (
              <li key={row.farmId} data-status={row.status}>
                <button
                  type="button"
                  disabled={!row.coordinates}
                  onClick={() => onFocusFarm?.(row)}
                  aria-pressed={focused}
                  title={row.coordinates ? 'Focus this farm on the map' : 'No GPS on record -- cannot be placed on the map'}
                  className={`flex w-full flex-col rounded-lg border px-3 py-2.5 text-left transition ${focused ? 'border-primary/60 bg-primary/10' : 'border-outline-variant/20 bg-surface-container/50 hover:border-primary/30'} disabled:cursor-default`}
                >
                  <span className="flex w-full items-center gap-2.5">
                    <StatusSquare status={row.status} />
                    <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-on-surface" title={row.name}>{row.name}</span>
                    <span className="shrink-0 text-[11.5px] text-on-surface-variant/70" title={row.animalCountStatus === 'NOT_SHARED' ? 'Herd size is shared only for farms assigned to you' : undefined}>{herdText(row)}</span>
                    {badge && (
                      <span className="shrink-0 rounded-md border px-1.5 py-0.5 font-mono text-[9.5px] font-bold tracking-wider" style={{ color: badge.colour, borderColor: `${badge.colour}88`, backgroundColor: `${badge.colour}12` }}>{badge.text}</span>
                    )}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
      {summary.assignedOutsideDistrict > 0 && (
        <div className="mt-1.5 text-[10px] text-on-surface-variant/55">{summary.assignedOutsideDistrict} of your assigned farm{summary.assignedOutsideDistrict === 1 ? '' : 's'} {summary.assignedOutsideDistrict === 1 ? 'is' : 'are'} outside {districtLabel} (or has no district/GPS) and {summary.assignedOutsideDistrict === 1 ? 'is' : 'are'} not listed here.</div>
      )}
    </section>
  )
}
