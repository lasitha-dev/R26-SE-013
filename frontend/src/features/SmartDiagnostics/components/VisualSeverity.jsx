import React from 'react';

export default function VisualSeverity({ assessment }) {
  if (!assessment) return null;
  const thresholds = assessment.thresholds_pct || {};
  const evidence = assessment.evidence || {};
  const graded = ['Mild', 'Moderate', 'Severe'].includes(assessment.grade);
  const color = assessment.grade === 'Severe' ? 'text-rose-300' : assessment.grade === 'Moderate' ? 'text-amber-300' : 'text-on-surface';
  return <section aria-label="Visual severity estimate" className="rounded-xl border border-outline-variant/20 bg-surface-container p-4 space-y-2 text-xs text-on-surface-variant">
    <h3 className="font-bold text-on-surface">Visual lesion burden · provisional</h3>
    <p className={`text-sm font-bold ${color}`} data-testid="visual-severity-grade">{assessment.grade}{graded ? ' visual burden' : ''}</p>
    <p>{assessment.coverage_pct == null ? 'Coverage unavailable' : `${assessment.coverage_pct}% predicted lesion coverage in the analyzed crop`}</p>
    {thresholds.moderate_min_pct != null && thresholds.severe_min_pct != null && <>
      <p>Mild: above 0% and below {thresholds.moderate_min_pct}%; Moderate: {thresholds.moderate_min_pct}% to below {thresholds.severe_min_pct}%; Severe: {thresholds.severe_min_pct}% or above.</p>
      <div className="flex h-2 overflow-hidden rounded-full" aria-hidden="true">
        <span className="bg-emerald-400/60" style={{ width: `${thresholds.moderate_min_pct}%` }} />
        <span className="bg-amber-400/60" style={{ width: `${thresholds.severe_min_pct - thresholds.moderate_min_pct}%` }} />
        <span className="bg-rose-400/60" style={{ width: `${100 - thresholds.severe_min_pct}%` }} />
      </div>
    </>}
    <p>Detector confidence: {evidence.yolo_confidence == null ? 'Unknown' : `${(evidence.yolo_confidence * 100).toFixed(1)}%`}; disease confidence: {evidence.vit_confidence_pct ?? 'Unknown'}%; class margin: {evidence.top2_margin_pct ?? 'Unknown'} points.</p>
    <details>
      <summary className="cursor-pointer">Threshold evidence and review reasons</summary>
      <p>Unvalidated thresholds. This estimates crop appearance; clinical severity, total body involvement and disease stage require clinical assessment.</p>
      <p className="mt-2">{assessment.rationale}</p>
      <p>Policy: {assessment.policy_version}</p>
      {assessment.review_reasons?.length > 0 && <ul className="list-disc pl-4">{assessment.review_reasons.map(reason => <li key={reason}>{reason.replaceAll('_', ' ')}</li>)}</ul>}
      {assessment.references?.map(reference => <a className="block underline" key={reference.url} href={reference.url} target="_blank" rel="noreferrer">{reference.title}</a>)}
    </details>
  </section>;
}
