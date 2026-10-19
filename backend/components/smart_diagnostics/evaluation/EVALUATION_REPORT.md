# Existing-checkpoint evaluation and threshold review

**Follow-up:** [Source and annotation review](DATA_REVIEW_REPORT.md) now traces all 8,515 source-export frames, flags 330 abnormal-udder annotations mapped to `cattle`, and reports a separate validation-only crop correction. The original baseline and test measurements below are preserved. Neither follow-up nor baseline establishes independent clinical accuracy.

15 October 2026. **Baseline evaluation is complete; independent validation and new threshold approval remain incomplete.** No weights were trained or changed. Application thresholds, highest-confidence ROI selection, and LSD severity arithmetic were preserved.

The user supplied `C:\Users\lasit\merged_dataset` and `C:\Users\lasit\vit_dataset`. These are the original notebook datasets, not a verified external cohort. We audited all 20,346 images/crops and ran the existing YOLO and ViT checkpoints on all **4,903 validation/test records**, using production preprocessing and crop selection. ViT used CUDA; inference took approximately 220 seconds after model loading. The ResNet50 U-Net's quantitative lesion evaluation could not proceed without reviewed lesion masks. Its loading/output compatibility was already checked in Phase 1.

## Data audit

| Dataset | Train | Validation | Test |
| --- | ---: | ---: | ---: |
| YOLO images | 6,958 | 1,130 | 942 |
| ViT saved crops | 8,485 | 1,557 | 1,274 |

File-byte and normalized-RGB hashes did not produce cross-split links. Conservative filename-lineage matching produced **681 cross-split links**, and **374 dHash values** occurred across partitions. These are review findings: generic filenames can connect unrelated photos, while transformations can escape the perceptual screen. Neither establishes animal identity. All cross-partition lineage bundles and dHash candidates were excluded from a second reporting scope, leaving 903 validation/635 test frames and 1,375 validation/988 test crops. The exclusion rules were fixed before scoring.

The resulting subset is called `conservative_clean` in the JSON reports. **It is not established as independent**: animal/farm IDs, per-image original sources, complete training exposure and prior checkpoint-selection use of the test set remain unknown. Class labels are inherited rather than newly veterinarian-reviewed. The notebook's label mapper also defaults unrecognized source labels to `cattle`, so that label does not independently establish clinical health.

### Confirmed crop-generation defect

The detector labels contain 9,327 boxes and 2,091 polygons. The ViT dataset-creation notebook interprets the first four polygon coordinates as normalized `x_center, y_center, width, height`. Polygon coordinates instead describe vertex pairs.

**1,994 existing saved crops** have polygon parents: 1,597 train, 246 validation and 151 test; 1,428 labelled cattle and 566 LSD. Every one of these saved crop dimensions matches the erroneous notebook calculation; none matches its polygon's actual bounding envelope. For example, one saved test crop is 97×93 pixels, while the polygon envelope is 363×468. This is evidence of an existing input-construction error, not an effect of this evaluation. Images, annotations and training data were left untouched.

These original crop scores therefore measure performance on the supplied, partly incorrect crops. Review/correct evaluation ROI references in a new evaluation version before treating them as lesion/animal evidence. Do not silently replace test crops and compare the resulting numbers as though the input cohort stayed identical. This finding does not require retraining to continue evaluation, but may eventually explain a training/runtime mismatch.

## Fixed-policy test measurements

All metrics below are relative to inherited labels. Detection uses confidence 0.25 and IoU 0.5. The validation policy was frozen before this run's test scoring. No test threshold sweeps were performed.

| Classification input | Original test n | Accuracy | Macro F1 | Screened test n | Accuracy | Macro F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ViT on saved crops | 1,274 | 88.78% | 0.8773 | 988 | 87.75% | 0.8432 |
| ViT on whole frames | 938 | 90.30% | 0.9007 | 633 | 91.15% | 0.8820 |
| YOLO → ViT, including ROI misses | 938 | 81.24% | 0.8709 | 633 | 79.62% | 0.8361 |

Whole-frame and cascade results use the same cases where all reference annotation labels agree. Four original test frames, or two screened frames, have ambiguous/absent case labels and are excluded from case classification; all remain in detector evaluation. Saved crops are a different sample unit and cohort. Cascade correctness requires the highest-confidence crop to overlap some annotated region at IoU ≥0.5 **and** predict the case label. Missing or incorrect ROIs count as failures. This is a stricter research endpoint than class-name agreement alone; the annotations do not independently establish the farmer's selected animal or a clinically relevant symptom ROI.

For the screened subset, photo-lineage bootstrap 95% intervals are **85.15–89.79%** for saved-crop accuracy and **76.55–82.40%** for cascade accuracy (300 resamples, seed 13013). These intervals do not account for unknown farms/animals, label errors or unresolved source overlap.

| Disease/class, screened test | Saved-crop n | Crop precision | Crop recall | Cascade n | Cascade precision | Cascade recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cattle label | 675 | 94.85% | 87.26% | 378 | 94.41% | 75.93% |
| FMD | 98 | 92.45% | 100.00% | 96 | 98.94% | 96.88% |
| LSD | 130 | 72.67% | 83.85% | 111 | 90.91% | 81.08% |
| Mastitis | 85 | 63.96% | 83.53% | 48 | 62.96% | 70.83% |

