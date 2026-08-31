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
 *
 * Each row shows a short, vet-facing primary status (never inventing an
 * "Available" state that isn't real) plus the exact underlying reason as
 * small secondary text -- the longer technical phrasing stays readable
 * for anyone who wants it without dominating the row.
 */
export default function AnalysisTrendsEvidencePanel({ modelEvaluation, modelRunComparison, confidence, drivers }) {
  const modelNotReady = modelEvaluation?.status === 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY'

  const rows = [
    {
      label: LABEL_MODEL_EVALUATION,
      status: modelNotReady ? 'Not ready' : 'Unavailable',
      detail: modelNotReady ? LABEL_MODEL_EVALUATION_MODEL_NOT_READY : LABEL_MODEL_EVALUATION_NOT_AVAILABLE,
    },
    {
      label: LABEL_ORIGIN_LEVEL_DIRECTION,
      status: 'Unavailable',
      detail: LABEL_DIRECTION_NOT_DEFINED,
    },
    {
      label: LABEL_CONFIDENCE,
      status: LABEL_CONFIDENCE_NOT_AVAILABLE,
      detail: null,
    },
    {
      label: LABEL_DRIVERS,
      status: LABEL_DRIVERS_NOT_AVAILABLE,
      detail: null,
    },
    {
      label: LABEL_MODEL_RUN_COMPARISON,
      status: LABEL_MODEL_RUN_COMPARISON_NOT_AVAILABLE,
      detail: null,
    },
  ]

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/60 p-3 text-xs sm:p-4">
      <div>
        <div className="font-mono text-xs uppercase tracking-wide text-emerald-300">{LABEL_EVIDENCE_AVAILABILITY}</div>
        <p className="mt-0.5 text-[11px] text-slate-500">Available evidence for the current runtime/model context</p>
      </div>
      <ul className="mt-3 space-y-1.5">
        {rows.map((row) => (
          <EvidenceRow key={row.label} label={row.label} status={row.status} detail={row.detail} />
        ))}
      </ul>
    </div>
  )
}

function EvidenceRow({ label, status, detail }) {
  return (
    <li className="flex items-start justify-between gap-3 rounded-lg border border-white/5 bg-slate-950/40 px-2.5 py-2">
      <span className="text-slate-300">{label}</span>
      <span className="flex flex-col items-end gap-0.5 text-right">
        <span className="flex items-center gap-1.5 text-slate-400">
          <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-slate-600" />
          {status}
        </span>
        {detail && <span className="text-[10px] text-slate-600">{detail}</span>}
      </span>
    </li>
  )
}
