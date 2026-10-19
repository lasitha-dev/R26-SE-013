# Source and annotation review follow-up

15 October 2026. The existing checkpoints, original datasets, runtime thresholds, highest-confidence ROI policy and LSD score remain unchanged. This follow-up traces source exports, creates separate validation crops with corrected polygon geometry, and prepares review material. It does not establish independent clinical accuracy or approve any symptom mask.

Open the [local review packet](artifacts/review_packet_20261015_v2/index.html) in a browser. It contains 16 source/category examples with the original polygons and six old-versus-corrected crop comparisons. Its download button exports sample review notes; these do not change clinical records or approve the full dataset. The packet and full per-image queues are local, ignored artifacts rather than files distributed with the repository.

## Source reconstruction

All **8,515 frames from the six dataset exports** match one original export by filename, exact image SHA-256, annotation coordinates, and the notebook's class remapping. This includes source-export images with empty annotations; it is not a count of confirmed positive cases. The additional user-supplied folder was `C:\Users\lasit\lumpy-skin-diesease--6`.

| Export | Matched frames | Source labels relevant to interpretation |
| --- | ---: | --- |
| atc / lumpy-skin-mdtsn v2 | 1,098 | `lumpyskin`, `normal` |
| yuossef / lumpy-skin-diesease v6 | 739 | `lumpy skin diesease` |
| moaz-ahmen / foot-and-mouth-disease-mfuiw v1 | 520 | `Foot-and-mouth disease` |
| non-fmzye / name1-mb7nq v1 | 520 | Inherited FMD dataset title |
| cow-udder / deteksi-mastitis-sapi v3 | 741 | `abnormal`, `normal` |
| kirubel-yemane / cow-and-mastitis-detection v18 | 4,897 | Behaviour, healthy udder, LSD-infected cow and mastitis-infected udder |

The remaining **515 frames are train-only `background_*` images with empty labels**. Tier 1 notebook cell 2 downloads random farm/field images from LoremFlickr, falling back to Picsum, and writes empty label files. It does not retain the final image URL or verify image content. Their exact photographic origins and suitability as negative controls remain unresolved. They are not reviewed healthy-animal controls or symptom-free mask references.

An export match identifies the local artifact used to construct this dataset. It does not prove which examples the final checkpoint saw, that the test set was unused in model selection, or that different images show different animals/farms. The local metadata declares export licences; individual photograph rights and original capture provenance were not established by this matching exercise.

## Label problems requiring review

The merge function defaults source names without disease keywords to `cattle`. It therefore maps **330 `abnormal` udder annotations to `cattle`**: 300 in the training partition, 24 in validation and six in test. They are annotations, not verified counts of unique animals. `abnormal` is insufficient evidence to relabel every example as mastitis; the current class target should be quarantined for review rather than replaced automatically.

There are also 4,924 behaviour-labelled annotations and 1,874 annotations carrying healthy/normal wording among matched exports. Feeding, drinking, lying and standing annotations describe behaviour, not an independent clinical examination. Consequently, the merged `cattle` class cannot simply be treated as a verified healthy reference group. Earlier classification metrics remain measurements against inherited labels, including these problems.

The source review preserves original labels and creates [a local label queue](artifacts/review_20261015_v2/label_review_queue.csv). The combined [review manifest](artifacts/review_packet_20261015_v2/review_manifest.jsonl) contains 20,346 records with source matches, review flags and parent-crop links. Every record remains `clinical_label_reviewed: false`, `independent: false` and `threshold_selection_eligible: false`. Training images were not moved into evaluation, and source matches do not automatically clear review status.

## Cross-split lineage review

The previous 681 record-level links collapse to **250 frame filename-lineage candidates involving 1,201 frames**. Of those candidate lineages, 141 occur within one matched export and 109 span exports. These counts exclude the crop records when counting frames; they do not replace the previous audit's record-level counts.

Within-export matches warrant checking for augmented siblings across partitions. Cross-export matches may be reused photographs or generic filename collisions. Neither category can be automatically accepted or dismissed. The [local lineage queue](artifacts/review_packet_20261015_v2/lineage_review_queue.jsonl) retains IDs, source exports and partitions for all 250 candidates. Existing conservative exclusions are retained; no group was declared independent solely because its source became known. Perceptual-hash candidates still require separate content review.

## Validation-only crop correction

Before running new predictions, [a separate protocol](results/review_20261015/roi_protocol.json) fixed the intervention: replace polygon-derived **validation** crops with the full annotation envelope and leave box-derived crop bytes unchanged. Labels and weights stay identical. Annotation envelopes are geometric references, not approved symptom regions. The generator checks parent-image hashes, current annotation coordinates and orientation; it refuses mismatches. Regenerated crops use explicit JPEG settings, so decoder/encoder differences may contribute alongside geometry.

