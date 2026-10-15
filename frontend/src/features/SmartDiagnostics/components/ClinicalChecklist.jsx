import React, { useState } from 'react';

const booleanOptions = [['true', 'Yes'], ['false', 'No']];

export default function ClinicalChecklist({ diseaseKey, busy, onAssess, onEdit }) {
  const [values, setValues] = useState({ vet_confirmed: false });
  const mastitis = diseaseKey === 'mastitis';
  const fields = mastitis ? [
    ['milk_abnormal', 'Abnormal milk (flakes, clots or altered colour)', booleanOptions],
    ['udder_inflammation', 'Udder inflammation (swelling, heat, redness or pain)', booleanOptions],
    ['systemic_illness', 'Systemic illness assessed by the veterinarian (temperature, behaviour, hydration)', booleanOptions],
  ] : [
    ['affected_feet', 'Affected feet (all four examined)', [['0', '0'], ['1', '1'], ['2', '2'], ['3', '3'], ['4', '4']]],
    ['appetite', 'Appetite', [['normal', 'Normal'], ['reduced', 'Reduced'], ['none', 'Absent']]],
    ['mentation', 'Behaviour / mentation', [['normal', 'Normal'], ['slightly_dull', 'Slightly dull'], ['depressed', 'Depressed']]],
    ['heel_and_coronary_involved', 'Heel and coronary band involvement', booleanOptions],
    ['unable_to_stand', 'Unable to stand', booleanOptions],
  ];
  const change = (name, value) => {
    setValues((current) => ({ ...current, [name]: value,
      ...(name !== 'vet_confirmed' ? { vet_confirmed: false } : {}),
    }));
    onEdit();
  };
  const complete = values.vet_confirmed && fields.every(([name]) => values[name] !== undefined && values[name] !== '')
    && (mastitis || (values.mouth_lesion_cm !== undefined && values.mouth_lesion_cm !== '' && Number(values.mouth_lesion_cm) >= 0));
  const submit = (event) => {
    event.preventDefault();
    if (!complete) return;
    const observations = { disease: diseaseKey, vet_confirmed: true };
    fields.forEach(([name, , options]) => {
      observations[name] = options === booleanOptions ? values[name] === 'true'
        : name === 'affected_feet' ? Number(values[name]) : values[name];
    });
    if (!mastitis) observations.mouth_lesion_cm = Number(values.mouth_lesion_cm);
    onAssess(observations);
  };

  return (
    <form onSubmit={submit} className="rounded-xl border border-amber-500/30 bg-surface-container p-4 space-y-3" aria-label="Veterinary clinical checklist">
      <h3 className="font-bold text-sm text-on-surface">Veterinary clinical checklist</h3>
      <p className="text-xs text-on-surface-variant">
        {mastitis ? 'Clinical mastitis grading uses milk, udder and systemic findings.' : 'FMD field triage uses measured lesions, affected feet, appetite and behaviour. Mixed profiles need veterinary grading.'}
        {' '}Record observations for the animal in the selected image crop. Unknown findings cannot be treated as normal.
      </p>
      {fields.map(([name, label, options]) => (
        <label key={name} className="block text-xs text-on-surface-variant">
          {label}
          <select required value={values[name] ?? ''} onChange={(event) => change(name, event.target.value)}
            className="mt-1 block w-full rounded-lg bg-surface-container-highest border border-outline-variant/30 p-2 text-on-surface">
            <option value="">Not assessed / unknown</option>
            {options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
          </select>
        </label>
      ))}
      {!mastitis && <label className="block text-xs text-on-surface-variant">
        Largest oral lesion measured in person (cm; 0 if examined and absent)
        <input type="number" min="0" step="any" required value={values.mouth_lesion_cm ?? ''}
          onChange={(event) => change('mouth_lesion_cm', event.target.value)}
          className="mt-1 block w-full rounded-lg bg-surface-container-highest border border-outline-variant/30 p-2 text-on-surface" />
        <span className="block mt-1">Use a physical measurement; image pixels do not establish centimetres.</span>
      </label>}
      {(values.systemic_illness === 'true' || values.unable_to_stand === 'true') && <p role="alert" className="text-xs text-amber-300">
        Reported systemic illness or inability to stand requires prompt veterinary assessment; do not wait for a completed checklist.
      </p>}
      <label className="flex items-start gap-2 text-xs text-on-surface-variant">
        <input type="checkbox" checked={values.vet_confirmed} onChange={(event) => change('vet_confirmed', event.target.checked)} />
        These observations have been confirmed by the reviewing veterinarian.
      </label>
      <button type="submit" disabled={!complete || busy}
        className="rounded-lg px-4 py-2 bg-primary text-on-primary text-xs font-bold disabled:opacity-50">
        {busy ? 'Assessing observations...' : 'Assess clinical observations'}
      </button>
      <p className="text-xs text-amber-300">Provisional decision support. Clinical accuracy in this application has not been validated. Disease identity still requires veterinary assessment.</p>
    </form>
  );
}
