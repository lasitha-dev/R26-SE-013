import React from 'react'

import {
  LABEL_OPERATIONAL_CONTEXT,
  LABEL_OPERATIONAL_DISEASE,
  LABEL_OPERATIONAL_VERIFIED_AT,
} from '../semanticLabels'

/**
 * GEO-AREA-02 Section 17: the selected farm's qualifying Verified
 * Clinical Context -- reuses the EXACT SAME approved wording GEO-INT-03
 * already established for this concept (`LABEL_OPERATIONAL_CONTEXT` =
 * "Verified clinical context") rather than declaring a second, possibly
 * drifting label. Never historical origin / forecast origin / confirmed
 * outbreak / official outbreak / model input -- a separate, visually
 * distinct operational section. No PII: only case id / disease /
 * verification time are shown (the adapter already stripped everything
 * else, matching GEO-INT-03's `OperationalContextPopup.jsx` field list).
 */
export default function MyAreaClinicalPanel({ verifiedClinicalContexts }) {
  if (!verifiedClinicalContexts || verifiedClinicalContexts.length === 0) return null

  return (
    <div className="rounded-lg border border-primary/20 bg-surface-container/95 p-3 text-xs shadow-card-subtle">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-primary">{LABEL_OPERATIONAL_CONTEXT}</div>
      <ul className="mt-2 space-y-2">
        {verifiedClinicalContexts.map((ctx) => (
          <li key={ctx.caseId} className="rounded-md border border-outline-variant/30 p-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-on-surface-variant/70">{LABEL_OPERATIONAL_DISEASE}</span>
              <span className="text-on-surface-variant">{ctx.disease}</span>
            </div>
            <div className="mt-0.5 flex items-center justify-between gap-2">
              <span className="text-on-surface-variant/70">{LABEL_OPERATIONAL_VERIFIED_AT}</span>
              <span className="text-on-surface-variant">{ctx.verificationTime ?? 'unknown'}</span>
            </div>
            <div className="mt-1 truncate text-on-surface-variant/50" title={ctx.caseId}>
              {ctx.caseId}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
