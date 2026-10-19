import React from 'react';
import ClinicalRecommendationCard from './ClinicalRecommendationCard';

/** Render only server-validated points; all text uses React's normal escaping. */
export default function GroundedBriefing({ explanation, assessment, status }) {
  const references = new Map(explanation.references.map(reference => [reference.id, reference]));
  const groups = [
    ['Case evidence', explanation.supporting_evidence],
    ['General reference context', explanation.reference_context],
    ['Limitations and review', explanation.limitations],
    ['Suggested next checks', explanation.next_checks],
  ];
  const fallback = explanation.origin === 'template';
  return <section className="rounded-2xl border border-outline-variant/20 bg-surface-container-low p-5 space-y-4" data-testid="reasoning-briefing" aria-label="Evidence-based explanation">
    <div>
      <h3 className="font-bold text-on-surface">Evidence-based explanation</h3>
      <p className="mt-1 text-xs text-on-surface-variant" role="status">
        {fallback ? 'Reference summary · generated explanation unavailable' : 'LLM-organized evidence and reference context'}
        {status === 'error' ? ' · review required' : ''}
      </p>
    </div>
    {assessment && <p className="text-sm font-bold text-amber-300" data-testid="briefing-severity-grade">{assessment.formatted || assessment.grade}</p>}
    <p className="text-sm text-on-surface-variant">{explanation.summary}</p>
    {explanation.recommendation && <ClinicalRecommendationCard recommendation={explanation.recommendation} />}
    {groups.filter(([, points]) => points?.length).map(([heading, points]) => <div key={heading}>
      <h4 className="text-sm font-bold text-on-surface">{heading}</h4>
      <ul className="mt-2 space-y-2 text-xs leading-relaxed text-on-surface-variant">
        {points.map(point => <li key={point.id} className="border-l-2 border-primary/30 pl-3">
          <p>{point.text}</p>
          {point.reference_ids?.map(id => {
            const reference = references.get(id);
            return reference && <a key={id} className="mt-1 block text-primary underline" href={reference.url} target="_blank" rel="noreferrer">{reference.title}</a>;
          })}
        </li>)}
      </ul>
    </div>)}
    <details className="text-xs text-on-surface-variant">
      <summary className="cursor-pointer">Explanation provenance</summary>
      <p>{explanation.reference_review_status}</p>
      <p className="mt-2">Reference pack: {explanation.reference_pack_version}; prompt: {explanation.prompt_version}</p>
      {explanation.severity_policy_version && <p>Severity policy: {explanation.severity_policy_version}</p>}
      <p className="break-all">Evidence fingerprint: {explanation.evidence_sha256}</p>
    </details>
  </section>;
}
