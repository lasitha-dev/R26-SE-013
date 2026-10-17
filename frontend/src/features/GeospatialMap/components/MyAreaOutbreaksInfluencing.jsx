import React from 'react'

import { INFLUENCE_KIND } from '../adapters/spatialTimelineView'
import './myAreaChrome.css'

// Card type colours (prototype v4): green = local source, violet = approaching.
const KIND_COLOUR = { [INFLUENCE_KIND.LOCAL]: '#22c55e', [INFLUENCE_KIND.APPROACHING]: '#a78bfa' }
const NO_DATA_COLOUR = '#94a3b8'

/** Day-by-day modelled influence on district land (backend `by_day` max
 * score), scaled to its own peak, with the selected day marked. */
function InfluenceSparkline({ series, day, colour }) {
  if (!Array.isArray(series) || series.length < 2) return null
  const peak = Math.max(...series, 0.01)
  const x = (k) => (k / (series.length - 1)) * 300
  const points = series.map((v, k) => `${x(k).toFixed(1)},${(24 - (v / peak) * 20).toFixed(1)}`).join(' ')
  return (
    <svg className="mt-2 block h-[26px] w-full" viewBox="0 0 300 26" preserveAspectRatio="none" role="img" aria-label="Modelled influence on the district, Day 0 to the last day" data-chart="influence-series">
      <polyline points={points} fill="none" stroke={colour} strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
      <line x1={x(day)} x2={x(day)} y1="0" y2="26" stroke="#ffffff" strokeOpacity="0.35" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

/**
 * "Outbreaks influencing my area": one card per verified source whose
 * modelled influence touches the vet's district within the horizon --
 * LOCAL SOURCE (inside) or APPROACHING AREA (outside). Every value comes
 * from the backend snapshot for the selected day (`influence.card`);
 * locations are the source's own GPS resolved to a mapped place and the
 * real district polygon (`locationFor`).
 */
export default function MyAreaOutbreaksInfluencing({
  influences = [], day = 0, focusedCaseId = null, onFocusCase, onViewOnMap = null, onViewOnOutbreakMap = null,
  districtLabel = 'district', farmNames = null, diseaseShortLabel = '', locationFor = null, influenceDataAvailable = true,
  horizonDays = 14, statusText = null,
}) {
  const withCard = influences.filter((influence) => influence.card)
  const cards = withCard.filter((influence) => influence.card.kind || !influence.card.modelData)
  const noInfluence = withCard.filter((influence) => influence.card.modelData && !influence.card.kind)
  const sourceIdOf = (influence) => {
    if (influence.card?.caseRef) return influence.card.caseRef
    // Another vet's case arrives privacy-reduced: its one-way source key only.
    if (influence.privacyReduced) return String(influence.sourceId ?? '').slice(0, 15)
    // The vet's own case without a case number: the record id they already see.
    return influence.caseId ?? influence.sourceId
  }
  const evidenceOf = (influence) => (influence.recordDomain === 'OPERATIONAL'
    ? 'Vet-verified case'
    : `Historical ${diseaseShortLabel} record`.replace(/\s+/g, ' ').trim())
  const placeOf = (influence) => {
    const location = locationFor?.(influence) ?? null
    const farm = influence.farmId ? farmNames?.get?.(influence.farmId)?.name : null
    const parts = [location?.place, location?.district].filter(Boolean)
    return { text: parts.join(', ') || null, farm }
  }

  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container/70 shadow-card-subtle" aria-labelledby="influencing-area-title">
      <div className="shrink-0 p-4 pb-2">
        <div id="influencing-area-title" className="text-sm font-semibold text-on-surface">Outbreaks influencing my area</div>
        <div className="mt-0.5 text-[10.5px] text-on-surface-variant/60">Verified source cases inside or outside {districtLabel} whose modelled reach touches the district in the next {horizonDays} days.</div>
      </div>

      {statusText ? (
        <div className="px-4 pb-4 text-xs text-on-surface-variant" data-state="model-status">{statusText}</div>
      ) : !influenceDataAvailable && withCard.length > 0 ? (
        <div className="px-4 pb-2 text-[10.5px] text-amber-200/80" data-state="insufficient-model-data">District influence is not available in this snapshot, so sources are listed without a modelled first-influence day.</div>
      ) : null}

      {!statusText && cards.length === 0 && (
        <div className="px-4 pb-4 text-xs text-on-surface-variant" data-state="no-influence">No eligible source reaches {districtLabel} in this {horizonDays}-day window.</div>
      )}

      {!statusText && cards.length > 0 && (
        <ul className="my-area-scroll flex min-h-0 flex-col gap-2 px-4 pb-3" role="list" aria-label="Outbreaks influencing my area">
          {cards.map((influence) => {
            const { card } = influence
            const active = influence.anchorId === focusedCaseId
            const colour = KIND_COLOUR[card.kind] ?? NO_DATA_COLOUR
            const place = placeOf(influence)
            const local = card.kind === INFLUENCE_KIND.LOCAL
            return (
              <li key={influence.anchorId} data-kind={card.kind ?? 'NO MODEL DATA'} className={active ? 'rounded-xl border border-primary/50 bg-primary/10 px-4 py-3' : 'rounded-xl border border-outline-variant/25 bg-surface-container-lowest/40 px-4 py-3'}>
                <div className="flex items-center gap-2">
                  <span className={`h-3 w-3 shrink-0 rounded-full ${local ? 'bg-[#EF4444] ring-2 ring-[#22c55e]' : 'border-[2.5px] border-[#EF4444] bg-white'}`} aria-hidden="true" />
                  <span className="truncate font-mono text-[13px] font-bold text-on-surface" title={influence.privacyReduced ? "Another vet's case: details are privacy-reduced" : place.farm ?? undefined}>{sourceIdOf(influence)}</span>
                  {place.text && <span className="truncate text-[12.5px] text-on-surface-variant">· {place.text}</span>}
                  <span className="ml-auto shrink-0 rounded-md border px-2 py-0.5 font-mono text-[10px] font-bold tracking-wider" style={{ color: colour, borderColor: `${colour}88`, backgroundColor: `${colour}14` }}>
                    {card.kind ?? 'NO MODEL DATA'}
                  </span>
                </div>
                <p className="mt-2 text-[13px] leading-snug text-on-surface">
                  {[card.whereText, card.directionText, card.dayStatusText].filter(Boolean).join(' · ')}.
                </p>
                {card.possibleText && <p className="mt-1 text-[11px] font-semibold text-[#fb923c]" data-line="possible-new-cases">{card.possibleText}</p>}
                <InfluenceSparkline series={card.series} day={day} colour={colour} />
                <div className="mt-2 flex items-center justify-end gap-2">
                  <span className="flex shrink-0 items-center gap-3">
                    {onViewOnOutbreakMap && (
                      <button type="button" onClick={() => onViewOnOutbreakMap(influence)} className="text-[10.5px] text-on-surface-variant/70 hover:text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">Outbreak Map ↗</button>
                    )}
                    <button type="button" onClick={() => (onViewOnMap ? onViewOnMap(influence) : onFocusCase(influence.anchorId))} aria-pressed={active} className="text-[13px] font-semibold text-[#4ade80] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                      {active ? 'Focused on map' : 'View on Map →'}
                    </button>
                  </span>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {!statusText && noInfluence.length > 0 && (
        <div className="px-4 pb-4 text-[10.5px] text-on-surface-variant/55" data-state="nearby-no-influence">
          {noInfluence.length} nearby source{noInfluence.length === 1 ? '' : 's'} within model range {noInfluence.length === 1 ? 'does' : 'do'} not reach {districtLabel} in {horizonDays} days (no modelled influence), so {noInfluence.length === 1 ? 'it is' : 'they are'} not listed.
        </div>
      )}
    </section>
  )
}
