import React, { useState } from 'react'

const TAB = { AREA: 'AREA', EXPLAINER: 'EXPLAINER' }

function Row({ label, value }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="flex items-center justify-between gap-3 py-1">
      <dt className="text-[11px] text-on-surface-variant/60">{label}</dt>
      <dd className="truncate text-right text-xs font-medium text-on-surface" title={typeof value === 'string' ? value : undefined}>
        {value}
      </dd>
    </div>
  )
}

/**
 * GEO-MY-AREA-VISUAL-QA-REBUILD: the right-column "Area Intelligence /
 * AI Explainer" tabbed panel from the reference composition.
 *
 * AREA INTELLIGENCE reuses the exact same real fields
 * `MyAreaSummaryPanel.jsx`/`MyAreaScientificPanel.jsx` already rendered
 * (area identity, selected-origin scientific context, forecast window,
 * relevant-origin/clinical counts) -- only the presentation changes.
 *
 * AI EXPLAINER is deliberately NOT a generative call -- it is a small set
 * of deterministic, template sentences chosen from the SAME real state
 * already on screen (disease capability, whether an origin is selected,
 * whether a real score/forecast exists). No medical/diagnostic claim is
 * ever synthesized.
 */
export default function MyAreaIntelligencePanel({
  area,
  selectedOriginContext,
  hasSpatialCells,
  diseaseShortLabel,
  availableForecastDays,
  relevantOriginsCount,
  verifiedClinicalCount,
}) {
  const [tab, setTab] = useState(TAB.AREA)

  const futureDays = (availableForecastDays ?? []).filter((d) => d > 0)
  const coordinates = area && typeof area.latitude === 'number' && typeof area.longitude === 'number' ? `${area.latitude.toFixed(4)}, ${area.longitude.toFixed(4)}` : null
  const primaryAreaLabel = area?.locationDistrict ?? area?.farmId ?? '—'

  const explainerLines = []
  if (!selectedOriginContext) {
    explainerLines.push('Select a relevant historical or model origin below to see area-specific spatial context.')
  } else if (!hasSpatialCells) {
    explainerLines.push(`A spatial-cell risk surface is not available for the selected ${diseaseShortLabel ?? 'disease'} context. Observed and historical context can still be reviewed.`)
  } else if (selectedOriginContext.relativeSpatialScore?.value != null) {
    explainerLines.push('The selected view displays the available local spatial risk output derived from the selected historical/model origin.')
  } else {
    explainerLines.push('Local spatial risk is not exposed for this exact farm location. Observed and historical context can still be reviewed.')
  }
  explainerLines.push(
    futureDays.length === 0
      ? 'No time-varying forecast frames are available for this selection.'
      : `Real forecast frames are available up to D+${Math.max(...futureDays)}, each showing this origin's own nominal reach.`,
  )
  explainerLines.push(
    verifiedClinicalCount > 0
      ? `${verifiedClinicalCount} verified clinical ${verifiedClinicalCount === 1 ? 'case has' : 'cases have'} been recorded for this farm.`
      : 'No verified clinical cases have been recorded for this farm in the current scope.',
  )

  return (
    // GEO-MY-AREA-LAYOUT-BALANCE: no `h-full`/internal `overflow-y-auto`
    // here on purpose -- this panel is now `position: sticky` in the
    // page's own grid (`MyAreaPage.jsx`, desktop only) and grows to its
    // own natural content height. Section 13 of the rebalance: the page
    // has exactly ONE deliberate internal scroll region (the outbreak
    // list); this panel stays a normal, non-scrolling sticky block.
    <div className="flex flex-col rounded-xl border border-outline-variant/30 bg-surface-container/70 shadow-card-subtle">
      <div className="flex shrink-0 gap-1 border-b border-outline-variant/20 p-2" role="tablist" aria-label="Area intelligence tabs">
        <button
          type="button"
          role="tab"
          aria-selected={tab === TAB.AREA}
          onClick={() => setTab(TAB.AREA)}
          className={tab === TAB.AREA ? 'rounded-md bg-primary/15 px-3 py-1.5 text-xs font-semibold text-primary' : 'rounded-md px-3 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-surface-container-high/60'}
        >
          Area Intelligence
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === TAB.EXPLAINER}
          onClick={() => setTab(TAB.EXPLAINER)}
          className={tab === TAB.EXPLAINER ? 'rounded-md bg-primary/15 px-3 py-1.5 text-xs font-semibold text-primary' : 'rounded-md px-3 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-surface-container-high/60'}
        >
          AI Explainer
        </button>
      </div>

      <div className="p-3">
        {tab === TAB.AREA ? (
          <div className="flex flex-col gap-3 text-xs">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-on-surface-variant/60">Authorized farm</div>
              <div className="mt-0.5 truncate text-base font-bold text-on-surface" title={primaryAreaLabel}>
                {primaryAreaLabel}
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10.5px] text-on-surface-variant/60">
                {coordinates && <span>{coordinates}</span>}
                {area?.farmId && (
                  <span className="truncate font-mono" title={area.farmId}>
                    {area.farmId}
                  </span>
                )}
              </div>
            </div>

            <dl className="divide-y divide-outline-variant/10 border-t border-outline-variant/10">
              <Row label="Current frame" value={selectedOriginContext ? `${selectedOriginContext.forecastDay === 0 ? 'D0' : `D+${selectedOriginContext.forecastDay}`}${selectedOriginContext.forecastDate ? ` · ${selectedOriginContext.forecastDate}` : ''}` : 'No origin selected'} />
              <Row label="Available forecast window" value={futureDays.length === 0 ? 'Not available' : `D0 – D+${Math.max(...futureDays)}`} />
              <Row
                label="Spatial risk"
                value={
                  !hasSpatialCells
                    ? 'Not available'
                    : selectedOriginContext?.relativeSpatialScore?.value != null
                      ? (Number.isInteger(selectedOriginContext.relativeSpatialScore.value) ? String(selectedOriginContext.relativeSpatialScore.value) : selectedOriginContext.relativeSpatialScore.value.toFixed(2))
                      : selectedOriginContext
                        ? 'Unavailable for this exact location'
                        : null
                }
              />
              <Row label="Relevant origins" value={relevantOriginsCount} />
              <Row label="Recent verified clinical events" value={verifiedClinicalCount} />
              <Row label="Location status" value={area?.locationStatus ?? '—'} />
              <Row label="Total animals" value={typeof area?.totalAnimals === 'number' ? area.totalAnimals : null} />
            </dl>
          </div>
        ) : (
          <ul className="flex flex-col gap-2.5 text-xs text-on-surface-variant">
            {explainerLines.map((line, index) => (
              <li key={index} className="rounded-lg border border-outline-variant/15 bg-surface-container-lowest/40 p-2.5 leading-relaxed">
                {line}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
