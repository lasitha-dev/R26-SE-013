# Existing-model evaluation

This workflow evaluates the existing YOLO, ViT and binary ResNet50 U-Net checkpoints. It never trains, updates weights, changes application thresholds, changes LSD severity arithmetic, or changes highest-confidence single-ROI selection. See [EVALUATION_REPORT.md](EVALUATION_REPORT.md) for measured results and data limitations.

The subsequent [source and annotation review](DATA_REVIEW_REPORT.md) adds reproducible source matching, a separate validation-only geometry experiment and a local review packet. This does not clear the original data's independence or clinical-reference limitations.

Run these commands from the repository root in the existing backend Python environment. Local images, per-image manifests, predictions and probability maps stay in ignored `artifacts/`. All input datasets are read only. Use a new output directory for each experiment; commands refuse to overwrite a manifest, prediction run, frozen policy or test report.

```powershell
python -u -m backend.components.smart_diagnostics.evaluation.audit --yolo-root C:\Users\lasit\merged_dataset --vit-root C:\Users\lasit\vit_dataset --output backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015

python -m backend.components.smart_diagnostics.evaluation.audit_crops --manifest backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/manifest.jsonl --output backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/crop_annotation_audit.json

python -u -m backend.components.smart_diagnostics.evaluation.infer --manifest backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/manifest.jsonl --output backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/predictions

python -m backend.components.smart_diagnostics.evaluation.report validate --manifest backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/manifest.jsonl --predictions backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/predictions --output backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/reports

python -m backend.components.smart_diagnostics.evaluation.report test --manifest backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/manifest.jsonl --predictions backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/predictions --policy backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/reports/frozen_policy.json --output backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/reports/test_report.json
```

The audit hashes file bytes and EXIF-normalized RGB pixels, links crops to conservative filename-lineage bundles, and flags exact 64-bit dHash matches across splits for review. The dHash screen is not an exhaustive near-duplicate search. Generic filenames can overgroup unrelated images. Neither filenames nor perceptual similarity establish animal identity. No old train/val/test split is shuffled or relabelled as independent.

Two scopes are reported: all original samples, and a conservative subset excluding every cross-partition lineage bundle and cross-partition dHash candidate. Train records are included in the audit but never in inference/threshold selection. Missing predictions cause a failed evaluation rather than disappearing from its denominator. Inference verifies audited image hashes; completed caches and frozen policies are hash-bound. Group bootstrap intervals use 300 resamples with seed 13013 and refer to photo-lineage bundles, not verified farms/animals.

The stage comparisons are:

- ViT on the supplied saved crops, with macro F1, per-class precision/recall, confusion, Brier score, negative log-likelihood and descriptive 10-bin calibration error. Crops may contain the notebook's polygon-coordinate parsing error; these are inherited dataset labels, not independently confirmed diagnoses.
- YOLO class-aware greedy precision/recall at IoU 0.5, plus highest-confidence ROI recall against any annotation. Polygon envelopes supply detection boxes; their existence does not establish lesion-mask semantics. These are operating-point metrics, **not mAP**.
- ViT on whole frames versus production YOLO crops. Frame case labels are available only where all annotation classes agree. Mixed-class and empty-labelled frames are explicitly counted and excluded from case classification; they remain in detector metrics. A selected crop that misses every reference region, or no detection, counts as a cascade failure even if a disease guess happens to agree. These reference regions have not been confirmed as the user's selected animal or lesion ROI.
- Binary masks, when reviewed reference masks exist: disease-macro positive-image Dice, IoU, pixel precision/recall, and false-positive area on reviewed negatives. Empty masks never inflate positive-lesion Dice. This currently lacks qualifying reference data.

Validation reports confidence/margin risk-versus-coverage candidates and detector operating points. Those curves describe only confidence filtering; they do not implement all runtime review flags or automatic clinical acceptance. The 60% confidence, 15-point margin and 0.25 detector defaults are preserved. An acceptable error/coverage tradeoff must be specified before selecting a new review threshold. Test reports evaluate fixed defaults/policy without threshold sweeps. Do not tune after viewing test results and call that same cohort unseen.

For segmentation, the predeclared candidate grid is thresholds `[0.3, 0.4, 0.5, 0.6, 0.7]` and minimum area fractions `[0, 15/50176, 50/50176]`, using the runtime's float resizing and 8-neighbour component filtering. Selection requires audited independent validation masks for **all three diseases** plus reviewed negatives. The objective is equal disease-weighted positive Dice; ties use less negative false-positive area, then closeness to 0.5 and smaller filter fraction. This is an offline candidate, not an automatic deployment or a clinical-severity threshold. Check the negative false-positive results and per-disease tradeoffs before approving any future change.

