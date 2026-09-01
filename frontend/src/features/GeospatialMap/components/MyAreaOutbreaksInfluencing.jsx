import React from 'react'

import './myAreaChrome.css'

function badgeClass(status) {
  if (status.includes('OVERLAPPING')) return 'border-red-400/35 bg-red-400/10 text-red-200'
  if (status.includes('AFFECTS')) return 'border-orange-400/35 bg-orange-400/10 text-orange-200'
  if (status.includes('APPROACHING')) return 'border-violet-400/35 bg-violet-400/10 text-violet-200'
  return 'border-primary/30 bg-primary/10 text-primary'
}

/** The cards explain the same real case identities that anchor the map.
 * The map generator remains generic; this presentation list intentionally
 * prioritizes the first two stable real influences for leader review. */
export default function MyAreaOutbreaksInfluencing({ influences = [], focusedCaseId = null, onFocusCase }) {
  const visibleInfluences = influences.slice(0, 2)
  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container/70 shadow-card-subtle" aria-labelledby="influencing-area-title">
      <div className="shrink-0 p-4 pb-2">
        <div id="influencing-area-title" className="text-sm font-semibold text-on-surface">Outbreaks influencing my area</div>
        <div className="mt-0.5 text-[10.5px] text-on-surface-variant/60">Real verified case identities and deterministic presentation corridors for the active Sep frame.</div>
      </div>

      {visibleInfluences.length === 0 ? (
        <div className="px-4 pb-4 text-xs text-on-surface-variant">Waiting for verified Matara case coordinates.</div>
      ) : (
        <ul className="my-area-scroll flex min-h-0 flex-col gap-2 px-4 pb-4" role="list" aria-label="Outbreaks influencing my area">
          {visibleInfluences.map((influence) => {
            const active = influence.anchorId === focusedCaseId
            return (
              <li key={influence.anchorId} className={active ? 'rounded-lg border border-primary/50 bg-primary/10 p-3 shadow-[0_0_18px_rgba(78,222,163,0.09)]' : 'rounded-lg border border-outline-variant/20 bg-surface-container-lowest/40 p-3'}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-[#EF4444] ring-2 ring-white/70" aria-hidden="true" />
                    <span className="truncate font-mono text-xs font-semibold text-on-surface" title={influence.caseId}>{influence.caseId}</span>
                    {influence.locationDistrict && <span className="truncate text-[10.5px] text-on-surface-variant">- {influence.locationDistrict}</span>}
                  </div>
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[8.5px] font-bold tracking-wide ${badgeClass(influence.status)}`}>{influence.status}</span>
                </div>
                <p className="mt-2 text-[10.5px] leading-relaxed text-on-surface-variant/75">{influence.description}</p>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <span className="text-[9.5px] text-on-surface-variant/45">Projected future impact - not a confirmed future case</span>
                  <button type="button" onClick={() => onFocusCase(influence.anchorId)} aria-pressed={active} className="shrink-0 text-[10.5px] font-semibold text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                    {active ? 'Focused on map' : 'View on Map ->'}
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
