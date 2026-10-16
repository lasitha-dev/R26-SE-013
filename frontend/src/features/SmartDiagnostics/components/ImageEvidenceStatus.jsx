import React from 'react';
import VisualSeverity from './VisualSeverity';

export default function ImageEvidenceStatus({ result }) {
  const segmentation = result?.segmentation;
  const completed = segmentation?.status?.startsWith('completed_');
  return <div className="p-3 rounded-xl bg-surface-container border border-outline-variant/20 space-y-2 text-xs text-on-surface-variant" data-testid="image-evidence-status">
    <p>Lesion segmentation: <strong>{(segmentation?.status || 'unavailable').replaceAll('_', ' ')}</strong></p>
    {completed && <p>Predicted mask: {segmentation.lesion_coverage_pct ?? 'Unknown'}% of analyzed crop pixels; {segmentation.cluster_count ?? 'Unknown'} connected regions.</p>}
    {!completed && <p>Mask measurements were not obtained. No zero-lesion or healthy conclusion is implied.</p>}
    <p>Body site: {result?.body_site ? `${result.body_site} (reported)` : 'Not assessed'}</p>
    {result?.review?.reasons?.length > 0 && <ul className="list-disc pl-4 text-amber-300">
      {result.review.reasons.map((reason) => <li key={reason}>{reason.replaceAll('_', ' ')}</li>)}
    </ul>}
    <p>Model findings provide the initial severity estimate; LLM reasoning refines it using the configured policy.</p>
    <VisualSeverity assessment={result?.severity?.visual_assessment} />
  </div>;
}