## Supplying independent mask references

Create a separate JSONL manifest using the audited row format, with reviewed original-image lineage and frozen `train`/`val`/`test` groups. For mask evaluation use `kind: "roi"`: an explicitly selected, EXIF-normalized crop and a single-channel binary PNG mask at exactly that crop's dimensions. No automatic ground-truth resizing is performed. `0` is background and either `1` or `255` is symptom foreground. Missing masks are unknown, never negatives. A whole-cow or whole-udder polygon is not a lesion reference.

Additional fields for each mask row:

```json
{
  "mask": "C:/evaluation/masks/case-001.png",
  "mask_reviewed": true,
  "mask_semantics": "visible_lesion_foreground",
  "negative_reviewed": false,
  "independent": true,
  "training_exclusion_evidence": "Document source/animal exclusion against all three training datasets here"
}
```

These fields are attestations with supporting evidence, not proof generated by the software. Keep source IDs, animal/farm IDs, veterinary review and training-image inventories with the study. Union **all reviewed symptom instances** into the binary target. For reviewed negatives supply an explicit empty mask and set `negative_reviewed: true`. Use canonical disease names `foot_and_mouth`, `lumpy_skin`, `mastitis`, or `cattle` for a reviewed healthy control. The current module evaluates annotated-ROI segmentation, not full-frame mask recovery after a detector miss. The latter remains an additional study once relevant ROI and lesion annotations are available.

Clinical FMD/mastitis rules require a separate blinded veterinary reference cohort with the actual checklist observations and clinical grades. These image datasets cannot validate clinical severity, physical lesion-size cutoffs, milk/systemic observations, or the retained LSD score.

```powershell
python -m pytest backend/components/smart_diagnostics/evaluation/test_evaluation.py -q -p no:cacheprovider
```

## Source review and separate validation geometry experiment

`review_sources.json` records the six local YOLO exports and the COCO annotation locations. Update these explicit paths for another machine. Source matching requires identical image bytes and annotation coordinates plus the historical notebook's remapping; a filename match alone is insufficient. Its flags identify review needs, not replacement diagnoses. The historical mapping is reproduced for audit and is not adopted as a recommended new label policy.

The commands below reproduce this follow-up. Existing outputs are preserved, so use new experiment directories when running them again.

```powershell
python -u -m backend.components.smart_diagnostics.evaluation.review --manifest backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/manifest.jsonl --output backend/components/smart_diagnostics/evaluation/artifacts/review_20261015_v2

python -u -m backend.components.smart_diagnostics.evaluation.roi_validation prepare --manifest backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/manifest.jsonl --baseline-predictions backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/predictions --output backend/components/smart_diagnostics/evaluation/artifacts/roi_validation_20261015

python -u -m backend.components.smart_diagnostics.evaluation.infer --manifest backend/components/smart_diagnostics/evaluation/artifacts/roi_validation_20261015/manifest.jsonl --output backend/components/smart_diagnostics/evaluation/artifacts/roi_validation_20261015/predictions --kind roi

python -m backend.components.smart_diagnostics.evaluation.roi_validation compare --manifest backend/components/smart_diagnostics/evaluation/artifacts/roi_validation_20261015/manifest.jsonl --predictions backend/components/smart_diagnostics/evaluation/artifacts/roi_validation_20261015/predictions --baseline-predictions backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/predictions --protocol backend/components/smart_diagnostics/evaluation/artifacts/roi_validation_20261015/protocol.json --output backend/components/smart_diagnostics/evaluation/artifacts/roi_validation_20261015/paired_report.json

python -m backend.components.smart_diagnostics.evaluation.review_packet --manifest backend/components/smart_diagnostics/evaluation/artifacts/legacy_20261015/manifest.jsonl --source-review backend/components/smart_diagnostics/evaluation/artifacts/review_20261015_v2 --roi-experiment backend/components/smart_diagnostics/evaluation/artifacts/roi_validation_20261015 --output backend/components/smart_diagnostics/evaluation/artifacts/review_packet_20261015_v2

python -m pytest backend/components/smart_diagnostics/evaluation/test_evaluation.py backend/components/smart_diagnostics/evaluation/test_review.py -q -p no:cacheprovider
```

Open the generated `index.html` in a browser. Images are embedded for local viewing, with original polygons drawn as SVG outlines. Review-note export is entirely local and does not submit data or approve references. The full label, mask and lineage queues remain separate from the small visual preview. Prepared validation images are new files; box-derived crops retain their original bytes. The historical test set and production ROI policy are preserved.
