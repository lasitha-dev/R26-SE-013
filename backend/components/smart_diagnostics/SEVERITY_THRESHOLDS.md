# Configurable model and LLM severity estimates

The runtime combines three model roles: YOLO selects the highest-confidence crop,
ViT provides a disease prediction, and ResNet50 U-Net measures predicted lesion
foreground within that crop. The former confidence-weighted composite is retired:
classifier confidence, attention coverage, cattle count and cattle bounding-box
area do not measure disease severity. The initial visual grade is available from
`/api/detect`. `/api/reason` combines that grade with an evidence-backed LLM
recommendation and returns the final automatic estimate as `severity_assessment`.
Both diagnostic screens display and save that final estimate.

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
is skipped. Scores within two percentage points of a cutoff receive a boundary
flag. Missing evidence and image-quality problems also remain visible. Validation
status and segmentation lineage are retained in the evidence details; they do not
automatically require review unless enabled in the policy. Confidence gates
themselves remain unvalidated defaults.

LSD, FMD and mastitis all return an **automatic visual estimate** as the primary
`severity`, without requiring veterinary input. It is available immediately from
`/api/detect`. All diseases use the shared grounded explanation service, with a
reference-summary fallback when the LLM is unavailable. See [REASONING.md](pipeline/REASONING.md). The full visual
evidence remains in `severity.visual_assessment`.

FMD and mastitis clinical checklists are optional, under "Optional clinical
assessment" in the UI. Explicitly submitting clinical observations requests that
separate assessment via `/api/reason`. It does not turn visual cutoffs into clinical
grades. Editing or clearing the clinical assessment restores the original automatic
estimate. Cases recorded from visual estimates retain the provisional visual label
and threshold evidence, without claiming a clinical grade was established.

For automatic visual estimates, `severity.score` holds crop coverage / 100 when
assessable and `composite_score` is null. A combined result has source
`model_llm_reasoning`; its `score` still retains crop coverage / 100, while
`composite_score` holds the weighted ordinal score (1–3). The original visual
grade and thresholds stay in `visual_assessment`, and `reasoning_assessment`
records the LLM grade, weight, weighted score and final cutoffs. Consumers must
inspect `source`, `assessment_target` and `formatted`, rather than treating all
numeric scores as comparable.

## LLM contribution and final grade

The LLM receives structured model findings and any reported symptoms. It returns
an estimated grade and supporting case-evidence IDs, separately from its reference
selections. Reference disease signs, classifier confidence, attention and the
existing grade cannot serve as severity evidence. The backend rejects unsupported
IDs and preserves the visual result if reasoning is unavailable or invalid.
Missing/unreliable model measurements remain unassessable, and optional clinical
checklists are never overridden by the LLM.

Grades have ordinal scores: Mild = 1, Moderate = 2, Severe = 3. The final score is:

```text
score = (1 - reasoning.llm_weight) * visual_grade_score
        + reasoning.llm_weight * llm_grade_score
```

With defaults, the visual grade has 70% weight and the LLM has 30%. A score below
1.5 is Mild, at least 1.5 but below 2.5 is Moderate, and at least 2.5 is Severe.
For example, visual Mild plus LLM Severe yields 1.6, or Moderate. These weights
and cutoffs are configurable engineering choices, not a validated clinical scale.

Edit these keys in `severity_policy.json`:

| Keys | Controls |
| --- | --- |
| `diseases.<disease>.moderate_min_pct`, `severe_min_pct` | Per-disease initial visual thresholds (crop coverage percentage) |
| `minimum_detector_confidence` | Detector gate (0–1) |
| `minimum_classifier_confidence_pct`, `minimum_top_two_margin_pct` | Classifier gates (0–100) |
| `boundary_margin_pct` | Distance from visual thresholds that triggers a boundary check; 0 flags exact boundaries only |
| `reasoning.llm_weight` | LLM influence (0–1); 0 disables LLM influence, 1 uses its grade |
| `reasoning.moderate_min_score`, `reasoning.severe_min_score` | Final ordinal cutoffs (1–3), with moderate below severe |
| `review.require_unvalidated_policy_review` | Require review for policy validation status (default false) |
| `review.require_unverified_segmentation_review` | Require review for missing verified segmentation lineage (default false) |
| `review.minimum_crop_side_px`, `minimum_image_stddev`, `minimum_image_brightness`, `maximum_image_brightness` | Image quality thresholds |

## Updating the policy

Edit the bundled policy; changes apply to subsequent assessments without a
backend restart. Set `SEVERITY_POLICY_PATH` to use another JSON file (restart
after changing this environment setting). Relative paths resolve from `backend/`. Raise the policy
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
