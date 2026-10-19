import React, { useState } from 'react';
import { SYMPTOM_OVERLAY_LABEL } from '../modelInfo';

export default function ImageEvidenceViewer({ result, original, cropped, overlay, view, showMask }) {
  const [attention, setAttention] = useState(false);
  const width = result?.image_size?.width || 1;
  const height = result?.image_size?.height || 1;
  const bbox = result?.crop_transform?.crop_box || result?.best_detection?.bbox;
  const crop = bbox?.length === 4 ? { x: bbox[0], y: bbox[1], width: bbox[2] - bbox[0], height: bbox[3] - bbox[1] } : null;
  const highlighted = attention ? result?.attention_image : showMask ? overlay : null;
  return <div className="rounded-xl border border-outline-variant/20 bg-black/20 p-3 space-y-2">
    {result?.attention_image && <label className="flex gap-2 text-xs text-on-surface-variant">
      <input type="checkbox" checked={attention} onChange={(event) => setAttention(event.target.checked)} />
      Show attention explanation (saliency, separate from lesion mask)
    </label>}
    {view === 'full' ? <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Original image with analyzed region"
      className="w-full max-h-[520px]" preserveAspectRatio="xMidYMid meet" data-testid="full-image-evidence">
      <image href={original} x="0" y="0" width={width} height={height} />
      {crop && highlighted && <image href={highlighted} {...crop} preserveAspectRatio="none" data-testid="symptom-overlay-img" />}
      {crop && <rect {...crop} fill="none" stroke="#35cfa2" strokeWidth={Math.max(width, height) / 250} />}
      {crop && <text x={crop.x} y={Math.max(15, crop.y)} fill="#35cfa2" fontSize={Math.max(width, height) / 35}>
        {highlighted && !attention ? 'LESION_MASK' : 'ANALYZED_ROI'}
      </text>}
    </svg> : <img src={highlighted || cropped || original}
      alt={highlighted ? (attention ? 'ViT attention explanation on analyzed region' : `${SYMPTOM_OVERLAY_LABEL} on analyzed region`) : 'Analyzed region'}
      data-testid="lesion-focus-image" className="w-full max-h-[520px] object-contain" />}
    <p className="text-xs text-on-surface-variant">{view === 'full' ? 'Original image; outline marks the analyzed crop.' : 'Analyzed crop at its original aspect ratio.'}
      {showMask && overlay && !attention && ` ${SYMPTOM_OVERLAY_LABEL}. Red: predicted symptom regions.`}</p>
  </div>;
}
