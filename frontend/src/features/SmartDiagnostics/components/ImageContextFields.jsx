import React from 'react';

export default function ImageContextFields({ value, onChange }) {
  return <fieldset className="grid gap-3 mb-4 text-xs text-on-surface-variant">
    <legend className="font-bold mb-2">Reported image context (optional)</legend>
    <label>Body site
      <input value={value.body_site || ''} maxLength={120} placeholder="Not assessed"
        onChange={(event) => onChange({ ...value, body_site: event.target.value })}
        className="block w-full mt-1 p-2 rounded bg-surface-container-highest" />
    </label>
    <label>Observed symptoms
      <textarea value={value.observed_symptoms || ''} maxLength={1000} placeholder="Reported observations, pending veterinary review"
        onChange={(event) => onChange({ ...value, observed_symptoms: event.target.value })}
        className="block w-full mt-1 p-2 rounded bg-surface-container-highest" />
    </label>
  </fieldset>;
}
