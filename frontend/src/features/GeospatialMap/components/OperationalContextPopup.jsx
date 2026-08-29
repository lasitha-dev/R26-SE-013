import React from 'react'

import {
  LABEL_OPERATIONAL_CONTEXT,
  LABEL_OPERATIONAL_DISEASE,
  LABEL_OPERATIONAL_DISTRICT,
  LABEL_OPERATIONAL_FARM_ID,
  LABEL_OPERATIONAL_LOCATION_STATUS,
  LABEL_OPERATIONAL_VERIFIED_AT,
} from '../semanticLabels'

/**
 * GEO-INT-03 Section 11: compact operational popup/card -- a plain
 * React-rendered positioned div, mirroring `SourcePopup.jsx`'s exact
 * convention (MapLibre's native `Popup` class is not used anywhere in
 * this feature). ONLY the Section 11 approved fields are shown; no
 * owner name, vet email, phone, or diagnostic reasoning/imagery ever
 * reaches this component (`operationalContextAdapter.js` already strips
 * everything else before this point).
 *
 * `verificationTime` is shown verbatim, labelled `Verification time`
 * (Section 19, never "Outbreak started"/"Detected at"/"Onset") -- no
 * Asia/Colombo conversion is attempted because no timezone-aware
 * formatting utility exists anywhere in this feature (confirmed by
 * inspection) and the raw backend string carries no timezone marker;
 * displaying it unmodified is honest, a guessed conversion would not be.
 */
export default function OperationalContextPopup({ clinicalContext, onClose }) {
  if (!clinicalContext) return null
  const { caseId, disease, farmId, locationDistrict, verificationTime } = clinicalContext

  return (
    <div className="pointer-events-auto w-60 rounded-lg border border-teal-400/30 bg-slate-900/95 p-3 text-sm shadow-xl">
      <div className="flex items-start justify-between">
        <div className="font-mono text-xs uppercase tracking-wide text-teal-300">{LABEL_OPERATIONAL_CONTEXT}</div>
        <button type="button" onClick={onClose} aria-label="Close" className="text-slate-500 hover:text-white">
          ×
        </button>
      </div>
      <dl className="mt-2 space-y-1 text-xs">
        <Row label={LABEL_OPERATIONAL_DISEASE} value={disease} />
        <Row label={LABEL_OPERATIONAL_FARM_ID} value={farmId} mono />
        {locationDistrict && <Row label={LABEL_OPERATIONAL_DISTRICT} value={locationDistrict} />}
        <Row label={LABEL_OPERATIONAL_VERIFIED_AT} value={verificationTime ?? 'unknown'} />
        <Row label={LABEL_OPERATIONAL_LOCATION_STATUS} value="VALID" />
      </dl>
      <div className="mt-2 truncate text-slate-500" title={caseId}>
        {caseId}
      </div>
    </div>
  )
}

function Row({ label, value, mono }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className={mono ? 'truncate font-mono text-slate-300' : 'text-slate-300'}>{value}</dd>
    </div>
  )
}