The FMD result is not evidence of perfect clinical sensitivity: the cohort is small, inherits source labels, and lacks verified external independence. Mastitis has appreciable false positives and misses; aggregate accuracy conceals this weakness.

YOLO's screened test **class-aware box precision is 78.01%, box recall 76.48%, and highest-confidence ROI recall 87.05%**. It is evaluated on 635 images with 863 reference boxes/envelopes. These are operating-point metrics, not mAP or verified symptom-localization accuracy. Whole-frame classification performed better on this cohort than the retained cascade; this supports further ROI/reference review, not an automatic change to the agreed single-ROI policy.

## Threshold evidence and decision

The screened validation saved-crop results illustrate the confidence tradeoff. The 15-percentage-point top-two margin applies in these rows:

| Minimum top-class confidence | Confidence-filter coverage | Accuracy among retained crops |
| --- | ---: | ---: |
| 60% | 96.51% | 90.35% |
| 80% | 88.51% | 92.36% |
| 90% | 80.22% | 94.29% |
| 95% | 74.04% | 95.78% |

These are **validation-only descriptive candidates**, not selected production cutoffs or clinical guarantees. They describe supplied saved crops, not end-to-end clinical accuracy. They exclude other runtime review flags and require per-class/ROI analysis before deployment. The confidence threshold cannot repair a wrong ROI or a ground-truth annotation error. Validation saved-crop 10-bin calibration error is approximately 5.26 percentage points; no temperature scaling or probability calibration was fitted.

For screened validation detection, raising confidence from 0.25 to 0.40 increases box precision from 80.03% to 86.18%, but lowers selected-ROI recall from 88.00% to 85.33%. Raising it to 0.60 yields 91.94% precision and 77.56% selected-ROI recall. Changing it would trade away cases; it does not establish a universally better operating point.

**Keep detector 0.25, review confidence 60%, margin 15 points, mask threshold 0.5 and minimum component fraction 15/50176 for now.** Their status remains unvalidated operating defaults. There is no agreed acceptable error/coverage tradeoff and no independently verified evaluation cohort to justify promoting alternatives.

The mask validation grid and shared runtime postprocessing are implemented, but **Dice, IoU, negative false-positive area and an optimal mask threshold are not measurable from the current references**. Existing YOLO polygons are unreviewed anatomical/object annotations; FMD COCO files with only boxes cannot substitute for lesion masks. Even a disease label does not identify symptom pixels. Missing annotation is not a healthy/lesion-free control. FMD/mastitis clinical cutoff validation also needs blinded veterinary grades and checklist observations; image labels cannot provide them. LSD scoring was not revalidated or altered.

## What is needed to finish independent validation

1. Reconcile source-image lineage and training/checkpoint-selection exposure; review the cross-split candidates. Supply verified animal/farm groups or an external source cohort where possible. Do not move training images into a newly named test set.
2. Review diagnosis labels and relevant ROI annotations, especially polygon-derived saved crops. Freeze a new evaluation version; retain the current report as the baseline.
3. Add veterinarian-reviewed symptom masks for FMD/LSD/mastitis, with all visible lesion instances included, plus explicit reviewed negative masks. Confirm the exact segmenter normalization and annotation target against its actual training/export recipe.
4. Choose the desired per-disease error/coverage tradeoff, select candidates on validation only, then evaluate once on a separately frozen independent test cohort. Assess clinical rubrics against separate blinded veterinary grades.

No new training is required to carry out those evaluation steps. Phase 2 remains partial until the references and independence evidence are available.

## Reproducibility and software checks

See [README.md](README.md) for commands, mask-manifest requirements and metric conventions. [Published aggregate artifacts](results/legacy_20261015/audit.json), [crop audit](results/legacy_20261015/crop_annotation_audit.json), [validation metrics](results/legacy_20261015/validation_report.json), [frozen policy](results/legacy_20261015/frozen_policy.json), [test metrics](results/legacy_20261015/test_report.json) and [run fingerprints](results/legacy_20261015/run.json) are retained beside the code. Full per-image manifests/predictions remain local in ignored `artifacts/legacy_20261015/`.

Checkpoint SHA-256: ViT `ee684b699363193f04184299b2586e5e03f05ba801fa0103caa8e3f2528e2f41`; YOLO `b7269367dc0dc54575e11f2e8fa513ecdc562c9a60137d5515fbe237f1169d57`. The segmenter remains pinned by its existing manifest. Dataset/prediction/policy hashes are recorded in the artifacts.

The runtime segmenter now exposes raw float probabilities and shares its existing component filter with offline evaluation; its preprocessing, threshold comparisons, connectivity and measurements are preserved. **123 existing backend tests and 15 evaluation tests passed.** Checks cover failure denominators, class support, calibration, greedy matching, ROI misses, empty/negative masks, mask geometry, float precision, leakage claims, group resampling, validation/test separation, threshold selection with incomplete class coverage, frozen outputs and tampered/missing caches. No frontend changes, dataset downloads, clinical records, or model training were part of this phase.
