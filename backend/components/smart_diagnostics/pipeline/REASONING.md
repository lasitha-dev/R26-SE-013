# Grounded veterinary explanations

LSD, FMD and mastitis use the same local explanation service. Automatic visual
grades and optional clinical checklists remain deterministic. Explanation failures
never replace their scores, measurements, unknowns or review flags.

## Evidence and reference flow

`/api/reason` builds a JSON evidence record containing the selected ROI, class
probabilities, segmentation status/measurements/denominator, full assessment,
visual thresholds and policy hashes, attention telemetry, review reasons,
optional clinical findings, reported symptoms/body site, crop geometry and model
metadata. The LLM receives structured data, not the photograph. Probabilities
remain uncalibrated; attention does not become lesion evidence.

`reference_packs.json` supplies short source-checked summaries and optional next
checks for each disease. They were checked against the cited WOAH pages and
Krebs et al. (2023); veterinary review is still pending. No vector database,
runtime web search, model-generated URLs or unsupported treatment advice is used.
These reference summaries do not validate visual cutoffs or establish findings in
an individual animal. Review and version the reference pack when updating it;
restart the backend to clear the cached pack.

To make grounding enforceable, the LLM selects catalog IDs in a JSON-schema
response: case evidence, general reference facts, limitations and next checks.
It does **not** write unrestricted clinical prose. The server validates types,
assessment kind, applicable IDs and duplicates, then renders source-bound text.
The model can select/order optional points but cannot create claims, citations,
numbers, diagnoses or severity fields. Essential assessment evidence, all
applicable limitations and disease-specific confirmation/check items remain
mandatory even when the model omits them. User-reported observations stay labelled
as unverified data, including instruction-like text.

This is constrained explanation organization, not an independent diagnostic model.
It reduces the model's freedom to hallucinate at the cost of less flexible prose.
It does not ensure that upstream model measurements, reported findings or the
references themselves are correct. Clinical usefulness requires veterinary review.

## Responses and UI

`ReasoningResponse.explanation` contains the structured display document:
summary, case evidence, general reference context, limitations, next checks and
server-owned reference links. `reasoning_report` contains the same information
in Markdown for saved reports and older consumers. Both carry provenance:
evidence/reference-pack SHA-256 hashes, reference/prompt versions and severity
policy metadata. These fingerprints identify supplied content; they do not prove
its clinical accuracy, provenance or training independence.

`origin: llm_selected` means valid model selections were used. `origin: template`
means the server's reference summary was used instead. Unavailable service,
unsupported structured output, invalid IDs, attempted new fields, empty/truncated
output and request failures yield a labelled fallback with the original assessment.
No response text from an invalid generation is displayed. No analyzed ROI yields
`unavailable` without inventing evidence. Optional checklists remain usable when
explanation generation falls back.

Both veterinary and farmer views display the explanation separately from the
immediate severity result. Request revisions clear stale explanations after image
or checklist changes. The prior Markdown formatter and severity-metadata parser
remain compatibility helpers; the active service does not use them to extract or
replace grades.

## Model configuration

Set `REASONING_MODEL_NAME` to the exact local model identifier (default:
`qwen2.5-vl-3b-instruct`). The service does not switch to the first listed model.
The current local endpoint is configured in `pipeline/config.py`; timeouts and
retry limits are in component settings. Requests use temperature 0.1, up to 800
output tokens and LM Studio JSON-schema output.

[LM Studio's structured-output documentation](https://lmstudio.ai/docs/developer/openai-compat/structured-output)
notes that not all models support this feature, especially smaller models. The
configured model needs a live compatibility check. The implementation does not
silently retry as unrestricted prose when schema output fails.

## Reproducible checks

From `backend/`, run software checks without model weights or a live server:

```powershell
python -m pytest components/smart_diagnostics/tests test_dynamic_severity.py -q -p no:cacheprovider
python -m components.smart_diagnostics.evaluation.reasoning_benchmark --output components/smart_diagnostics/evaluation/artifacts/reasoning_template_v1.json
```

The fixed synthetic set has eight scenarios per disease: moderate visual burden,
boundary coverage, measured empty mask, missing mask, low confidence, reported
history, instruction-like user notes, and detector/classifier disagreement.
Tests also reject forged citations, grade/score fields, cross-disease references,
duplicate IDs, malformed JSON and truncated output. Mocked selections verify the
application contract, not the quality of an actual LLM.

Once LM Studio is serving the configured model, use a new report filename:

```powershell
python -m components.smart_diagnostics.evaluation.reasoning_benchmark --live --limit 3 --output components/smart_diagnostics/evaluation/artifacts/reasoning_live_smoke_v1.json
python -m components.smart_diagnostics.evaluation.reasoning_benchmark --live --output components/smart_diagnostics/evaluation/artifacts/reasoning_live_full_v1.json
```

Reports include per-case latency, model identity, accepted/fallback counts,
structured explanations and unchanged-assessment checks. Existing report files
are never overwritten. A run with fallbacks or changed assessments exits nonzero.
These synthetic checks are not clinical validation or a comparison of diagnostic
accuracy. Compare models only on a frozen case set and add blinded veterinary
ratings of correctness, relevance, omissions and usefulness on independent cases.

During implementation, the configured local endpoint refused connections, so no
live model acceptance rate, latency or quality improvement was established.
