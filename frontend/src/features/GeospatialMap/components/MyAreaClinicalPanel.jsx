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
    <div className="rounded-lg border border-teal-400/30 bg-slate-900/70 p-3 text-xs">
      <div className="font-mono uppercase tracking-wide text-teal-300">{LABEL_OPERATIONAL_CONTEXT}</div>
      <ul className="mt-2 space-y-2">
        {verifiedClinicalContexts.map((ctx) => (
          <li key={ctx.caseId} className="rounded-md border border-white/10 p-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-slate-500">{LABEL_OPERATIONAL_DISEASE}</span>
              <span className="text-slate-300">{ctx.disease}</span>
            </div>
            <div className="mt-0.5 flex items-center justify-between gap-2">
              <span className="text-slate-500">{LABEL_OPERATIONAL_VERIFIED_AT}</span>
              <span className="text-slate-300">{ctx.verificationTime ?? 'unknown'}</span>
            </div>
            <div className="mt-1 truncate text-slate-600" title={ctx.caseId}>
              {ctx.caseId}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
