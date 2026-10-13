import React from 'react'

import {
  LABEL_DISTANCE_FROM_AREA,
  LABEL_MY_AREA_NO_RELEVANT_ORIGINS,
  LABEL_MY_AREA_SELECT_ORIGIN,
  LABEL_NEAREST_T0_TRIGGER_SOURCE,
  LABEL_RELEVANT_ORIGINS,
} from '../semanticLabels'

/**
 * GEO-AREA-02 Section 10/27: authorized-farm summary (real fields only,
 * Section 27 -- never any farmer/vet contact or account detail) plus the
 * relevant-origins list. Section 10's exact required wording: a
 * `distance_basis === 'NEAREST_T0_TRIGGER_SOURCE'` origin is shown via
 * `LABEL_NEAREST_T0_TRIGGER_SOURCE` -- a stronger, unsupported claim
 * about proximity to a live/active event is never used here (see
 * `myAreaPageWiring.test.js`'s forbidden-wording scan).
 */
export default function MyAreaSummaryPanel({ area, relevantOrigins, selectedOriginId, onSelectOrigin }) {
  return (
    <div className="flex flex-col gap-3">
      {area && (
        <div className="rounded-lg border border-outline-variant/30 bg-surface-container/95 p-3 text-xs shadow-card-subtle">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-primary">Area summary</div>
          <dl className="mt-2 space-y-1">
            <Row label="Farm identifier" value={area.farmId} mono />
            {area.locationDistrict && <Row label="District" value={area.locationDistrict} />}
            {typeof area.totalAnimals === 'number' && <Row label="Total animals" value={area.totalAnimals} />}
            <Row label="Location status" value={area.locationStatus} />
          </dl>
        </div>
      )}

      <div className="rounded-lg border border-outline-variant/30 bg-surface-container/95 p-3 text-xs shadow-card-subtle">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-primary">{LABEL_RELEVANT_ORIGINS}</div>

        {relevantOrigins.length === 0 ? (
          <div className="mt-2 text-on-surface-variant">{LABEL_MY_AREA_NO_RELEVANT_ORIGINS}</div>
        ) : (
          <>
            <ul className="mt-2 max-h-72 space-y-1.5 overflow-y-auto">
              {relevantOrigins.map((origin) => {
                const active = origin.originId === selectedOriginId
                return (
                  <li key={origin.originId}>
                    <button
                      type="button"
                      onClick={() => onSelectOrigin(origin.originId)}
                      aria-pressed={active}
                      className={
                        active
                          ? 'w-full rounded-md border border-primary/40 bg-primary/10 p-2 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-primary'
                          : 'w-full rounded-md border border-outline-variant/30 p-2 text-left hover:border-primary/30 hover:bg-surface-container-high focus:outline-none focus-visible:ring-2 focus-visible:ring-primary'
                      }
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-mono text-[11px] text-on-surface" title={origin.originId}>
                          {origin.originId}
                        </span>
                        <span className="shrink-0 rounded-full border border-outline-variant/30 px-1.5 py-0.5 text-[10px] text-on-surface-variant">{origin.disease}</span>
                      </div>
                      {origin.t0 && <div className="mt-0.5 text-on-surface-variant">t0: {origin.t0}</div>}
                      {origin.distanceBasis === 'NEAREST_T0_TRIGGER_SOURCE' ? (
                        <div className="mt-0.5 text-on-surface-variant">
                          {LABEL_NEAREST_T0_TRIGGER_SOURCE}: {origin.distanceFromAreaKm.toFixed(1)} km
                        </div>
                      ) : (
                        <div className="mt-0.5 text-on-surface-variant">
                          {LABEL_DISTANCE_FROM_AREA}: {origin.distanceFromAreaKm.toFixed(1)} km
                        </div>
                      )}
                      {origin.scientificMode && <div className="mt-0.5 text-on-surface-variant/50">{origin.scientificMode}</div>}
                    </button>
                  </li>
                )
              })}
            </ul>
            {!selectedOriginId && <div className="mt-2 text-on-surface-variant/70">{LABEL_MY_AREA_SELECT_ORIGIN}</div>}
          </>
        )}
      </div>
    </div>
  )
}

function Row({ label, value, mono }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-on-surface-variant/70">{label}</dt>
      <dd className={mono ? 'truncate font-mono text-on-surface-variant' : 'text-on-surface-variant'}>{value}</dd>
    </div>
  )
}
