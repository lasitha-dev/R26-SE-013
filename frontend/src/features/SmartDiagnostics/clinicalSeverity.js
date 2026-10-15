export function clinicalDiseaseKey(name) {
  const key = (name || '').toLowerCase().replace(/[^a-z]/g, '');
  if (['fmd', 'footandmouth', 'footandmouthdisease'].includes(key)) return 'foot_and_mouth';
  return key === 'mastitis' ? 'mastitis' : null;
}

// Automatic visual estimates are primary; clinical checklists are an explicit option.
export function resolveSeverity(result, assessment) {
  if (!clinicalDiseaseKey(result?.disease?.name)) return assessment || result?.severity;
  if (assessment?.source === 'clinical_rules') return assessment;
  if (assessment?.source === 'visual_thresholds') return assessment;
  if (result?.severity?.source === 'visual_thresholds') return result.severity;
  if (result?.severity?.source === 'clinical_rules') return result.severity;
  return {
    source: 'clinical_rules', grade: 'Unassessable', assessment_status: 'unassessable',
    formatted: 'Unassessable - clinical review needed', needs_review: true,
    prognosis: 'Not assessed', confidence_level: 'Not validated',
    description: 'Veterinary clinical observations are required. Image confidence and mask coverage do not determine this grade.',
    diagnostic_rationale: 'Complete the disease-specific clinical checklist with the reviewing veterinarian.',
  };
}
