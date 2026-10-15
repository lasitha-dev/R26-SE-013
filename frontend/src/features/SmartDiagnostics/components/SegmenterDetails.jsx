import React from 'react';
import { SEGMENTER_NAME } from '../modelInfo';

export default function SegmenterDetails() {
  return (
    <section aria-label="Symptom segmentation model" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-400/20 bg-surface-container-low p-4">
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="material-symbols-outlined rounded-lg bg-rose-400/10 p-2 text-rose-300">layers</span>
        <div>
          <p className="text-3xs font-mono uppercase tracking-wider text-on-surface-variant">Symptom segmenter</p>
          <h3 className="text-sm font-bold text-on-surface">{SEGMENTER_NAME}</h3>
          <p className="mt-1 text-xs text-on-surface-variant">U-Net with a ResNet50 encoder. Predicted symptom overlays for FMD, LSD and mastitis.</p>
        </div>
      </div>
      <span className="flex items-center gap-2 text-xs text-on-surface-variant">
        <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm bg-red-500/70" />
        Red overlay: predicted symptom regions
      </span>
    </section>
  );
}
