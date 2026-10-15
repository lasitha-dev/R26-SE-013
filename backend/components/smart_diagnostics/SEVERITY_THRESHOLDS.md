# Provisional visual severity thresholds

The runtime combines three model roles: YOLO selects the highest-confidence crop,
ViT provides a disease prediction, and ResNet50 U-Net measures predicted lesion
foreground within that crop. The former confidence-weighted composite is retired:
classifier confidence, attention coverage, cattle count and cattle bounding-box
area do not measure disease severity.

The per-image score is `predicted lesion pixels / analyzed crop pixels` (0–1).
Cutoffs are fixed policy parameters, not recomputed for each image. Recomputing a
cutoff from the same case would make grades inconsistent across cases. The policy
supports a separate profile for LSD, FMD and mastitis.

## Current demonstration policy

`severity_policy.json` contains editable, **unvalidated engineering defaults**:

| Predicted coverage of analyzed crop | Visual grade |
| --- | --- |
| Exactly 0%, with completed empty segmentation | No visible regions |
| Above 0% and below 10% | Mild visual burden |
| At least 10% and below 30% | Moderate visual burden |
| At least 30% | Severe visual burden |

These percentages are not derived from a clinical study. They do not indicate
the proportion of the animal's body affected. Crop framing, body site and mask
errors change the measured fraction. Even a severe clinical case can show a small
visible lesion in one image. Connected regions are not validated lesion counts.

YOLO confidence must be at least 0.25, ViT confidence at least 60%, and the top-two
class margin at least 15 percentage points. Missing/invalid inputs, failed or
skipped segmentation, unsupported disease context, inconsistent segmentation
status/coverage, or failed confidence gates yield `Unassessable`, retaining valid
coverage measurements as evidence. Zero measured foreground does not establish
health. Healthy classifier predictions have no visual grade because segmentation
is skipped. All outputs require review; scores within two percentage points of a
cutoff receive an additional boundary flag. An unverified segmentation training
contract is also shown. Confidence gates themselves remain unvalidated defaults.

FMD and mastitis clinical grades continue to use veterinary observations. Their
visual grade is returned separately in `severity.visual_assessment`. The existing
clinical checklist never obtains a clinical grade from mask percentages. LSD's
`severity.score` now holds crop coverage / 100 when assessable; the obsolete
`composite_score` is null. Consumers must inspect `source`, `assessment_target`
and `formatted`, rather than treating all numeric scores as comparable. LLM
explanations retain the supplied assessment.

## Updating the policy

Set `SEVERITY_POLICY_PATH` to another JSON file, or edit the bundled policy and
restart the backend. Relative paths resolve from `backend/`. Raise the policy
version for each experiment. Every visual response includes the parsed policy's
SHA-256 digest, applied cutoffs, model evidence and review reasons. Invalid JSON,
nonfinite or unordered cutoffs are rejected. A reference URL documents rationale;
adding one does not validate the model or remove the unvalidated status.

## Establishing clinical validity

1. Agree with a veterinarian on a separate target and reference rubric for each
   disease. Specify whether the target is appearance in a standardized crop,
   animal-level clinical severity, or a triage decision. One photograph may be
   insufficient for the latter targets.
2. Collect paired images, model outputs, body-site/framing information, clinical
   findings and blinded veterinary reference grades. Verify lesion masks and
   model-training exclusion. Include normal controls and failures.
3. Keep animals/farms and related photographs together when separating fitting,
   validation and independent test cohorts. Use fitting/validation data to learn
   disease-specific cutoffs or a supervised ordinal fusion model; do not tune
   against the final test cohort. Select the objective with the veterinarian,
   including the cost of missed severe cases and review workload.
4. Freeze the entire pipeline, including ROI/mask policy and confidence gates.
   Evaluate per-grade sensitivity, severe-case misses, confusion matrix,
   weighted agreement, uncertainty intervals and unassessable coverage. Include
   unassessable cases in end-to-end reporting. If predicting probabilities,
   assess calibration and decision utility as well as discrimination.
5. Evaluate on independent farms and prospectively in the intended workflow.
   Literature-informed criteria and a successful software test suite alone do
   not establish clinical accuracy in this application.

Relevant evidence:

- [Krebs et al. (2023), Severity of Clinical Mastitis and Bacterial Shedding](https://pmc.ncbi.nlm.nih.gov/articles/PMC10537990/)
  describes the milk/local-udder/systemic-sign hierarchy. It does not provide
  image coverage cutoffs or validate this application.
- [Ausvet (2023), Animal Health and Welfare Manual, Appendix E](https://www.ausvet.com.au/wp-content/uploads/2023/05/Animal-Health-and-Welfare-Manual-English-compressed-1.pdf#page=46)
  informs the existing FMD field checklist. Its physical lesion sizes cannot be
  substituted with crop pixel percentages.
- [TRIPOD+AI (2024)](https://www.bmj.com/content/385/bmj-2023-078378)
  is a reporting framework for prediction-model development and evaluation,
  including calibration and clinical utility; it is not veterinary validation.
