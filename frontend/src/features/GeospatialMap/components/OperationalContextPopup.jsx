import React from 'react'

import {
  LABEL_OPERATIONAL_CASE_COUNT,
  LABEL_OPERATIONAL_CASE_IDS,
  LABEL_OPERATIONAL_CONTEXT,
  LABEL_OPERATIONAL_DISEASE,
  LABEL_OPERATIONAL_DISTRICT,
  LABEL_OPERATIONAL_FARM_ID,
  LABEL_OPERATIONAL_LATEST_VERIFIED,
  LABEL_OPERATIONAL_LOCATION_STATUS,
  LABEL_OPERATIONAL_NEUTRAL_LOCATION,
  LABEL_OPERATIONAL_RECENT_VERIFIED,
} from '../semanticLabels'

const MAX_RECENT_DATES_SHOWN = 5
const MAX_CASE_IDS_SHOWN = 8

/**
 * GEO-INT-03 Section 11 / GEO26B Section 10: compact farm-level
 * operational popup/card -- a plain React-rendered positioned div,
 * mirroring `SourcePopup.jsx`'s exact convention (MapLibre's native
 * `Popup` class is not used anywhere in this feature).
 *
 * `farmAggregate` is one row from `operationalFarmAggregation.js`'s
 * output (or an equivalent single-case shape for the live-toast "View on
 * Map" path before a refresh lands -- see `OutbreakMapPage.jsx`). ONLY
 * real, already-verified fields are shown; no owner name, vet email,
 * phone, or diagnostic reasoning/imagery ever reaches this component.
 * A field this codebase's real DTOs don't carry (e.g. `locationDistrict`)
 * is omitted, never guessed.
 *
 * Every date/time is shown verbatim (Section 19, never "Outbreak
 * started"/"Detected at"/"Onset") -- no Asia/Colombo conversion is
 * attempted because no timezone-aware formatting utility exists anywhere
 * in this feature and the raw backend string carries no timezone marker;
 * displaying it unmodified is honest, a guessed conversion would not be.
 */
export default function OperationalContextPopup({ clinicalContext, onClose }) {
  if (!clinicalContext) return null
  const {
    disease,
    farmId,
    locationDistrict,
    caseCount,
    latestVerificationTime,
    verificationTimes,
    caseIds,
    // Back-compat single-case shape used transiently by the live-toast
    // "View on Map" path before the next operational refresh lands.
    verificationTime,
    caseId,
    personallyAssigned,
  } = clinicalContext

  const effectiveLatest = latestVerificationTime ?? verificationTime ?? null
  const effectiveCount = caseCount ?? (caseId ? 1 : 0)
  const recentDates = (verificationTimes ?? (verificationTime ? [verificationTime] : [])).filter(Boolean)
  const ids = caseIds ?? (caseId ? [caseId] : [])
  // GEO29A Phase 5: `personallyAssigned` defaults true (matches the
  // backend/adapter default) so every pre-existing caller keeps showing
  // the real farm identifier exactly as before.
  const showRealFarmId = personallyAssigned !== false

  return (
    <div className="pointer-events-auto w-64 rounded-lg border border-primary/30 bg-surface-container/95 p-3 text-sm shadow-card-subtle">
      <div className="flex items-start justify-between">
        <div className="font-mono text-xs uppercase tracking-wide text-primary">{LABEL_OPERATIONAL_CONTEXT}</div>
        <button type="button" onClick={onClose} aria-label="Close" className="text-on-surface-variant/70 hover:text-on-surface">
          ×
        </button>
      </div>
      <dl className="mt-2 space-y-1 text-xs">
        <Row label={LABEL_OPERATIONAL_DISEASE} value={disease} />
        {showRealFarmId ? (
          <Row label={LABEL_OPERATIONAL_FARM_ID} value={farmId} mono />
        ) : (
          <Row label={LABEL_OPERATIONAL_FARM_ID} value={LABEL_OPERATIONAL_NEUTRAL_LOCATION} />
        )}
        {locationDistrict && <Row label={LABEL_OPERATIONAL_DISTRICT} value={locationDistrict} />}
        <Row label={LABEL_OPERATIONAL_CASE_COUNT} value={String(effectiveCount)} />
        <Row label={LABEL_OPERATIONAL_LATEST_VERIFIED} value={effectiveLatest ?? 'unknown'} />
        <Row label={LABEL_OPERATIONAL_LOCATION_STATUS} value="VALID" />
      </dl>

      {recentDates.length > 1 && (
        <div className="mt-2 border-t border-outline-variant/30 pt-2 text-xs">
          <div className="text-on-surface-variant/70">{LABEL_OPERATIONAL_RECENT_VERIFIED}</div>
          <ul className="mt-1 space-y-0.5 text-on-surface-variant">
            {recentDates.slice(0, MAX_RECENT_DATES_SHOWN).map((t, i) => (
              <li key={`${t}-${i}`}>{t}</li>
            ))}
            {recentDates.length > MAX_RECENT_DATES_SHOWN && (
              <li className="text-on-surface-variant/70">+{recentDates.length - MAX_RECENT_DATES_SHOWN} more</li>
            )}
          </ul>
        </div>
      )}

      {ids.length > 0 && (
        <div className="mt-2 border-t border-outline-variant/30 pt-2 text-xs text-on-surface-variant/70" title={ids.join(', ')}>
          <span>{LABEL_OPERATIONAL_CASE_IDS}: </span>
          <span className="text-on-surface-variant">
            {ids.slice(0, MAX_CASE_IDS_SHOWN).join(', ')}
            {ids.length > MAX_CASE_IDS_SHOWN ? `, +${ids.length - MAX_CASE_IDS_SHOWN} more` : ''}
          </span>
        </div>
      )}
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
