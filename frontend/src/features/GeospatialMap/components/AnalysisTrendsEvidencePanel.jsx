import React from 'react'

import {
  LABEL_CONFIDENCE,
  LABEL_CONFIDENCE_NOT_AVAILABLE,
  LABEL_DRIVERS,
  LABEL_DRIVERS_NOT_AVAILABLE,
  LABEL_EVIDENCE_AVAILABILITY,
  LABEL_MODEL_EVALUATION,
  LABEL_MODEL_EVALUATION_MODEL_NOT_READY,
  LABEL_MODEL_EVALUATION_NOT_AVAILABLE,
  LABEL_MODEL_RUN_COMPARISON,
  LABEL_MODEL_RUN_COMPARISON_NOT_AVAILABLE,
  LABEL_ORIGIN_LEVEL_DIRECTION,
  LABEL_DIRECTION_NOT_DEFINED,
} from '../semanticLabels'

/**
 * GEO-ANALYSIS-02 Section 30-34: instead of fabricating an evaluation
 * score, a numeric confidence indicator, an environmental-contribution
 * breakdown, or a comparison between stored model runs, makes every
 * unavailable-evidence block look INTENTIONAL -- a compact, visually
 * clean panel of explicit "not available" statements. This is
 * scientifically stronger and visually cleaner than a page full of
 * placeholder `—`/`0`/`N/A %` values (Section 34's own framing).
 */
export default function AnalysisTrendsEvidencePanel({ modelEvaluation, modelRunComparison, confidence, drivers }) {
  const evaluationLabel =
    modelEvaluation?.status === 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY'
      ? LABEL_MODEL_EVALUATION_MODEL_NOT_READY
      : LABEL_MODEL_EVALUATION_NOT_AVAILABLE

  return (
    <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3 text-xs">
      <div className="font-mono uppercase tracking-wide text-emerald-300">{LABEL_EVIDENCE_AVAILABILITY}</div>
      <ul className="mt-2 space-y-1.5">
        <EvidenceRow label={LABEL_MODEL_EVALUATION} state={evaluationLabel} />
        <EvidenceRow label={LABEL_ORIGIN_LEVEL_DIRECTION} state={LABEL_DIRECTION_NOT_DEFINED} />
        <EvidenceRow label={LABEL_CONFIDENCE} state={LABEL_CONFIDENCE_NOT_AVAILABLE} />
        <EvidenceRow label={LABEL_DRIVERS} state={LABEL_DRIVERS_NOT_AVAILABLE} />
        <EvidenceRow label={LABEL_MODEL_RUN_COMPARISON} state={LABEL_MODEL_RUN_COMPARISON_NOT_AVAILABLE} />
      </ul>
    </div>
  )
}

function EvidenceRow({ label, state }) {
  return (
    <li className="flex items-center justify-between gap-2 rounded-md border border-white/5 bg-slate-950/40 px-2 py-1.5">
      <span className="text-slate-300">{label}</span>
      <span className="flex items-center gap-1.5 text-slate-500">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-slate-600" />
        {state}
      </span>
    </li>
  )
}
