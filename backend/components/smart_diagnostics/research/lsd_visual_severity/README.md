# LSD visual-severity research prototype

This directory audits LumpySkinDisease_DataHub and trains a separate classifier for its inherited image labels: `normal`, `mild`, and `severe`. The target is **visual LSD skin-lesion grade**. Clinical severity and clinical stage remain veterinary assessments. This experiment does not modify the Smart Diagnostics API, UI, single-ROI selection, segmenter checkpoint, or veterinary records.

Read [EXPERIMENT_REPORT.md](EXPERIMENT_REPORT.md) for the actual audit and held-out results, and [MODEL_CARD.md](MODEL_CARD.md) for interpretation and limitations. The selected trained checkpoint is stored locally at `artifacts/weights/best_model.pt`; large downloads and weights are ignored by Git. Cloning these source files alone does not include trained weights.

Run commands from the repository root. An existing compatible Python environment can be used; otherwise install `requirements.txt` in a separate virtual environment. The recorded run used Python 3.12, PyTorch 2.11 with CUDA 13, and an RTX 3050 Laptop GPU. [artifacts/environment.json](artifacts/environment.json) records exact installed versions. Choose a compatible PyTorch CPU/CUDA installation for your machine using the [official installation instructions](https://pytorch.org/get-started/locally/).

```powershell
python backend/components/smart_diagnostics/research/lsd_visual_severity/download_data.py
python backend/components/smart_diagnostics/research/lsd_visual_severity/audit.py
python backend/components/smart_diagnostics/research/lsd_visual_severity/train.py
python backend/components/smart_diagnostics/research/lsd_visual_severity/predict.py "C:\path\to\cattle-photo.jpg"
```

The first command retrieves only the unbalanced nested ZIP and two source notebooks using verified HTTP ranges. It checks the selected outer member's size/CRC, every nested image CRC, and records its SHA256. The complete 511 MB outer ZIP is not retrieved by default, so its published whole-file MD5 is **not** claimed as verified. Source notebooks are inspected as JSON and never executed. Initial training downloads the official 10 MB ImageNet MobileNet V3 Small weights if they are not already in `data/torch_cache/checkpoints/`.

`audit.py` decodes all images, records checksums and filename labels, applies [content_review.json](content_review.json), builds exact/perceptual/manual similarity groups, excludes conflicting-label components, and writes [artifacts/manifest.csv](artifacts/manifest.csv). The manual content decisions were made before model fitting. They are a single assistant review, not veterinary reannotation. The resulting test set is held out by known image similarity, with no claim of animal/farm independence.

`train.py` uses the frozen manifest and [protocol.json](protocol.json). It compares balanced logistic regression on frozen ImageNet features against a weighted-loss neural head with limited fine tuning. Model selection and temperature scaling use validation data; test inference occurs after both are fixed. No synthetic images, oversampling, or augmented copies are added before splitting. Full images are resized without random cropping. See [artifacts/run_protocol.json](artifacts/run_protocol.json), [artifacts/training_history.json](artifacts/training_history.json), [artifacts/metrics.json](artifacts/metrics.json), and [artifacts/test_predictions.csv](artifacts/test_predictions.csv).

To preserve the reported experiment, copy this research directory to a new experiment location before changing the protocol, content decisions, split, or training configuration. Re-running the scripts overwrites local manifests/results/checkpoints. Do not tune against the reported test results and then describe that same test set as unseen.

The prediction CLI returns a visual grade, three model probabilities, `clinical_severity: null`, `clinical_stage: null`, and `veterinary_review_required: true`. It does not confirm LSD, detect other diseases, score total body lesion coverage, or estimate lesion age. It will still produce probabilities for unsuitable images; it has no validated image-quality or out-of-distribution rejection. Use it only as a supervised research demonstration on in-scope cattle photographs.

Final QA found eight overbroad manual grouping constraints. [artifacts/group_review_errata.json](artifacts/group_review_errata.json) supplies corrected source links. The 782 frozen units are conservative split bundles, not verified unique photographs/animals. Corrected source links remain within those partitions; the model and evaluated manifest were preserved. For a later experiment, use the corrected links and a new external test cohort.

Verify the existing saved CPU export against all recorded GPU test decisions, without retraining:

```powershell
python backend/components/smart_diagnostics/research/lsd_visual_severity/verify_export.py
```

The targeted checks cover mirrored/cropped duplicate grouping, conflict rejection, stable group splits, full-image preprocessing, incompatible checkpoint rejection, and both exported model architectures:

```powershell
python -m pytest backend/components/smart_diagnostics/research/lsd_visual_severity/test_research.py -q -p no:cacheprovider --rootdir=backend/components/smart_diagnostics/research/lsd_visual_severity
```

Data attribution: Francesco Branda, **LumpySkinDisease_DataHub**, version 1 (21 April 2024), [Zenodo DOI 10.5281/zenodo.11003967](https://doi.org/10.5281/zenodo.11003967), declared [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) in the [record API](https://zenodo.org/api/records/11003967). The accompanying study is [Pal et al., Veterinary Medicine and Science (2025)](https://doi.org/10.1002/vms3.70664). Our processing converts images to RGB, filters documented unsuitable/conflicting content, groups known source matches, and creates new experiment splits. Several source photographs visibly carry third-party stock watermarks; individual image provenance and rights were not independently established. Downloaded photographs and review contact sheets remain local and are ignored by Git.

Backbone attribution: [torchvision MobileNet V3 Small, ImageNet1K V1](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html). [artifacts/backbone_provenance.json](artifacts/backbone_provenance.json) records the official weight URL and verified SHA256 prefix; [artifacts/source_provenance.json](artifacts/source_provenance.json) records dataset retrieval evidence. The prototype is a classification model, separate from the application's ResNet50-based segmentation model.