| Validation cohort | n | Original accuracy | Envelope-corrected accuracy | Difference |
| --- | ---: | ---: | ---: | ---: |
| All saved crops | 1,557 | 89.66% | 89.85% | +0.19 percentage points |
| Polygon-derived crops | 246 | 83.74% | 84.96% | +1.22 points |
| Box-derived crops, unchanged | 1,311 | 90.77% | 90.77% | 0.00 points |
| Previous conservatively screened subset | 1,375 | 89.31% | 89.60% | +0.29 points |

Thirty predictions changed from wrong to correct, and 27 changed from correct to wrong. The polygon-cohort accuracy-difference bootstrap interval is **−4.99 to +6.91 percentage points**; the overall interval is **−0.77 to +1.21 points**. These photo-lineage intervals include zero and do not support claiming a demonstrated accuracy improvement. They also do not account for unresolved clinical labels or animal/farm dependence.

The original box-crop predictions were unchanged. No original dataset images were overwritten. **Test crops were not regenerated or rescored in this follow-up.** The original baseline remains intact, and these validation results are not a new independent test result. No review or mask threshold was selected from this experiment.

## Symptom-mask audit

The catalog covers **4,644 source-image entries**. These are source/partition entries, not a deduplicated independent cohort. The [mask queue](artifacts/review_20261015_v2/mask_review_queue.jsonl) retains categories and annotation IDs for review. No mask was approved, exported as reference foreground, or inferred from an image-model prediction.

| Source | What the local annotations establish | Why it is not yet lesion ground truth |
| --- | --- | --- |
| My First Project / anatomy export | Foot, head, mouth, torso and udder polygons | Anatomical targets must not be unioned into a symptom mask |
| Mastitis v1 | 20 `Mastitis-High`, 15 `Low`, 31 `Moderate`, 61 `No` annotations across 124 images | Category names do not supply a clinical grading protocol, veterinary review or lesion-boundary definition. `Mastitis-No` polygons must not become positive symptom pixels |
| LSD exports | `lumpy`, `normal`, and disease-name categories | Normal regions and whole-animal/image annotations need to be distinguished from actual lesion outlines |
| Local FMD annotation export | 403 polygons labelled blisters, drooling or erosions across 273 images | Useful annotation candidates, but referenced in the historical training notebook and not established as held out. Species and foreground meaning need review; a visually inspected `pigf_...` sample depicts pig feet. This is not a cattle-only reference collection |
| Two other local FMD exports | Boxes with numeric or disease labels | No pixel segmentation is provided |

The FMD export contains old Label Studio upload paths. The catalog now resolves those paths to the local image basenames without following stale parent-directory traversal. All 273 image files are present. The review packet displays inherited polygons, never model-generated masks disguised as ground truth.

Clinical mastitis severity still requires the actual milk, local inflammation and systemic observations with independent veterinary grading. The local category names are a new review lead, not permission to train another severity model or replace clinical grading. No clinical thresholds were altered.

## Remaining decisions and evidence

1. Review the flagged `abnormal` and behaviour/health labels, recording reviewer identity, source evidence and whether each region supports the intended diagnostic target.
2. Resolve the lineage and perceptual candidates against original photographs and animal/farm records. Keep a genuinely external cohort for final testing; the previously inspected test set cannot become unseen again by changing labels or filenames.
3. Have an appropriate veterinary/annotation reviewer define symptom foreground and assess the existing polygons. Mark non-cattle FMD images out of scope for cattle evaluation. Supply all-instance lesion masks and explicit reviewed negative masks at the evaluated ROI dimensions.
4. Once those references and training-exclusion evidence exist, use validation-only threshold selection and a fresh independent test cohort. The existing evaluation tools can do this without retraining.

The review packet can collect notes now. Clinical diagnosis, clinical grade and independence approval remain pending evidence; they were not manufactured to finish an evaluation.

## Artifacts and checks

Published aggregates: [source matches](results/review_20261015/source_summary.json), [background/lineage summary](results/review_20261015/background_and_lineage_summary.json), [mask catalog](results/review_20261015/mask_source_catalog.json), [crop preparation](results/review_20261015/roi_preparation_summary.json), [paired validation metrics](results/review_20261015/roi_paired_report.json) and [packet fingerprint](results/review_20261015/packet_summary.json). Source images, corrected crops and per-image review queues remain in ignored local artifacts.

**22 evaluation/review tests passed.** New checks cover the actual remapping error, anatomy/normal targets, polygon envelopes, relocated COCO paths, ambiguous image matches, source annotation/hash evidence, nonfinite polygons, preservation of originals and validation-only crop preparation. No production application files or model weights were changed in this follow-up.
